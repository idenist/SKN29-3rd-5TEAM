"""워크플로우와 실험이 공유하는 Chroma 검색·후보 정리 (p.10~11).

입력은 컬렉션, 질문 벡터, 조건과 기준일이다. 검색 청크와 정리된 정책·단계별 개수를 반환한다.
분야 우선 정렬은 간단한 규칙이다. 충분 여부만으로 실제 자격이나 답변 품질을 확정할 수 없다.
"""

from datetime import date

from config import FETCH_K
from indexing import embed_texts
from policy_filters import candidate_matches, domain_matches, period_match


def search_by_vector(collection, embedding, fetch_k, conditions, mode="post"):
    """한 질문 벡터를 재사용해 원래 Chroma 거리 순으로 청크를 가져온다."""
    if mode not in ("pre", "post") or fetch_k < 1:
        raise ValueError("검색 방식은 pre/post, FETCH_K는 양수여야 합니다.")
    count = collection.count()
    if not count:
        return []
    age, region = conditions.get("age"), conditions.get("region")
    where = None
    if mode == "pre" and (age is not None or region):
        # 복수 코드는 쉼표 문자열이다. 전체 메타데이터에 공통 판정을 적용한 뒤,
        # 같은 정책의 모든 청크에 전파된 item_id로 Chroma 검색 범위를 제한한다.
        # 전체 스캔과 긴 $in 목록의 비용이 있으므로 속도 개선을 가정하지 않는다.
        metadata = collection.get(include=["metadatas"])["metadatas"]
        allowed_ids = {m["item_id"] for m in metadata if candidate_matches(m, age, region)}
        if not allowed_ids:
            return []
        where = {"item_id": {"$in": sorted(allowed_ids)}}

    raw = collection.query(query_embeddings=[embedding], n_results=min(fetch_k, count),
                           where=where, include=["documents", "metadatas", "distances"])
    # 질문 한 건에 대한 네 병렬 목록. 코사인 거리의 방향을 바꿔 큰 점수가 먼저 오게 한다.
    return [
        {"chunk_id": key, "document": doc, "metadata": meta, "distance": dist, "score": 1 - dist}
        for key, doc, meta, dist in zip(raw["ids"][0], raw["documents"][0],
                                       raw["metadatas"][0], raw["distances"][0])
    ]


def search_chunks(collection, query, fetch_k=FETCH_K, conditions=None, mode="post"):
    """한 질문을 문서와 같은 모델로 임베딩한다. 비교 실험은 search_by_vector에 같은 벡터를 준다."""
    return search_by_vector(collection, embed_texts([query])[0], fetch_k, conditions or {}, mode)


def filter_results(results, user_age, user_region):
    """검색 청크에서 명시적인 연령·지역 불일치만 제외한다."""
    return [r for r in results if candidate_matches(r["metadata"], user_age, user_region)]


def deduplicate_results(results):
    """정책별 최고 유사도 청크 하나를 남긴다. 동점은 먼저 검색된 청크가 남고 다른 본문은 빠진다."""
    best = {}
    for result in results:
        key = result["metadata"]["item_id"]
        if key not in best or result["score"] > best[key]["score"]:
            best[key] = result
    return list(best.values())


def rerank_results(results, user_domain):
    """분야 일치 여부를 먼저, 같은 그룹에서는 원래의 유사도를 비교한다."""
    return sorted(results, key=lambda r: (domain_matches(r["metadata"], user_domain), r["score"]),
                  reverse=True)


def filter_expired_results(results, as_of=None):
    """상시·특정 기간·마감 규칙으로 명시된 기간 밖의 정책을 제외하고 미확인은 유지한다."""
    day = as_of or date.today()
    return [r for r in results if period_match(r["metadata"], day) is not False]


def refine_candidates(results, conditions, as_of, top_k):
    """검색 청크를 정책 단위로 정리한 뒤에만 TOP_K를 적용한다. 각 단계의 개수도 함께 반환한다."""
    if top_k < 1:
        raise ValueError("TOP_K는 양수여야 합니다.")
    filtered = filter_results(results, conditions["age"], conditions["region"])
    unique = deduplicate_results(filtered)
    ranked = rerank_results(unique, conditions["interest_domain"])
    available = filter_expired_results(ranked, as_of)
    final = available[:top_k]
    counts = {"조건 필터링": len(filtered), "중복 제거": len(unique), "재정렬": len(ranked),
              "마감 필터링": len(available), "최종 정책": len(final)}
    return final, counts


def check_sufficiency(results, user_domain):
    """빈 후보 또는 관심 분야 전체 불일치면 외부 경로를 선택한다. 유사도 임계값은 사용하지 않는다."""
    if not results:
        return False, "내부 검색 결과 없음"
    if user_domain and not any(domain_matches(r["metadata"], user_domain) for r in results):
        return False, "관심 분야와 일치하는 정책 없음"
    return True, "관련 검색 후보 존재"
