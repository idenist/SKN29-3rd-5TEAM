from typing import Any, TypedDict

from backend.services.condition_extractor import (
    extract_conditions,
    conditions_to_retriever_filters,
    build_query_from_conditions,
)
from backend.services.rag_service import retrieve_policies
from backend.services.policy_matcher import attach_eligibility_to_policies
from backend.services.answer_generator import generate_answer


class GraphState(TypedDict, total=False):
    # input
    user_query: str

    # intermediate
    user_conditions: dict[str, Any]
    route: str
    route_reason: str
    filters: dict[str, Any]
    retriever_query: str
    retrieved_chunks: list[dict[str, Any]]
    eligibility_results: list[dict[str, Any]]

    # output
    answer: str
    warnings: list[str]
    errors: list[str]


ROUTE_DOMAINS = {
    "일자리",
    "주거",
    "교육",
    "복지문화",
    "참여권리",
    "금융",
    "창업",
    "기타",
    "전체",
}


DOMAIN_KEYWORDS = {
    "일자리": [
        "취업",
        "구직",
        "재직",
        "중소기업",
        "면접",
        "이력서",
        "자소서",
        "인턴",
        "일자리",
        "채용",
        "고용",
        "취준",
        "취준생",
        "미취업",
        "재취업",
    ],
    "주거": [
        "월세",
        "전세",
        "주거",
        "임대",
        "보증금",
        "주택",
        "집",
        "기숙사",
        "청년주택",
    ],
    "금융": [
        "대출",
        "저축",
        "자산",
        "계좌",
        "적금",
        "통장",
        "목돈",
        "금융",
        "청년도약",
        "이자",
    ],
    "창업": [
        "창업",
        "사업",
        "예비창업",
        "예비창업자",
        "스타트업",
        "사업자",
        "창업지원",
    ],
    "교육": [
        "교육",
        "자격증",
        "훈련",
        "학습",
        "강의",
        "수업",
        "시험",
        "응시료",
        "국가기술자격",
        "직무교육",
    ],
    "복지문화": [
        "복지",
        "문화",
        "건강",
        "심리",
        "상담",
        "생활비",
        "마음건강",
        "교통비",
    ],
    "참여권리": [
        "참여",
        "권리",
        "정책참여",
        "청년참여",
        "위원",
        "네트워크",
        "공론장",
        "청년정책네트워크",
    ],
}


DOMAIN_ALIASES = {
    "취업": "일자리",
    "구직": "일자리",
    "고용": "일자리",
    "일자리": "일자리",
    "주거": "주거",
    "월세": "주거",
    "전세": "주거",
    "금융": "금융",
    "자산": "금융",
    "저축": "금융",
    "교육": "교육",
    "자격증": "교육",
    "창업": "창업",
    "복지": "복지문화",
    "문화": "복지문화",
    "복지문화": "복지문화",
    "참여": "참여권리",
    "참여기반": "참여권리",
    "참여권리": "참여권리",
    "청년참여": "참여권리",
    "unknown": "전체",
    "기타": "전체",
}

SOURCE_CATEGORY_KEYWORDS = {
    "training": [
        "국비지원",
        "국비",
        "국민내일배움카드",
        "내일배움카드",
        "훈련",
        "훈련과정",
        "교육과정",
        "직업훈련",
        "직무훈련",
        "k-digital",
        "k digital",
        "kdt",
        "부트캠프",
        "개발자 과정",
        "데이터 분석 과정",
        "ai 과정",
        "hrd",
        "고용24",
    ],
    "startup_notice": [
        "창업공고",
        "창업 지원사업",
        "창업지원사업",
        "사업화",
        "예비창업",
        "예비창업자",
        "초기창업",
        "스타트업",
        "창업교육",
        "창업진흥원",
        "k-startup",
        "입주기업",
        "입주공간",
        "ir",
        "투자유치",
        "창업자금",
    ],
    "policy": [
        "정책",
        "수당",
        "지원금",
        "장려금",
        "월세",
        "전세",
        "주거",
        "저축",
        "적금",
        "계좌",
        "청년도약계좌",
        "청년수당",
        "교통비",
        "면접수당",
        "응시료 지원",
        "복지",
    ],
}

def _append_warning(state: GraphState, message: str) -> list[str]:
    return state.get("warnings", []) + [message]


def _append_error(state: GraphState, message: str) -> list[str]:
    return state.get("errors", []) + [message]


def normalize_domain(domain: Any) -> str | None:
    if domain is None:
        return None

    text = str(domain).strip()

    if not text:
        return None

    if text in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[text]

    for key, value in DOMAIN_ALIASES.items():
        if key in text:
            return value

    if text in ROUTE_DOMAINS:
        return text

    return None


