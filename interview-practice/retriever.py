"""내부 검색과 후보 정리 (p.10~11).

workflow에서 질문·컬렉션을 받아 청크별 본문과 점수를 반환한다. 사용자 조건과 기준일에 따라
후보를 정책 단위로 좁힌다. 충분성과 이유를 돌려주면 workflow가 내부 답변 또는 외부 검색을 선택한다."""

from datetime import date

from config import FETCH_K
from indexing import embed_texts


def search_chunks(collection, query, fetch_k=FETCH_K):
    """
    사용자 질문과 의미적으로 유사한 청크를 검색한다.

    1. 질문을 임베딩한다.
    2. Chroma에서 가까운 벡터를 검색한다.
    3. 검색 결과를 다루기 편한 딕셔너리 리스트로 변환한다.

    이 단계에서는 사용자의 나이와 지역 조건을 비교하지 않는다.
    fetch_k는 필터링 전에 가져올 후보 수이며 최종 추천 수와는 다르다.
    """

    if collection.count() == 0:
        return []

    # 질문 역시 문서와 동일한 모델로 임베딩해야 비교할 수 있다.
    query_embedding = embed_texts([query])[0]

    raw_results = collection.query(
        query_embeddings=[query_embedding],

        # 저장된 청크 개수보다 많이 요청하지 않도록 제한한다.
        n_results=min(fetch_k, collection.count()),

        include=["documents", "metadatas", "distances"]
    )

    results = []

    # Chroma는 여러 질문을 한 번에 검색할 수 있으므로
    # 반환값이 중첩 리스트 형태이다.
    # 현재는 질문 하나만 검색하므로 [0]을 사용한다.
    for i in range(len(raw_results["ids"][0])):

        distance = raw_results["distances"][0][i]

        # 코사인 거리 = 1 - 코사인 유사도
        # 따라서 거리가 작을수록 유사도가 높다.
        score = 1 - distance

        result = {
            "chunk_id": raw_results["ids"][0][i],
            "document": raw_results["documents"][0][i],
            "metadata": raw_results["metadatas"][0][i],
            "distance": distance,
            "score": score
        }

        results.append(result)

    return results


def filter_results(results, user_age, user_region):
    """
    의미 검색 결과에서 사용자의 기본 조건과 맞지 않는 청크를 제외한다.

    나이 조건:
        age_min <= user_age <= age_max

    지역 조건:
        정책 대상 지역 == 사용자 거주 지역

    사용자 조건이 None이면 해당 필터를 생략한다.
    정책의 메타데이터 자체가 누락된 경우와 전국 대상 정책은 아직 처리하지 않는다.
    """

    filtered = []

    for result in results:
        metadata = result["metadata"]

        # 사용자의 나이를 모르면 연령 필터링을 생략한다.
        age_match = (
            user_age is None
            or metadata["age_min"] <= user_age <= metadata["age_max"]
        )

        # 사용자의 지역을 모르면 지역 필터링을 생략한다.
        region_match = (
            user_region is None
            or metadata["region"] == user_region
        )

        # 알려진 조건에 모두 맞는 후보를 유지한다.
        # 모르는 조건을 통과시키는 것은 신청 자격 충족을 뜻하지 않는다.
        if age_match and region_match:
            filtered.append(result)

    return filtered


def deduplicate_results(results):
    """
    동일한 정책에 속하는 여러 청크 중 대표 청크를 선택한다.

    딕셔너리의 key:
        item_id

    딕셔너리의 value:
        해당 정책에서 유사도가 가장 높은 청크

    청크 단위 검색 결과를 정책 단위 추천 후보로 변환한다.
    """

    unique_results = {}

    for result in results:

        # chunk_id가 아닌 원본 정책의 item_id를 사용한다.
        item_id = result["metadata"]["item_id"]

        # 처음 등장한 정책이라면 그대로 저장한다.
        if item_id not in unique_results:
            unique_results[item_id] = result

        # 이미 등장한 정책이라면 유사도를 비교한다.
        elif result["score"] > unique_results[item_id]["score"]:
            unique_results[item_id] = result

    return list(unique_results.values())


def rerank_results(results, user_domain):
    """
    관심 분야와 유사도를 기준으로 검색 결과를 재정렬한다.

    1순위: 사용자 관심 분야와 일치하는 정책
    2순위: 코사인 유사도가 높은 정책

    관심 분야가 다르더라도 무조건 제외하지는 않는다.
    단지 추천 순서를 낮춘다.

    별도의 AI Reranker 모델을 사용하는 것이 아니라
    Python 정렬 기능을 이용한 규칙 기반 재정렬이다.
    """

    ranked = sorted(
        results,
        key=lambda result: (
            result["metadata"]["domain"] == user_domain,
            result["score"]
        ),
        reverse=True
    )

    return ranked


def filter_expired_results(results, as_of=None):
    """
    신청 마감일이 지난 정책을 검색 후보에서 제외한다.

    as_of: 마감 여부를 판단할 기준 날짜
    기준 날짜가 지정되지 않으면 오늘 날짜를 사용한다.
    신청 시작일과 마감 시각은 아직 검사하지 않는다.
    """

    if as_of is None:
        as_of = date.today()

    filtered = []

    for result in results:
        metadata = result["metadata"]
        end_date = metadata.get("application_end_date")

        # 마감일 정보가 없으면 후보를 유지한다.
        # 단, 현재 신청 가능하다는 의미는 아니다.
        if not end_date:
            filtered.append(result)
            continue

        # 문자열을 날짜 객체로 변환한다.
        deadline = date.fromisoformat(end_date)

        # 마감일이 지나지 않은 정책만 유지한다.
        if deadline >= as_of:
            filtered.append(result)

    return filtered


def check_sufficiency(results, user_domain):
    """
    내부 검색 후보의 존재 여부와 관심 분야 일치 여부를 검사한다.
    실제 레포지토리보다 단순화한 학습용 기준이며,
    True여도 모든 후보의 직접 관련성이나 근거가 보장되지는 않는다.

    반환값:
        sufficient: 충분성 판단 결과 (bool)
        reason: 판단 근거 (str)
    """

    # 검색 결과가 한 건도 없는 경우
    if not results:
        return False, "내부 검색 결과 없음"

    # 관심 분야가 명확하지만 일치하는 정책이 없는 경우
    if user_domain is not None:
        domain_matched = any(
            result["metadata"]["domain"] == user_domain
            for result in results
        )

        if not domain_matched:
            return False, "관심 분야와 일치하는 정책 없음"

    return True, "관련 검색 후보 존재"
