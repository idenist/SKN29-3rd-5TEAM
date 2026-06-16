import re
from typing import Any, TypedDict

from backend.services.condition_extractor import (
    extract_conditions,
    conditions_to_retriever_filters,
    build_query_from_conditions,
)
from backend.services.rag_service import retrieve_policies
from backend.services.policy_matcher import attach_eligibility_to_policies
from backend.services.answer_generator import generate_answer
from backend.services.external_search_service import (
    plan_official_external_search,
    search_official_external_sources,
)


class GraphState(TypedDict, total=False):
    # input
    user_query: str
    top_k: int
    use_llm: bool

    # intermediate
    user_conditions: dict[str, Any]
    route: str
    route_reason: str
    filters: dict[str, Any]
    retriever_query: str
    retrieved_chunks: list[dict[str, Any]]
    eligibility_results: list[dict[str, Any]]

    # ReAct / tool routing trace
    tool_trace: list[dict[str, Any]]
    internal_search_sufficient: bool
    sufficiency_reasons: list[str]
    next_action: str
    external_used: bool
    external_search_status: str
    external_search_targets: list[str]
    external_search_queries: list[str]
    external_search_guidance_answer: str
    allow_internal_fallback_after_external: bool

    # output
    answer: str
    warnings: list[str]
    errors: list[str]

    # neo4j
    graph_chunks:  list[dict[str, Any]]   # Neo4j 검색 결과
    graph_context: str                    # 프롬프트 결합용 Graph 컨텍스트



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


def _append_tool_trace(
    state: GraphState,
    step: str,
    action: str,
    observation: Any,
    next_action: str | None = None,
) -> list[dict[str, Any]]:
    """ReAct 설명을 위한 tool 실행 이력을 기록한다."""
    trace = list(state.get("tool_trace") or [])
    item: dict[str, Any] = {
        "step": step,
        "action": action,
        "observation": observation,
    }
    if next_action:
        item["next_action"] = next_action
    trace.append(item)
    return trace


def _get_nested_value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    metadata = item.get("metadata") or {}
    if key in item:
        return item.get(key)
    if isinstance(metadata, dict) and key in metadata:
        return metadata.get(key)
    return default


def _safe_bool_for_trace(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "y"}


def _has_source_url(item: dict[str, Any]) -> bool:
    source_url = _get_nested_value(item, "source_url", "")
    return bool(str(source_url or "").strip())


def _is_expired_item(item: dict[str, Any]) -> bool:
    is_expired = _get_nested_value(item, "is_expired", False)
    deadline_status = str(_get_nested_value(item, "deadline_status", "") or "").strip()
    return _safe_bool_for_trace(is_expired) or deadline_status == "expired"


def _has_freshness_intent(query: str) -> bool:
    """사용자가 현재 신청 가능성/현재 지원 여부를 묻는지 판단한다."""
    text = str(query or "")
    keywords = [
        "지금", "현재", "신청 가능한", "신청가능한", "모집 중", "모집중",
        "접수 중", "접수중", "마감 전", "마감전", "올해", "2026",
        "받을 수", "지원해주는", "지원해 주는", "있어?", "있나요", "추천", "기회",
    ]
    return any(keyword in text for keyword in keywords)


_GENERIC_QUERY_TERMS = {
    "청년", "정책", "사업", "지원", "지원사업", "지원금", "정보", "추천", "관련",
    "받을", "있는", "있어", "있나요", "알려줘", "해줘", "가능한", "현재", "지금",
    "올해", "대상", "프로그램", "과정", "분야", "확인", "제공", "한눈", "기회",
}

_PARTICLE_SUFFIXES = (
    "에서는", "에게는", "으로", "에서", "에게", "에는", "까지", "부터",
    "은", "는", "이", "가", "을", "를", "의", "에", "도", "만", "로",
)


def _normalize_query_token(token: str) -> str:
    token = token.strip().lower()
    for suffix in _PARTICLE_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            token = token[: -len(suffix)]
            break
    return token