def score_domains(query: str, conditions: dict[str, Any]) -> dict[str, int]:
    query = query or ""
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query:
                scores[domain] += 1

    interest_domain = normalize_domain(conditions.get("interest_domain"))
    if interest_domain and interest_domain in scores:
        scores[interest_domain] += 3

    employment_status = str(conditions.get("employment_status") or "")
    if employment_status in {"취업준비생", "재직자", "구직자"}:
        scores["일자리"] += 2

    company_type = str(conditions.get("company_type") or "")
    if company_type:
        if any(word in company_type for word in ["중소기업", "중견기업", "대기업", "스타트업"]):
            scores["일자리"] += 1

    education_status = str(conditions.get("education_status") or "")
    major = str(conditions.get("major") or "")
    if education_status or major:
        scores["교육"] += 1

    for keyword in conditions.get("keywords") or []:
        keyword = str(keyword)
        for domain, domain_keywords in DOMAIN_KEYWORDS.items():
            if any(k in keyword or keyword in k for k in domain_keywords):
                scores[domain] += 1

    return scores


def route_policy_domain(
    query: str,
    conditions: dict[str, Any] | None = None,
) -> dict[str, str]:
    conditions = conditions or {}
    scores = score_domains(query, conditions)

    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]

    if best_score <= 0:
        return {
            "route": "전체",
            "reason": "질문에서 특정 정책 분야를 판단할 명확한 키워드가 없어 전체 검색으로 라우팅",
        }

    matched_keywords = [
        keyword
        for keyword in DOMAIN_KEYWORDS[best_domain]
        if keyword in query
    ]

    interest_domain = normalize_domain(conditions.get("interest_domain"))

    reasons = []

    if matched_keywords:
        reasons.append(
            f"사용자 질문에 {', '.join(matched_keywords[:3])} 키워드가 포함됨"
        )

    if interest_domain == best_domain:
        reasons.append(
            f"조건 추출 결과 interest_domain이 {best_domain}로 판단됨"
        )

    if not reasons:
        reasons.append(f"조건 정보와 질문 내용을 종합해 {best_domain} 분야가 가장 적합함")

    return {
        "route": best_domain,
        "reason": " / ".join(reasons),
    }

