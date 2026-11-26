"""이젠, 안쉼 재현 실습 (실습 01~14 통합본).

포트폴리오 p.9~12의 핵심 검색 및 답변 생성 흐름을 소규모 데이터로 실습한다.
원본 저장소 전체를 복제한 코드는 아니다.

구현 범위:
- 데이터 준비, 임베딩, Chroma 검색, 자연어 조건 추출 및 후보 정리
- 충분성 판단, Tavily 외부 검색 및 결과 정제
- 규칙 기반 자격 판정, 내부 LLM 답변 및 외부 템플릿 답변

남은 범위:
- LangGraph 워크플로우 연결 및 LLM-as-a-Judge 평가
- 실제 공고의 모든 자격 요건, 신청 시작일·시각, 외부 공고의 최신성 검증
- 정확한 지원 유형 구분 및 외부 결과의 세부 자격 검증

실습용 코드이며 실제 정책의 신청 가능 여부를 보장하지 않는다.
"""

import json
import os
from datetime import date
from urllib.parse import urlparse

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient


# ============================================================
# 1. 환경 및 실험 설정
# ============================================================

# .env에서 API 키를 읽는다. 키를 코드에 직접 적거나 GitHub에 올리지 않는다.
load_dotenv()
client = OpenAI()

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

# 기존 실습에서 사용한 Chroma 저장 위치와 컬렉션 이름을 유지한다.
DB_PATH = "./practice_vector_db"
COLLECTION_NAME = "youth_policy"

# 검색 단계에서 가져올 최대 청크 수 (현재 실습 데이터는 4개).
FETCH_K = 4

# False: 기존 벡터 재사용. DB가 비어 있으면 자동으로 최초 적재한다.
# True: 정책 본문이나 메타데이터를 변경했을 때 기존 ID를 갱신한다.
# upsert는 삭제된 청크까지 자동으로 제거하지 않는다.
UPDATE_INDEX = False

# 실습할 질문과 마감 여부 판단 기준일.
QUERY = "월세 지원 정책 알려줘"
AS_OF = None  # 실험 B: 실행 당일 기준 (외부 검색 분기 확인)
# AS_OF = date(2026, 6, 1)  # 실험 A: 과거 기준일 (내부 검색 분기 확인)


# ============================================================
# 2. 실습용 원본 정책 데이터 (p.12)
# ============================================================