def _extract_specific_keywords(query: str) -> list[str]:
    """질문에서 일반적인 표현을 제거하고 핵심 키워드만 뽑는다."""
    raw_tokens = re.findall(r"[가-힣A-Za-z0-9+#.]{2,}", str(query or ""))
    keywords: list[str] = []
    for token in raw_tokens:
        normalized = _normalize_query_token(token)
        if not normalized or normalized in _GENERIC_QUERY_TERMS:
            continue
        if normalized.isdigit() and len(normalized) < 4:
            continue
        if normalized in {"2025", "2026"}:
            continue
        keywords.append(normalized)
    return list(dict.fromkeys(keywords))[:8]


def _item_text_for_relevance(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    parts = [
        item.get("policy_name"), item.get("title"), item.get("name"), item.get("text"), item.get("content"),
        metadata.get("policy_name"), metadata.get("title"), metadata.get("name"), metadata.get("text"), metadata.get("content"),
        metadata.get("support_content"), metadata.get("policy_summary"), metadata.get("source_category"),
        item.get("source_category"), item.get("domain"), metadata.get("domain"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _keyword_overlap_stats(query: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    keywords = _extract_specific_keywords(query)
    corpus = "\n".join(_item_text_for_relevance(item) for item in chunks)
    hit_keywords = [keyword for keyword in keywords if keyword and keyword in corpus]
    ratio = (len(hit_keywords) / len(keywords)) if keywords else 1.0
    return {
        "specific_keywords": keywords,
        "hit_keywords": hit_keywords,
        "hit_count": len(hit_keywords),
        "keyword_count": len(keywords),
        "hit_ratio": round(ratio, 4),
    }



def _direct_intent_required_groups(query: str) -> list[list[str]]:
    """질문이 특정 지원 유형을 직접 묻는 경우 반드시 확인되어야 하는 키워드 그룹."""
    text = str(query or "").lower()
    groups: list[list[str]] = []

    if any(word in text for word in ["식품", "식비", "먹거리", "도시락"]):
        groups.append(["식품", "식비", "먹거리", "식사", "도시락", "급식", "푸드", "양곡", "식생활", "식료품", "식품비"])
        groups.append(["청년", "취약", "저소득", "취약계층", "기초생활", "차상위"])

    if "교통비" in text or "교통" in text:
        groups.append(["교통비", "교통", "대중교통"])
        groups.append(["청년", "중소기업", "근로자", "재직", "산업단지"])

    if "임차료" in text or "임대료" in text:
        groups.append(["임차료", "임대료", "월세", "사무실", "사업장", "공간", "입주"])
        groups.append(["창업", "창업자", "창업기업", "스타트업"])

    if "행사" in text or "한눈" in text:
        groups.append(["행사", "박람회", "설명회", "페어", "컨퍼런스", "한눈"])
        groups.append(["고용", "일자리", "취업", "정책"])

    if "일경험" in text or ("직무" in text and "경험" in text):
        groups.append(["일경험", "직무", "인턴", "미래내일"])
        groups.append(["청년", "고용24", "고용노동부"])

    if "공공기관" in text and "인턴" in text:
        groups.append(["공공기관", "행정", "공공"])
        groups.append(["인턴", "일경험", "체험"])

    if ("장기" in text and "재직" in text) or "공제" in text:
        groups.append(["공제", "내일채움", "재직", "장기재직", "장기"])
        groups.append(["중소기업", "청년", "근로자", "재직자"])

    return groups


def _direct_intent_match_stats(query: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    groups = _direct_intent_required_groups(query)
    corpus = "\n".join(_item_text_for_relevance(item) for item in chunks)
    group_results: list[dict[str, Any]] = []
    for group in groups:
        hits = [term for term in group if term.lower() in corpus]
        group_results.append({"group": group, "hits": hits})
    missing = [row["group"] for row in group_results if not row["hits"]]
    return {
        "required_groups": groups,
        "group_results": group_results,
        "required_group_count": len(groups),
        "missing_group_count": len(missing),
        "missing_groups": missing[:3],
        "all_groups_satisfied": bool(groups) and not missing,
    }


def _is_external_policy(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata") or {}
    return bool(
        item.get("needs_detail_check")
        or metadata.get("external_search")
        or metadata.get("source") == "official_external_search"
    )


def _build_external_results_answer(query: str, policies: list[dict[str, Any]]) -> str:
    """외부 검색 결과는 LLM 과장 없이 공식 출처 확인 후보 톤으로 답변한다."""
    lines = [
        f"공식 외부 출처 검색 기준으로 '{query}'와 관련된 확인 후보를 찾았습니다.",
        "아래 결과는 검색 결과의 제목/요약/출처 URL을 근거로 정리한 것이므로, 실제 신청 가능 여부·지역·자부담금·마감일은 원문에서 확인해야 합니다.",
        "",
    ]

    for idx, item in enumerate(policies[:3], start=1):
        metadata = item.get("metadata") or {}
        title = _get_item_title(item) or "공식 출처 검색 결과"
        source_category = str(_get_nested_value(item, "source_category", "") or "")
        source_url = str(_get_nested_value(item, "source_url", "") or metadata.get("application_url") or "")
        official_source = str(metadata.get("official_source") or "공식 출처")
        snippet = str(item.get("content") or item.get("summary") or item.get("text") or "").strip()
        snippet = re.sub(r"\s+", " ", snippet)
        if len(snippet) > 240:
            snippet = snippet[:240].rstrip() + "..."
        matched = metadata.get("external_matched_terms") or []
        matched_text = ", ".join(str(term) for term in matched[:6]) if matched else "질문 키워드 일부"

        lines.append(f"### {idx}. {title}")
        if source_category:
            category_label = {
                "training": "교육훈련 과정",
                "policy": "청년정책",
                "startup_notice": "창업지원 공고",
            }.get(source_category, source_category)
            lines.append(f"- 항목 유형: {category_label}")
        lines.append(f"- 공식 출처: {official_source}")
        lines.append(f"- 관련 근거: 검색 결과에서 {matched_text} 키워드가 확인되었습니다.")
        if snippet:
            lines.append(f"- 요약: {snippet}")
        if source_url:
            lines.append(f"- 출처 URL: {source_url}")
        lines.append("- 확인 필요: 신청기간, 대상 연령, 지역 제한, 세부 자격, 실제 접수 가능 여부")
        lines.append("")

    lines.append("내부 DB 결과가 질문 핵심어와 충분히 맞지 않아, 공식 도메인 제한 외부 검색 결과를 우선 사용했습니다.")
    return "\n".join(lines).strip()

def _get_source_category(item: dict[str, Any]) -> str:
    return str(_get_nested_value(item, "source_category", "") or "").strip()


def _get_item_title(item: dict[str, Any]) -> str:
    return str(
        _get_nested_value(item, "policy_name", "")
        or _get_nested_value(item, "title", "")
        or _get_nested_value(item, "name", "")
        or ""
    ).strip()


def _has_old_year_in_title(item: dict[str, Any], min_year: int = 2010, max_year: int = 2024) -> bool:
    title = _get_item_title(item)
    years = [int(match) for match in re.findall(r"\b(20\d{2})\b", title)]
    return any(min_year <= year <= max_year for year in years)


def _is_route_source_mismatch(item: dict[str, Any], route: str, expected_source_category: str, query: str) -> bool:
    actual = _get_source_category(item)
    query_text = str(query or "")

    if expected_source_category and actual and actual != expected_source_category:
        return True

    if route in {"주거", "금융", "복지문화", "참여권리"} and actual == "startup_notice":
        return True

    if route == "일자리" and actual == "startup_notice" and not any(word in query_text for word in ["창업", "스타트업", "사업화"]):
        return True

    return False


def _candidate_filter_reasons(
    item: dict[str, Any],
    route: str,
    expected_source_category: str,
    query: str,
    freshness_intent: bool,
) -> list[str]:
    reasons: list[str] = []
    title = _get_item_title(item)

    if _is_route_source_mismatch(item, route, expected_source_category, query):
        reasons.append(f"route/source_category 불일치 후보 제외: {title}")

    if freshness_intent and _is_expired_item(item):
        reasons.append(f"현재성 질문에서 마감 후보 제외: {title}")

    if freshness_intent and _has_old_year_in_title(item):
        reasons.append(f"현재성 질문에서 오래된 연도 후보 제외: {title}")

    return reasons


def _filter_retrieved_candidates(
    chunks: list[dict[str, Any]],
    route: str,
    expected_source_category: str,
    query: str,
    freshness_intent: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    filtered: list[dict[str, Any]] = []
    removed_reasons: list[str] = []

    for item in chunks:
        reasons = _candidate_filter_reasons(
            item=item,
            route=route,
            expected_source_category=expected_source_category,
            query=query,
            freshness_intent=freshness_intent,
        )
        if reasons:
            removed_reasons.extend(reasons[:2])
            continue
        filtered.append(item)

    return filtered, removed_reasons[:5]


def _filter_answer_candidates(policies: list[dict[str, Any]], freshness_intent: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """자격 판단 이후 답변에 넘기기 부적합한 후보를 제거한다."""
    filtered: list[dict[str, Any]] = []
    removed: list[str] = []

    for policy in policies:
        title = _get_item_title(policy)
        eligibility = str(policy.get("eligibility") or "")
        if _is_expired_item(policy):
            removed.append(f"마감 후보 답변 제외: {title}")
            continue
        if freshness_intent and _has_old_year_in_title(policy):
            removed.append(f"오래된 연도 후보 답변 제외: {title}")
            continue
        if freshness_intent and eligibility == "가능성 낮음":
            removed.append(f"가능성 낮음 후보 답변 제외: {title}")
            continue
        filtered.append(policy)

    return filtered, removed[:5]


def _build_external_search_guidance_answer(
    query: str,
    route: str | None,
    plan: dict[str, Any],
    reasons: list[str],
) -> str:
    """실제 외부 API 호출 전 단계에서 사용자에게 보여줄 공식 출처 확인 안내문을 만든다."""
    target_names = plan.get("target_names") or []
    queries = plan.get("queries") or []
    targets = plan.get("targets") or []

    target_text = ", ".join(str(name) for name in target_names) or "공식 출처"
    route_text = str(route or "관련")

    reason_text = ""
    if reasons:
        reason_text = "\n" + "\n".join(f"- {reason}" for reason in reasons[:5])

    query_lines = "\n" + "\n".join(f"- {q}" for q in (queries or [query])[:5])

    target_lines = ""
    if targets:
        rows = []
        for target in targets:
            name = str(target.get("name") or "공식 출처")
            kind = str(target.get("kind") or "관련 정보")
            official_url = str(target.get("official_url") or "")
            rows.append(f"- {name} ({kind}): {official_url}" if official_url else f"- {name} ({kind})")
        target_lines = "\n" + "\n".join(rows)

    return (
        f"내부 데이터에서 출처와 관련성이 충분히 확인된 '{query}' 관련 지원 정보를 찾지 못했습니다.\n\n"
        f"이 질문은 {route_text} 분야에 해당하므로 {target_text} 공식 출처 확인이 필요합니다. "
        "현재 버전에서는 실제 외부 API 호출은 아직 수행하지 않지만, "
        "부정확한 내부 검색 결과를 추천하지 않고 공식 출처 확인 대상으로 분기했습니다."
        f"{reason_text}\n\n"
        "공식 사이트에서 아래 검색어로 다시 확인해 보세요:"
        f"{query_lines}\n\n"
        "확인 대상 공식 출처:"
        f"{target_lines}"
    )


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
        "tool_trace": _append_tool_trace(
            state,
            step="router",
            action="select_domain_and_source_category",
            observation={
                "route": route,
                "source_category": source_category,
                "filters": filters,
                "reason": route_reason,
            },
            next_action="internal_retriever",
        ),
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

        expired_count = sum(1 for item in chunks if _is_expired_item(item))
        source_count = sum(1 for item in chunks if _has_source_url(item))

        return {
            **state,
            "retriever_query": retriever_query,
            "retrieved_chunks": chunks,
            "warnings": warnings,
            "tool_trace": _append_tool_trace(
                state,
                step="internal_retriever",
                action="search_vector_db",
                observation={
                    "query": retriever_query,
                    "filters": filters,
                    "total": len(chunks),
                    "expired_count": expired_count,
                    "source_count": source_count,
                },
                next_action="result_sufficiency_checker",
            ),
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



def result_sufficiency_checker_node(state: GraphState) -> GraphState:
    """
    내부 Vector DB 검색 결과가 답변 생성에 충분한지 판단한다.

    결과 수만 보지 않고, 마감 여부·출처 URL·최신성 의도·질문 핵심 키워드 일치도를 함께 판단한다.
    """
    if state.get("errors"):
        return state

    raw_chunks = state.get("retrieved_chunks") or []
    query = state.get("user_query", "")
    route = str(state.get("route") or "")
    filters = state.get("filters") or {}
    expected_source_category = str(filters.get("source_category") or "")

    freshness_intent = _has_freshness_intent(query)
    candidate_chunks, removed_reasons = _filter_retrieved_candidates(
        chunks=raw_chunks,
        route=route,
        expected_source_category=expected_source_category,
        query=query,
        freshness_intent=freshness_intent,
    )

    total = len(candidate_chunks)
    raw_total = len(raw_chunks)
    expired_count = sum(1 for item in candidate_chunks if _is_expired_item(item))
    open_count = sum(
        1
        for item in candidate_chunks
        if str(_get_nested_value(item, "deadline_status", "") or "").strip() == "open"
    )
    source_count = sum(1 for item in candidate_chunks if _has_source_url(item))
    overlap = _keyword_overlap_stats(query, candidate_chunks)
    direct_intent = _direct_intent_match_stats(query, candidate_chunks)

    sufficient = True
    reasons: list[str] = []

    if raw_total > 0 and total == 0:
        sufficient = False
        reasons.append("검색 후보가 있었지만 route/source_category, 마감 여부, 오래된 연도 조건으로 모두 제외되었습니다.")

    if total == 0:
        sufficient = False
        reasons.append("내부 Vector DB 검색 결과가 없습니다.")

    if total > 0 and expired_count == total:
        sufficient = False
        reasons.append("검색 결과가 모두 마감된 항목입니다.")

    if total > 0 and source_count == 0:
        sufficient = False
        reasons.append("출처 URL이 포함된 검색 결과가 없습니다.")

    if total > 0 and overlap["keyword_count"] >= 2 and overlap["hit_count"] == 0:
        sufficient = False
        reasons.append("질문 핵심 키워드가 검색 결과 제목/본문에서 확인되지 않습니다.")
    elif total > 0 and overlap["keyword_count"] >= 4 and overlap["hit_ratio"] < 0.25:
        sufficient = False
        reasons.append("질문 핵심 키워드와 검색 결과의 일치도가 낮습니다.")

    if (
        total > 0
        and direct_intent["required_group_count"] > 0
        and direct_intent["missing_group_count"] > 0
    ):
        sufficient = False
        reasons.append("질문이 특정 지원 유형을 직접 묻고 있으나, 내부 검색 결과에서 해당 핵심 유형 키워드가 충분히 확인되지 않습니다.")

    blocking_reasons = [
        reason
        for reason in reasons
        if "핵심 키워드" in reason or "모두 제외" in reason or "특정 지원 유형" in reason
    ]
    allow_internal_fallback_after_external = bool(total > 0 and blocking_reasons)

    if freshness_intent and open_count >= 1 and source_count >= 1 and not blocking_reasons:
        sufficient = True
        reasons = []

    if (
        not freshness_intent
        and total > 0
        and source_count > 0
        and expired_count < total
        and not blocking_reasons
    ):
        sufficient = True
        reasons = []

    if removed_reasons:
        reasons.extend(reason for reason in removed_reasons if reason not in reasons)

    next_action = "answer_generation" if sufficient else "external_search"

    return {
        **state,
        "retrieved_chunks": candidate_chunks,
        "internal_search_sufficient": sufficient,
        "sufficiency_reasons": reasons,
        "next_action": next_action,
        "allow_internal_fallback_after_external": allow_internal_fallback_after_external,
        "tool_trace": _append_tool_trace(
            state,
            step="result_sufficiency_checker",
            action="check_internal_search_results",
            observation={
                "raw_total": raw_total,
                "total": total,
                "expired_count": expired_count,
                "open_count": open_count,
                "source_count": source_count,
                "freshness_intent": freshness_intent,
                "keyword_overlap": overlap,
                "direct_intent_match": direct_intent,
                "removed_candidate_reasons": removed_reasons,
                "sufficient": sufficient,
                "reasons": reasons,
            },
            next_action=next_action,
        ),
    }


def external_search_placeholder_node(state: GraphState) -> GraphState:
    """
    외부 공식 출처 fallback 노드.

    내부 검색 결과가 부족할 때 공식 도메인으로 제한된 외부 웹 검색을 실제로 시도한다.
    검색 결과가 있으면 외부 결과를 retrieved_chunks에 넣어 답변 생성에 사용하고,
    결과가 없으면 기존처럼 공식 출처 확인 안내문으로 fallback한다.
    """
    if state.get("errors"):
        return state

    reasons = state.get("sufficiency_reasons") or []
    query = state.get("user_query", "")
    route = state.get("route")
    conditions = state.get("user_conditions") or {}
    filters = state.get("filters") or {}

    search_result = search_official_external_sources(
        query=query,
        user_conditions=conditions,
        route=route,
        filters=filters,
        sufficiency_reasons=reasons,
        max_results=3,
    )

    external_results = search_result.get("results") or []
    guidance_answer = _build_external_search_guidance_answer(
        query=query,
        route=route,
        plan=search_result,
        reasons=reasons,
    )

    if external_results:
        warning_message = (
            "내부 데이터 검색 결과가 충분하지 않아 공식 외부 출처 검색 결과를 사용했습니다. "
            "외부 검색 결과는 원문에서 세부 조건 확인이 필요합니다."
        )
        next_action = "eligibility_checker"
        return {
            **state,
            "external_used": True,
            "external_search_status": search_result.get("status", "executed"),
            "external_search_targets": search_result.get("target_names", []),
            "external_search_queries": search_result.get("queries", []),
            "external_search_guidance_answer": guidance_answer,
            "retrieved_chunks": external_results,
            "eligibility_results": [],
            "warnings": state.get("warnings", []) + [warning_message],
            "tool_trace": _append_tool_trace(
                state,
                step="external_search",
                action="search_official_sources",
                observation={
                    "status": search_result.get("status", "executed"),
                    "backend": search_result.get("backend", "unknown"),
                    "target_names": search_result.get("target_names", []),
                    "queries": search_result.get("queries", []),
                    "result_count": len(external_results),
                    "result_titles": [item.get("policy_name") for item in external_results[:3]],
                    "post_filter": search_result.get("post_filter", {}),
                    "errors": search_result.get("errors", []),
                },
                next_action=next_action,
            ),
        }

    if state.get("allow_internal_fallback_after_external") and state.get("retrieved_chunks"):
        warning_message = (
            "내부 검색 결과의 직접 관련성이 낮아 공식 외부 출처 검색을 시도했지만, "
            "사용 가능한 외부 결과를 찾지 못해 내부 후보를 보조적으로 사용합니다."
        )
        return {
            **state,
            "external_used": False,
            "external_search_status": "attempted_no_result_keep_internal",
            "external_search_targets": search_result.get("target_names", []),
            "external_search_queries": search_result.get("queries", []),
            "external_search_guidance_answer": guidance_answer,
            "eligibility_results": [],
            "warnings": state.get("warnings", []) + [warning_message],
            "tool_trace": _append_tool_trace(
                state,
                step="external_search",
                action="search_official_sources",
                observation={
                    "status": "attempted_no_result_keep_internal",
                    "backend": search_result.get("backend", "none"),
                    "target_names": search_result.get("target_names", []),
                    "queries": search_result.get("queries", []),
                    "result_count": 0,
                    "post_filter": search_result.get("post_filter", {}),
                    "errors": search_result.get("errors", []),
                    "message": "외부 검색 결과가 없어 내부 후보를 보조적으로 유지",
                },
                next_action="eligibility_checker",
            ),
        }

    warning_message = (
        "내부 데이터 검색 결과가 충분하지 않아 외부 공식 출처 검색이 필요합니다. "
        "공식 도메인 제한 외부 검색에서도 사용 가능한 결과를 찾지 못해 확인 안내로 대체합니다."
    )

    return {
        **state,
        "external_used": False,
        "external_search_status": search_result.get("status", "planned_not_executed"),
        "external_search_targets": search_result.get("target_names", []),
        "external_search_queries": search_result.get("queries", []),
        "external_search_guidance_answer": guidance_answer,
        "retrieved_chunks": [],
        "eligibility_results": [],
        "warnings": state.get("warnings", []) + [warning_message],
        "tool_trace": _append_tool_trace(
            state,
            step="external_search",
            action="search_official_sources",
            observation={
                "status": search_result.get("status", "planned_not_executed"),
                "backend": search_result.get("backend", "none"),
                "target_names": search_result.get("target_names", []),
                "queries": search_result.get("queries", []),
                "result_count": 0,
                "errors": search_result.get("errors", []),
                "message": search_result.get("message"),
            },
            next_action="eligibility_checker",
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
    freshness_intent = _has_freshness_intent(query)

    if state.get("errors"):
        error_text = "\n".join(state.get("errors", []))
        return {
            **state,
            "answer": f"처리 중 오류가 발생했습니다.\n{error_text}",
        }

    if (
        not policies
        and state.get("next_action") == "external_search"
        and state.get("external_search_status") == "planned_not_executed"
    ):
        guidance_answer = state.get("external_search_guidance_answer")
        if guidance_answer:
            return {
                **state,
                "answer": guidance_answer,
            }

    if policies and state.get("external_used") and any(_is_external_policy(policy) for policy in policies):
        external_policies = [policy for policy in policies if _is_external_policy(policy)]
        return {
            **state,
            "eligibility_results": external_policies,
            "answer": _build_external_results_answer(query=query, policies=external_policies),
        }

    filtered_policies, removed_answer_reasons = _filter_answer_candidates(policies, freshness_intent=freshness_intent)
    if policies and not filtered_policies:
        reasons = state.get("sufficiency_reasons") or []
        reasons = reasons + ["자격 판단 이후 답변에 사용할 수 있는 유효 후보가 없습니다."] + removed_answer_reasons
        plan = plan_official_external_search(
            query=query,
            user_conditions=conditions,
            route=state.get("route"),
            filters=state.get("filters") or {},
            sufficiency_reasons=reasons,
        )
        guidance_answer = _build_external_search_guidance_answer(
            query=query,
            route=state.get("route"),
            plan=plan,
            reasons=reasons,
        )
        return {
            **state,
            "eligibility_results": [],
            "retrieved_chunks": [],
            "internal_search_sufficient": False,
            "sufficiency_reasons": reasons,
            "next_action": "external_search",
            "external_used": False,
            "external_search_status": plan.get("status", "planned_not_executed"),
            "external_search_targets": plan.get("target_names", []),
            "external_search_queries": plan.get("queries", []),
            "external_search_guidance_answer": guidance_answer,
            "warnings": state.get("warnings", []) + ["답변 후보가 마감/오래된/가능성 낮음 조건으로 제외되어 공식 출처 확인 안내로 전환했습니다."],
            "tool_trace": _append_tool_trace(
                state,
                step="answer_candidate_filter",
                action="filter_invalid_answer_candidates",
                observation={"removed_reasons": removed_answer_reasons},
                next_action="external_search_guidance_answer",
            ),
            "answer": guidance_answer,
        }

    policies = filtered_policies

    try:
        use_llm = bool(state.get("use_llm", True))

        answer = generate_answer(
            query=query,
            user_conditions=conditions,
            policies=policies,
            use_llm=use_llm,
            graph_context=state.get("graph_context", ""),  # ← 추가
            route=state.get("route", ""),   # ← 추가
        )

        return {
            **state,
            "eligibility_results": policies,
            "answer": answer,
        }

    except Exception as e:
        fallback_answer = generate_answer(
            query=query,
            user_conditions=conditions,
            policies=policies,
            use_llm=False,
            graph_context=state.get("graph_context", ""),  # ← 추가
            route=state.get("route", ""),   # ← 추가

        )

        return {
            **state,
            "eligibility_results": policies,
            "answer": fallback_answer,
            "warnings": _append_warning(
                state,
                f"LLM 답변 생성 중 오류가 발생하여 규칙 기반 답변으로 대체했습니다: {repr(e)}",
            ),
        }