def route_source_category(
    query: str,
    route: str,
    conditions: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    conditions = conditions or {}

    text_parts = [
        query or "",
        str(conditions.get("interest_domain") or ""),
        " ".join(str(k) for k in conditions.get("keywords") or []),
    ]

    text = " ".join(text_parts).lower()

    scores = {
        "training": 0,
        "startup_notice": 0,
        "policy": 0,
    }

    for category, keywords in SOURCE_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                scores[category] += 1

    # route 기반 보정
    if route == "창업":
        scores["startup_notice"] += 2

    if route in {"주거", "금융", "복지문화", "참여권리"}:
        scores["policy"] += 2

    # 교육은 training/policy가 모두 가능하므로 키워드에 따라 판단
    if route == "교육":
        if any(word in text for word in ["훈련", "국비", "내일배움", "k-digital", "kdt", "과정", "부트캠프"]):
            scores["training"] += 3
        elif any(word in text for word in ["응시료", "자격증", "시험"]):
            scores["policy"] += 2

    # 일자리는 애매하므로 강하게 고정하지 않음
    if route == "일자리":
        if any(word in text for word in ["훈련", "교육과정", "직업훈련", "k-digital", "kdt"]):
            scores["training"] += 2
        elif any(word in text for word in ["면접수당", "취업지원금", "청년수당"]):
            scores["policy"] += 2

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    if best_score <= 0:
        return {
            "source_category": None,
            "reason": "데이터 출처 유형을 특정할 명확한 키워드가 없어 전체 source_category 검색",
        }

    return {
        "source_category": best_category,
        "reason": f"질문과 route를 기준으로 {best_category} 데이터를 우선 검색",
    }

def input_validator_node(state: GraphState) -> GraphState:
    query = (
        state.get("user_query")
        or state.get("query")
        or ""
    ).strip()

    warnings = state.get("warnings", [])
    errors = state.get("errors", [])

    if not query:
        return {
            **state,
            "user_query": query,
            "warnings": warnings,
            "errors": errors + ["사용자 질문이 비어 있습니다."],
            "answer": "질문이 비어 있습니다. 찾고 싶은 청년 정책 조건을 입력해 주세요.",
        }

    if len(query) < 5:
        warnings = warnings + ["질문이 짧아 검색 정확도가 낮을 수 있습니다."]

    return {
        **state,
        "user_query": query,
        "warnings": warnings,
        "errors": errors,
    }


def condition_extractor_node(state: GraphState) -> GraphState:
    query = state.get("user_query", "")

    if state.get("errors"):
        return state

    try:
        conditions = extract_conditions(query)
        return {
            **state,
            "user_conditions": conditions,
        }
    except Exception as e:
        fallback_conditions = {
            "age": None,
            "region": None,
            "income": None,
            "employment_status": None,
            "company_type": None,
            "education_status": None,
            "major": None,
            "interest_domain": None,
            "keywords": [],
            "region_code": None,
        }

        return {
            **state,
            "user_conditions": fallback_conditions,
            "warnings": _append_warning(
                state,
                f"조건 추출 중 오류가 발생하여 기본 조건으로 검색합니다: {repr(e)}",
            ),
        }


def router_node(state: GraphState) -> GraphState:
    if state.get("errors"):
        return state

    query = state.get("user_query", "")
    conditions = state.get("user_conditions") or {}

    route_result = route_policy_domain(query=query, conditions=conditions)
    route = route_result["route"]

    source_category_result = route_source_category(
        query=query,
        route=route,
        conditions=conditions,
    )
    source_category = source_category_result.get("source_category")

    filters = conditions_to_retriever_filters(conditions)

    if route in {"전체", "기타"}:
        filters.pop("domain", None)
    else:
        filters["domain"] = route

    if source_category:
        filters["source_category"] = source_category

    route_reason = route_result["reason"]

    if source_category:
        route_reason = (
            f"{route_reason} / "
            f"{source_category_result.get('reason')}"
        )

    return {
        **state,
        "route": route,
        "route_reason": route_reason,
        "filters": filters,
    }


def retriever_node(state: GraphState) -> GraphState:
    if state.get("errors"):
        return state

    query = state.get("user_query", "")
    conditions = state.get("user_conditions") or {}
    filters = state.get("filters") or {}

    retriever_query = build_query_from_conditions(query, conditions)

    try:
        top_k = int(state.get("top_k", 5))

        chunks = retrieve_policies(
            query=retriever_query,
            filters=filters,
            top_k=top_k,
        )

        warnings = state.get("warnings", [])

        if not chunks:
            warnings = warnings + ["검색 조건에 맞는 지원 정보 chunk를 찾지 못했습니다."]

        return {
            **state,
            "retriever_query": retriever_query,
            "retrieved_chunks": chunks,
            "warnings": warnings,
        }

    except Exception as e:
        return {
            **state,
            "retriever_query": retriever_query,
            "retrieved_chunks": [],
            "errors": _append_error(
                state,
                f"Retriever 실행 중 오류가 발생했습니다: {repr(e)}",
            ),
        }


def eligibility_checker_node(state: GraphState) -> GraphState:
    if state.get("errors"):
        return state

    conditions = state.get("user_conditions") or {}
    chunks = state.get("retrieved_chunks") or []

    try:
        eligibility_results = attach_eligibility_to_policies(
            user_conditions=conditions,
            policies=chunks,
        )

        return {
            **state,
            "eligibility_results": eligibility_results,
        }

    except Exception as e:
        return {
            **state,
            "eligibility_results": chunks,
            "warnings": _append_warning(
                state,
                f"자격 판단 중 오류가 발생하여 검색 결과만 사용합니다: {repr(e)}",
            ),
        }


def answer_generator_node(state: GraphState) -> GraphState:
    query = state.get("user_query", "")
    conditions = state.get("user_conditions") or {}
    policies = state.get("eligibility_results") or state.get("retrieved_chunks") or []

    if state.get("errors"):
        error_text = "\n".join(state.get("errors", []))
        return {
            **state,
            "answer": f"처리 중 오류가 발생했습니다.\n{error_text}",
        }

    try:
        use_llm = bool(state.get("use_llm", True))
        
        answer = generate_answer(
            query=query,
            user_conditions=conditions,
            policies=policies,
            use_llm = use_llm
        )

        return {
            **state,
            "answer": answer,
        }

    except Exception as e:
        fallback_answer = generate_answer(
            query=query,
            user_conditions=conditions,
            policies=policies,
            use_llm=False,
        )

        return {
            **state,
            "answer": fallback_answer,
            "warnings": _append_warning(
                state,
                f"LLM 답변 생성 중 오류가 발생하여 규칙 기반 답변으로 대체했습니다: {repr(e)}",
            ),
        }