# 정책 한 건은 하나의 item_id를 갖는다.
# documents: 유형별로 구분한 검색 대상 본문
# metadata: 검색 이후 조건 비교 등에 사용하는 구조화된 정보
# 실습용 데이터이므로 실제 공고의 세부 자격 조건과 예외는 생략되어 있다.
POLICIES = [
    {
        "item_id": "policy_001",
        "title": "2026년 서울시 청년월세지원",
        "documents": {
            "summary": (
                "서울 청년의 주거비 부담을 줄이기 위해 "
                "월세를 월 최대 20만 원씩 12개월 동안 지원하는 사업"
            ),
            "eligibility": (
                "서울시 청년월세지원 사업의 신청 대상 연령은 "
                "19세 이상 39세 이하이며, 서울에 거주해야 한다."
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 39,
            "region": "서울",
            "domain": "주거",
            "application_end_date": "2026-05-19"
        }
    },
    {
        "item_id": "policy_002",
        "title": "2026년 대전시 청년월세지원",
        "documents": {
            "summary": (
                "대전시 거주 19~39세 무주택 청년에게 "
                "월세를 월 최대 20만 원씩 12개월 지원하는 사업"
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 39,
            "region": "대전",
            "domain": "주거",
            "application_end_date": "2026-09-10"
        }
    },
    {
        "item_id": "policy_003",
        "title": "2026년 서울시 청년수당",
        "documents": {
            "summary": (
                "서울시 거주 19~34세 미취업 청년에게 "
                "활동지원금을 월 50만 원씩 최대 6개월 지급하는 청년수당 사업"
            )
        },
        "metadata": {
            "age_min": 19,
            "age_max": 34,
            "region": "서울",
            "domain": "일자리",
            "application_end_date": "2026-05-29"
        }
    }
]


# ============================================================
# 3. 데이터 준비: 청킹, 임베딩, Chroma 적재 (p.10, p.12)
# ============================================================

def build_chunks(policies):
    """
    정책 단위 데이터를 검색용 청크 단위로 변환한다.

    item_id: 원본 정책의 고유 ID
    chunk_id: 개별 청크의 고유 ID
    document: 임베딩할 본문
    metadata: 필터링 및 원본 정책 식별에 사용할 정보

    동일한 정책의 청크들은 같은 정책 메타데이터를 갖는다.
    """

    chunks = []

    for policy in policies:
        item_id = policy["item_id"]

        # documents 딕셔너리를 순회하며 청크를 생성한다.
        # 예: chunk_type = "summary", document = "지원 내용..."
        for chunk_type, document in policy["documents"].items():

            chunk = {
                "chunk_id": f"{item_id}::{chunk_type}",
                "document": document,

                # 원본 정책의 메타데이터를 각 청크에 전달한다.
                # item_id는 검색 결과를 정책 단위로 묶을 때 사용한다.
                "metadata": {
                    **policy["metadata"],
                    "item_id": item_id,
                    "title": policy["title"],
                    "chunk_type": chunk_type
                }
            }

            chunks.append(chunk)

    return chunks


def embed_texts(texts):
    """
    문자열 리스트를 임베딩 벡터 리스트로 변환한다.

    문서와 사용자 질문 모두 동일한 임베딩 모델을 사용한다.
    text-embedding-3-small의 기본 출력은 1536차원 벡터이다.
    """

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    # API 응답의 index를 기준으로 입력 텍스트의 순서를 맞춘다.
    items = sorted(response.data, key=lambda item: item.index)

    return [item.embedding for item in items]


def get_collection():
    """
    로컬 Chroma DB에 연결하고 컬렉션을 반환한다.

    PersistentClient:
        데이터를 디스크에 저장하여 프로그램 종료 후에도 유지한다.

    cosine:
        벡터 간의 코사인 거리를 검색 기준으로 사용한다.
    """

    chroma_client = chromadb.PersistentClient(
        path=DB_PATH
    )

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={
            "hnsw": {"space": "cosine"}
        }
    )

    return collection


def index_chunks(collection, chunks):
    """
    각 청크의 본문을 임베딩하고 Chroma에 저장한다.

    Chroma에는 다음 정보를 함께 저장한다.
    - 청크 ID
    - 본문
    - 임베딩 벡터
    - 메타데이터
    """

    # 임베딩할 대상은 청크의 본문이다.
    texts = [chunk["document"] for chunk in chunks]

    # 여러 청크를 한 번의 API 호출로 임베딩한다.
    embeddings = embed_texts(texts)

    # upsert는 ID가 없으면 추가하고, 있으면 갱신한다.
    collection.upsert(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[chunk["metadata"] for chunk in chunks]
    )

    print("저장된 청크 수:", collection.count())


# ============================================================
# 4. 자연어 조건 추출 (p.9~10)
# ============================================================

def extract_conditions(query):
    """
    사용자의 자연어 질문에서 나이, 지역, 관심 분야를 추출한다.
    반환값은 Python 딕셔너리이다.
    """

    # LLM이 수행할 역할과 출력 형식을 지정한다.
    system_prompt = """
    당신은 청년정책 검색을 위한 사용자 조건 추출기입니다.

    사용자 질문에서 다음 정보를 추출하세요.

    - age: 나이 (정수)
    - region: 거주 지역 (예: 서울, 대전, 경기)
    - interest_domain: 관심 분야

    관심 분야는 다음 중 하나로 분류하세요.
    일자리, 주거, 교육, 금융, 창업, 복지문화, 참여권리

    확인할 수 없는 정보는 추측하지 말고 null로 반환하세요.

    반드시 다음 형식의 JSON으로 반환하세요.

    {
        "age": null,
        "region": null,
        "interest_domain": null
    }
    """

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    # LLM이 반환한 JSON 문자열
    raw_text = response.choices[0].message.content

    print("LLM 원본 출력:", raw_text)

    # JSON 문자열을 Python 딕셔너리로 변환한다.
    # JSON Mode는 필드의 타입과 값의 정확성까지 보장하지는 않는다.
    conditions = json.loads(raw_text)

    return conditions


# ============================================================
# 5. 내부 검색 및 후보 정리 (p.10~11)
# ============================================================

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


# ============================================================
# 6. 검색 결과 충분성 판단 및 외부 검색 (p.11)
# ============================================================

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


def search_external(query):
    """
    내부 검색 결과가 부족할 때 공식 사이트를 검색한다.

    검색 결과의 제목, 본문 일부, 출처 URL을 반환한다.
    """

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        print("Tavily API 키가 설정되지 않았습니다.")
        return []

    tavily_client = TavilyClient(api_key=api_key)

    # 검색 범위를 공식 사이트 도메인으로 제한한다.
    # 공식 도메인이라도 공고 마감 여부나 실제 신청 자격을 보장하지 않는다.
    response = tavily_client.search(
        query=query,
        search_depth="basic",
        max_results=3,
        include_domains=[
            "youthcenter.go.kr",
            "youth.seoul.go.kr",
            "housing.seoul.go.kr",
            "daejeon.go.kr",
            "bokjiro.go.kr",
            "work24.go.kr",
            "hrd.go.kr",
            "k-startup.go.kr"
        ]
    )

    return response["results"]


def refine_external_results(results):
    """
    Tavily 외부 검색 결과를 정제한다.

    1. 동일한 URL의 검색 결과를 제거한다.
    2. 사이트 메인 페이지를 제외한다.
    3. 일반 안내 페이지를 후순위로 배치한다.
    """

    refined = []
    seen_urls = set()

    for result in results:
        url = result["url"]
        title = result["title"]

        # URL을 구성 요소별로 분리한다.
        parsed = urlparse(url)

        # 1. 사이트 메인 페이지 제외
        if parsed.path in ("", "/") and not parsed.query:
            print("메인 페이지 제외:", title)
            continue

        # 2. 동일한 URL 중복 제거
        normalized_url = parsed._replace(
            path=parsed.path.rstrip("/"),
            fragment=""
        ).geturl()

        if normalized_url in seen_urls:
            print("중복 URL 제외:", title)
            continue

        seen_urls.add(normalized_url)

        # 3. 일반 안내 페이지인지 판단
        is_general_page = "개요" in title

        refined.append({
            **result,
            "is_general_page": is_general_page
        })

    # 1순위: 일반 안내 페이지가 아닌 결과
    # 2순위: Tavily 검색 점수가 높은 결과
    ranked = sorted(
        refined,
        key=lambda result: (
            not result["is_general_page"],
            result["score"]
        ),
        reverse=True
    )

    return ranked

# ============================================================
# 7. 자격 가능성 판단 (p.10)
# ============================================================

def check_eligibility(result, user_age, user_region):
    """
    사용자 조건과 정책의 신청 요건을 비교한다.

    matched: 충족한 조건
    unmatched: 충족하지 못한 조건
    missing: 추가 확인이 필요한 조건
    """

    metadata = result["metadata"]

    matched = []
    unmatched = []
    missing = []

    # 1. 연령 조건 판단
    if user_age is None:
        missing.append("사용자 나이 정보 없음")

    elif metadata["age_min"] <= user_age <= metadata["age_max"]:
        matched.append("연령 조건 충족")

    else:
        unmatched.append("연령 조건 불충족")

    # 2. 지역 조건 판단
    if user_region is None:
        missing.append("사용자 지역 정보 없음")

    elif metadata["region"] == user_region:
        matched.append("지역 조건 충족")

    else:
        unmatched.append("지역 조건 불충족")

    # 3. 아직 검증하지 않은 세부 자격 요건
    # 현재 실습 데이터는 소득, 고용 상태 등
    # 세부 조건이 생략되어 있으므로 기본값을 True로 둔다.
    if metadata.get("needs_detail_check", True):
        missing.append("정책별 세부 자격 요건 확인 필요")

    # 4. 최종 자격 가능성 판단
    if unmatched:
        eligibility = "가능성 낮음"

    elif missing:
        eligibility = "추가 확인 필요"

    else:
        eligibility = "가능성 높음"

    return {
        "eligibility": eligibility,
        "matched": matched,
        "unmatched": unmatched,
        "missing": missing
    }


def build_internal_context(results, user_age, user_region):
    """
    내부 검색 후보마다 자격을 한 번씩 판정하고 답변용 근거를 구성한다.

    반환하는 각 딕셔너리에는 정책명, 본문, 메타데이터와 판정 결과가 들어 있다.
    출력 함수와 답변 생성 함수가 동일한 판정 데이터를 재사용하므로
    자격 판정을 중복 실행하지 않는다.
    """

    context = []

    for result in results:
        judgment = check_eligibility(result, user_age, user_region)

        # 검색 결과와 규칙 기반 판정 결과를 하나로 묶는다.
        context.append({
            "title": result["metadata"]["title"],
            "document": result["document"],
            "metadata": result["metadata"],
            "judgment": judgment
        })

    return context


# ============================================================
# 8. 근거 기반 최종 답변 생성 (p.10~11)
# ============================================================

def generate_internal_answer(query, context, as_of):
    """
    검색 근거와 이미 계산한 자격 판정을 LLM에 전달한다.

    자격 판정은 Python 코드에서 수행하며, LLM은 판정 근거를 바탕으로
    자연어 답변을 생성한다. 프롬프트만으로 사실 오류를 완전히 방지할 수는 없다.
    """

    system_prompt = """
    당신은 청년정책 안내 서비스입니다.

    제공된 검색 결과와 자격 판정 근거만 사용하여
    사용자의 질문에 답변하세요.

    다음 규칙을 준수하세요.

    1. 제공되지 않은 정보를 만들어내지 마세요.
    2. 자격 판정 결과를 임의로 변경하지 마세요.
    3. 확인이 필요한 조건은 명시하세요.
    4. 질문과 관련 없는 정책은 추천하지 마세요.
    5. 마감 판단 기준일과 실제 현재 날짜를 혼동하지 마세요.
    """

    user_prompt = f"""
    사용자 질문: {query}
    마감 판단 기준일: {as_of}

    검색 결과 및 자격 판정 근거:
    {json.dumps(context, ensure_ascii=False, indent=2)}
    """

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


def generate_external_answer(results):
    """
    외부 검색 결과를 정해진 답변 양식으로 구성한다.

    확인되지 않은 신청 자격이나 모집 여부를
    임의로 판단하지 않는다.
    """

    if not results:
        return "관련 근거를 찾지 못했습니다."

    answer = [
        "내부 데이터에서 답변에 충분한 근거를 확보하지 못했습니다.",
        "공식 사이트에서 다음 확인 후보를 찾았습니다."
    ]

    for i, result in enumerate(results, start=1):

        # 검색된 본문의 일부를 발췌한다.
        preview = result["content"][:300]

        answer.append(
            f"\n{i}. {result['title']}"
        )
        answer.append(f"본문 일부: {preview}...")
        answer.append(f"출처: {result['url']}")
        answer.append("신청 가능 여부: 추가 확인 필요")

    answer.append(
        "\n정확한 신청 기간과 자격 조건은 "
        "공식 원문에서 확인해야 합니다."
    )

    return "\n".join(answer)


# ============================================================
# 9. 실습 결과 출력
# ============================================================

def print_results(title, results):
    """
    검색 결과를 확인하기 위한 출력 함수.

    각 처리 단계에서 어떤 후보가 남았는지 확인할 수 있다.
    """

    print(f"\n[{title}]")
    print("결과 수:", len(results))
    print("-" * 60)

    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]

        print(f"{rank}. {metadata['title']}")
        print("청크 ID:", result["chunk_id"])
        print("정책 ID:", metadata["item_id"])
        print("지역:", metadata["region"])
        print("분야:", metadata["domain"])
        print("유사도:", round(result["score"], 4))
        print("본문:", result["document"])
        print("-" * 60)


def print_eligibility_results(context):
    """이미 계산한 내부 후보의 자격 판정 결과와 근거를 출력한다."""
    print("\n[7. 내부 검색 결과 자격 가능성 판단]")

    for item in context:
        judgment = item["judgment"]

        print("정책명:", item["title"])
        print("판정:", judgment["eligibility"])
        print("충족 조건:", judgment["matched"])
        print("불충족 조건:", judgment["unmatched"])
        print("확인 필요:", judgment["missing"])
        print("-" * 60)


def print_external_results(results):
    """외부 검색 API가 반환한 근거 후보를 출력한다."""
    print("\n[7. Tavily 외부 검색 결과]")
    print("결과 수:", len(results))

    for result in results:
        print("제목:", result["title"])
        print("URL:", result["url"])
        print("내용:", result["content"])
        print("검색 점수:", result["score"])
        print("-" * 60)

    if not results:
        # 키가 없어서 실행하지 못한 경우도 []가 반환될 수 있다.
        print("사용 가능한 외부 검색 결과가 없습니다.")
    else:
        print("외부 결과의 실제 신청 가능 여부는 공식 원문에서 확인해야 합니다.")


# ============================================================
# 10. 전체 실행 흐름
# ============================================================

def main():
    """각 기능을 순서대로 호출하고 내부/외부 검색 경로를 선택한다."""

    # --------------------------------------------------------
    # A. 데이터 적재 (Indexing)
    # --------------------------------------------------------
    collection = get_collection()

    if UPDATE_INDEX or collection.count() == 0:
        chunks = build_chunks(POLICIES)
        print("원본 정책 수:", len(POLICIES))
        print("생성된 청크 수:", len(chunks))
        index_chunks(collection, chunks)
    else:
        print("기존 Chroma DB 사용")
        print("저장된 청크 수:", collection.count())

    # --------------------------------------------------------
    # B. 사용자 질문 및 조건 추출
    # --------------------------------------------------------
    query = QUERY
    as_of = AS_OF if AS_OF is not None else date.today()

    print("\n사용자 질문:", query)
    print("마감 판단 기준일:", as_of)

    # 자연어 질문에서 조건을 추출한다. 누락된 정보는 None이다.
    conditions = extract_conditions(query)
    user_age = conditions["age"]
    user_region = conditions["region"]
    user_domain = conditions["interest_domain"]

    print("나이:", user_age)
    print("지역:", user_region)
    print("관심 분야:", user_domain)

    # --------------------------------------------------------
    # C. 내부 의미 검색: 질문과 유사한 청크 찾기
    # --------------------------------------------------------
    retrieved_results = search_chunks(collection, query)
    print_results("1. 의미 검색 결과", retrieved_results)

    # --------------------------------------------------------
    # D. 후보 필터링: 알려진 나이·지역 조건과 불일치하는 후보 제외
    # --------------------------------------------------------
    filtered_results = filter_results(retrieved_results, user_age, user_region)
    print_results("2. 나이 및 지역 필터링 결과", filtered_results)

    # --------------------------------------------------------
    # E. 중복 제거: 같은 정책의 대표 청크만 선택
    # --------------------------------------------------------
    unique_results = deduplicate_results(filtered_results)
    print_results("3. 정책 단위 중복 제거 결과", unique_results)

    # --------------------------------------------------------
    # F. 재정렬: 관심 분야 일치 여부 → 유사도 순서
    # --------------------------------------------------------
    ranked_results = rerank_results(unique_results, user_domain)
    print_results("4. 재정렬 결과", ranked_results)

    # --------------------------------------------------------
    # G. 마감 필터링: 기준일보다 마감일이 앞선 공고 제외
    # --------------------------------------------------------
    remaining_results = filter_expired_results(ranked_results, as_of=as_of)
    print_results("5. 마감 공고 필터링 결과", remaining_results)

    # --------------------------------------------------------
    # H. 충분성 판단: 내부 후보를 사용할지, 외부 검색할지 결정
    # --------------------------------------------------------
    sufficient, reason = check_sufficiency(remaining_results, user_domain)

    print("\n[6. 검색 결과 충분성 판단]")
    print("충분 여부:", sufficient)
    print("판단 근거:", reason)

    # --------------------------------------------------------
    # I. 조건 분기 및 답변 생성
    # --------------------------------------------------------
    # 충분성 판단 결과에 따라 두 경로 중 하나만 실행한다.
    # 내부 경로: 자격 판정 → LLM 답변 생성
    # 외부 경로: Tavily 검색 → 결과 정제 → 템플릿 답변 생성
    if sufficient:
        print("내부 검색 결과 사용. 외부 검색 생략.")

        # 정책별 자격 판정을 한 번만 수행하여 출력과 답변에 재사용한다.
        context = build_internal_context(
            remaining_results, user_age, user_region
        )
        print_eligibility_results(context)

        answer = generate_internal_answer(query, context, as_of)

    else:
        # Tavily 검색은 한 번만 호출한다.
        # AS_OF가 과거여도 Tavily는 실행 시점의 웹을 검색한다.
        raw_external_results = search_external(query)
        print("외부 검색 원본 결과 수:", len(raw_external_results))

        # URL 중복, 메인 페이지, 일반 안내 페이지를 처리한다.
        external_results = refine_external_results(raw_external_results)
        print_external_results(external_results)

        # 외부 자료는 내부 정책과 동일한 메타데이터가 없으므로
        # 자격 판정 함수에 전달하지 않고 확인 후보로만 안내한다.
        answer = generate_external_answer(external_results)

    # --------------------------------------------------------
    # J. 최종 답변 출력 (두 경로 공통)
    # --------------------------------------------------------
    print("\n[8. 최종 답변]")
    print(answer)


if __name__ == "__main__":
    main()
