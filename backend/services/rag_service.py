from typing import Any, Optional
from datetime import date
import re
from backend.db.vector_store import YouthPolicyVectorStore, search_policy_chunks


DEFAULT_TOP_K = 5
DEFAULT_FETCH_K = 80
MIN_SCORE_THRESHOLD = 0.45


def _safe_int(value: Any, default: int = -1) -> int:
    if value is None or value == "":
        return default

    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default

    try:
        return float(value)
    except Exception:
        return default


def _normalize_filters(filters: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    외부에서 들어온 필터를 Retriever 내부 표준 형태로 정리한다.

    허용 예시:
    {
        "age": 25,
        "user_age": 25,
        "region_code": "11000",
        "user_region_code": "11000",
        "domain": "교육",
        "source_category": "training"
    }
    """
    filters = filters or {}

    user_age = filters.get("user_age", filters.get("age"))
    user_region_code = filters.get("user_region_code", filters.get("region_code"))
    domain = filters.get("domain")
    source_category = filters.get("source_category")

    normalized = {}

    if user_age is not None:
        normalized["user_age"] = _safe_int(user_age)

    if user_region_code:
        normalized["user_region_code"] = str(user_region_code).strip()

    if domain:
        normalized["domain"] = str(domain).strip()

    if source_category:
        normalized["source_category"] = str(source_category).strip()

    return normalized


def _get_info_score(item: dict[str, Any]) -> int:
    metadata = item.get("metadata") or {}
    return _safe_int(metadata.get("info_score"), default=0)


def _get_needs_detail_check(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata") or {}
    return bool(metadata.get("needs_detail_check", True))


def _get_source_category(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}

    return str(
        item.get("source_category")
        or metadata.get("source_category")
        or ""
    ).strip()


def _deduplicate_by_policy_id(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    chunk 단위 검색 결과를 policy_id 기준으로 중복 제거한다.

    같은 policy_id가 여러 chunk에서 검색된 경우:
    - score가 높은 chunk 우선
    - info_score가 높은 chunk 우선
    - needs_detail_check=False인 chunk 우선
    """
    best_by_policy_id: dict[str, dict[str, Any]] = {}

    for item in results:
        metadata = item.get("metadata") or {}
        policy_id = str(
            item.get("policy_id")
            or item.get("item_id")
            or metadata.get("policy_id")
            or metadata.get("item_id")
            or ""
        )

        if not policy_id:
            continue

        if policy_id not in best_by_policy_id:
            best_by_policy_id[policy_id] = item
            continue

        old = best_by_policy_id[policy_id]

        old_rank = (
            _safe_float(old.get("score")),
            _get_info_score(old),
            not _get_needs_detail_check(old),
        )

        new_rank = (
            _safe_float(item.get("score")),
            _get_info_score(item),
            not _get_needs_detail_check(item),
        )

        if new_rank > old_rank:
            best_by_policy_id[policy_id] = item

    return list(best_by_policy_id.values())


def _domain_match(item: dict[str, Any], domain: str | None) -> bool:
    if not domain:
        return True

    metadata = item.get("metadata") or {}
    item_domain = str(
        item.get("domain")
        or metadata.get("domain")
        or ""
    )

    # 신규 통합 데이터는 education/startup 같은 영문 domain도 사용하므로 route와 매핑한다.
    domain_aliases = {
        "교육": {"교육", "education", "training"},
        "창업": {"창업", "startup", "startup_notice"},
        "일자리": {"일자리", "job", "employment", "work"},
        "주거": {"주거", "housing"},
        "금융": {"금융", "finance"},
        "복지문화": {"복지문화", "welfare", "culture"},
        "참여권리": {"참여권리", "participation", "rights"},
    }

    if domain in item_domain or item_domain in domain:
        return True

    expected_domains = domain_aliases.get(domain, set())
    return item_domain in expected_domains


def _source_category_match(
    item: dict[str, Any],
    source_category: str | None,
) -> bool:
    if not source_category:
        return True

    return _get_source_category(item) == source_category


def _filter_by_source_category(
    results: list[dict[str, Any]],
    source_category: str | None,
    min_results: int,
) -> list[dict[str, Any]]:
    """
    source_category가 지정되면 해당 카테고리 결과를 우선 사용한다.
    단, 결과가 너무 적으면 원본 결과를 유지하여 빈 응답을 방지한다.
    """
    if not source_category:
        return results

    matched = [
        item
        for item in results
        if _source_category_match(item, source_category)
    ]

    if len(matched) >= min_results:
        return matched
    return results


def _has_freshness_intent(query: str) -> bool:
    """
    사용자가 현재 신청 가능/최신/특정 연도 신청 가능 여부를 요구했는지 판단한다.

    True이면 expired 결과를 참고용으로도 섞지 않고 강하게 제외한다.
    예: "지금 신청 가능한", "2026년에 신청 가능한", "모집 중", "마감 전"
    """
    text = str(query or "").strip()

    if not text:
        return False

    freshness_keywords = [
        "지금 신청",
        "현재 신청",
        "신청 가능한",
        "신청가능한",
        "신청 가능",
        "모집 중",
        "모집중",
        "접수 중",
        "접수중",
        "마감 전",
        "마감전",
        "현재 모집",
        "현재 접수",
        "올해",
        "올해 신청",
        "최신",
    ]

    if any(keyword in text for keyword in freshness_keywords):
        return True

    # "2026년에 신청 가능한"처럼 현재 프로젝트 연도 또는 미래 연도를 명시한 경우
    current_year = date.today().year
    for match in re.finditer(r"(20\d{2})", text):
        year = int(match.group(1))
        if year >= current_year:
            return True

    return False

def _parse_date_text(value: str) -> date | None:
    """
    '2025년 6월 19일', '2025-06-19', '2025.06.19', '2025/06/19' 형태를 date로 변환한다.
    """
    text = str(value or "").strip()

    if not text:
        return None

    patterns = [
        r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        year, month, day = map(int, match.groups())

        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None

def _extract_application_end_date(text: str, metadata: dict[str, Any] | None = None) -> date | None:
    """
    공고 본문/metadata에서 신청기간 또는 접수기간의 종료일을 추출한다.
    """
    metadata = metadata or {}
    text = str(text or "")

    candidate_values = [
        metadata.get("application_end_date"),
        metadata.get("end_date"),
        metadata.get("deadline"),
        metadata.get("application_period"),
        metadata.get("application_period_text"),
        metadata.get("신청기간"),
        metadata.get("접수기간"),
        metadata.get("모집기간"),
    ]
    
    # 제목과 본문 전체도 검사 후보에 넣는다.
    # 제목에 들어간 '(3/21~4/9 11:00)' 같은 패턴을 잡기 위함.
    candidate_values.append(text)

    # 본문에서 신청기간/접수기간/모집기간 라인 추출
    line_patterns = [
        r"(?:신청기간|접수기간|모집기간|공고기간)\s*:\s*([^\n]+)",
        r"(?:신청기간|접수기간|모집기간|공고기간)\s+([^\n]+)",
    ]

    for pattern in line_patterns:
        match = re.search(pattern, text)
        if match:
            candidate_values.append(match.group(1))

    
    for value in candidate_values:
        value = str(value or "").strip()

        if not value:
            continue

        # 상시/수시/예산 소진 시까지는 마감일 판단 불가
        if any(word in value for word in ["상시", "수시", "예산 소진", "예산소진", "별도 공지"]):
            continue
        
        # 제목 등에 들어간 '3/21~4/9', '03.21~04.09' 같은 연도 없는 기간 처리
        # 같은 문자열 안에 '2025년' 같은 연도가 있으면 그 연도를 사용한다.
        year_match = re.search(r"(20\d{2})", value)
        inferred_year = int(year_match.group(1)) if year_match else date.today().year

        short_range_match = re.search(
            r"(\d{1,2})\s*[/\.]\s*(\d{1,2})\s*[~\-–]\s*(\d{1,2})\s*[/\.]\s*(\d{1,2})",
            value,
        )

        if short_range_match:
            _, _, end_month, end_day = map(int, short_range_match.groups())

            try:
                return date(inferred_year, end_month, end_day)
            except ValueError:
                pass

        # 기간 문자열 안에 날짜가 2개 있으면 마지막 날짜를 종료일로 본다.
        date_matches = []

        for pattern in [
            r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일",
            r"\d{4}[-./]\d{1,2}[-./]\d{1,2}",
        ]:
            date_matches.extend(re.findall(pattern, value))

        if date_matches:
            end_date = _parse_date_text(date_matches[-1])
            if end_date:
                return end_date

        parsed = _parse_date_text(value)
        if parsed:
            return parsed

    return None


def _get_deadline_rank(item: dict[str, Any]) -> int:
    """
    startup_notice 정렬용 마감 상태 rank.

    값이 클수록 우선순위가 높다.
    3: 아직 마감 전인 창업공고
    2: 마감일 확인 불가 창업공고
    1: 이미 마감된 창업공고
    0: 창업공고가 아님
    """
    metadata = item.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    source_category = (
        item.get("source_category")
        or metadata.get("source_category")
        or ""
    )

    if source_category != "startup_notice":
        return 0

    title = (
        item.get("title")
        or item.get("policy_name")
        or metadata.get("title")
        or metadata.get("policy_name")
        or ""
    )

    text = "\n".join(
        [
            str(title),
            str(item.get("text") or item.get("document") or item.get("content") or ""),
        ]
    )

    end_date = _extract_application_end_date(
        text=text,
        metadata=metadata,
    )

    if not end_date:
        return 2

    if end_date < date.today():
        return 1

    return 3

def _rerank_results(
    results: list[dict[str, Any]],
    preferred_domain: str | None = None,
    preferred_source_category: str | None = None,
    strict_freshness: bool = False,
) -> list[dict[str, Any]]:
    """
    최종 노출 순서 재정렬.

    기준:
    1. preferred_source_category 일치 우선
    2. preferred_domain 일치 우선
    3. startup_notice인 경우 마감 전/마감일 확인 불가 공고 우선
    4. score 높은 순
    5. info_score 높은 순
    6. needs_detail_check=False 우선
    """
    ranked = sorted(
        results,
        key=lambda item: (
            _source_category_match(item, preferred_source_category),
            _domain_match(item, preferred_domain),
            _get_deadline_rank(item),
            _safe_float(item.get("score")),
            _get_info_score(item),
            not _get_needs_detail_check(item),
        ),
        reverse=True,
    )

    # 마감 상태가 있는 데이터 유형은 이미 마감된 항목을 가능한 한 뒤로 보낸다.
    # 특히 사용자가 "지금 신청 가능한", "2026년에 신청 가능한"처럼 최신성을 명시한 경우에는
    # expired 결과를 참고용으로도 섞지 않고 강하게 제외한다.
    deadline_target_categories = {"startup_notice"}

    if preferred_source_category in deadline_target_categories:
        non_expired = [
            item
            for item in ranked
            if _get_deadline_rank(item) in {2, 3}
        ]

        if strict_freshness:
            return non_expired

        # 일반 검색에서는 결과가 너무 적어지는 것을 막기 위해
        # 살아있는 후보가 충분할 때만 expired를 제거한다.
        if len(non_expired) >= 3:
            return non_expired

    return ranked

def _filter_low_score(
    results: list[dict[str, Any]],
    min_score: float = MIN_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    return [
        item
        for item in results
        if _safe_float(item.get("score")) >= min_score
    ]


def _compact_result(item: dict[str, Any]) -> dict[str, Any]:
    """
    Retriever 최종 반환 구조.

    신규 통합 데이터에서는 item_id/title/source_category를 사용하고,
    기존 서비스 코드 호환을 위해 policy_id/policy_name alias도 유지한다.
    """
    metadata = item.get("metadata") or {}

    item_id = str(
        item.get("item_id")
        or metadata.get("item_id")
        or item.get("policy_id")
        or metadata.get("policy_id")
        or ""
    )

    title = str(
        item.get("title")
        or metadata.get("title")
        or item.get("policy_name")
        or metadata.get("policy_name")
        or ""
    )

    source_category = _get_source_category(item)

    domain = str(
        item.get("domain")
        or metadata.get("domain")
        or ""
    )
    
    deadline_rank = _get_deadline_rank(item)

    deadline_status = "unknown"
    application_end_date = None

    if source_category == "startup_notice":
        end_date = _extract_application_end_date(
            text="\n".join(
                [
                    str(title),
                    str(item.get("text") or item.get("document") or item.get("content") or ""),
                ]
            ),
            metadata=metadata,
        )

        application_end_date = end_date.isoformat() if end_date else None

        if deadline_rank == 3:
            deadline_status = "open"
        elif deadline_rank == 2:
            deadline_status = "unknown"
        elif deadline_rank == 1:
            deadline_status = "expired"

    compact_metadata = {
        **metadata,
        "item_id": item_id,
        "title": title,
        "policy_id": item_id,
        "policy_name": title,
        "source_category": source_category,
        "domain": domain,
        "source_url": metadata.get("source_url", item.get("source_url", "")),
        "application_url": metadata.get("application_url", item.get("application_url", "")),
        "age_min": _safe_int(metadata.get("age_min"), default=-1),
        "age_max": _safe_int(metadata.get("age_max"), default=-1),
        "region_code": metadata.get("region_code", ""),
        "info_score": _safe_int(metadata.get("info_score"), default=0),
        "needs_detail_check": metadata.get("needs_detail_check", True),
        "source": metadata.get("source", ""),
        "chunk_id": metadata.get("chunk_id", item.get("chunk_id", "")),
        "deadline_rank": deadline_rank,
        "deadline_status": deadline_status,
        "application_end_date": application_end_date,
        "is_expired": deadline_status == "expired",
    }

    return {
        "policy_id": item_id,
        "policy_name": title,
        "item_id": item_id,
        "title": title,
        "source_category": source_category,
        "domain": domain,
        "score": round(_safe_float(item.get("score")), 4),
        "text": item.get("text", ""),
        "metadata": compact_metadata,
        "deadline_rank": deadline_rank,
        "deadline_status": deadline_status,
        "application_end_date": application_end_date,
        "is_expired": deadline_status == "expired",
    }


def retrieve_policies(
    query: str,
    filters: Optional[dict[str, Any]] = None,
    top_k: int = DEFAULT_TOP_K,
    vector_store: Optional[YouthPolicyVectorStore] = None,
) -> list[dict[str, Any]]:
    """
    사용자 질문을 받아 관련 정책/창업공고/교육훈련 chunk를 검색한다.

    처리 흐름:
    1. 사용자 질문 semantic search
    2. 나이/지역 필터 적용
    3. source_category/domain 우선 적용
    4. 결과 부족 시 source_category/domain 제외 fallback
    5. item_id(policy_id alias) 기준 중복 제거
    6. score/info_score 기준 재정렬
    7. 낮은 score 제거
    """
    if not query or not query.strip():
        return []

    normalized_filters = _normalize_filters(filters)

    fetch_k = max(DEFAULT_FETCH_K, top_k * 15)
    source_category = normalized_filters.get("source_category")
    strict_freshness = _has_freshness_intent(query)

    # 1차 검색: 필터 포함
    raw_results = search_policy_chunks(
        query=query,
        top_k=fetch_k,
        fetch_k=fetch_k,
        filters=normalized_filters,
        vector_store=vector_store,
    )

    category_filtered_results = _filter_by_source_category(
        results=raw_results,
        source_category=source_category,
        min_results=min(top_k, 3),
    )

    deduped = _deduplicate_by_policy_id(category_filtered_results)
    reranked = _rerank_results(
        deduped,
        preferred_domain=normalized_filters.get("domain"),
        preferred_source_category=source_category,
        strict_freshness=strict_freshness,
    )
    filtered = _filter_low_score(reranked)

    # 도메인/source_category 필터 때문에 결과가 부족하면 둘 다 제거하고 fallback
    if len(filtered) < top_k and (normalized_filters.get("domain") or source_category):
        fallback_filters = {
            key: value
            for key, value in normalized_filters.items()
            if key not in {"domain", "source_category"}
        }

        fallback_results = search_policy_chunks(
            query=query,
            top_k=fetch_k,
            fetch_k=fetch_k,
            filters=fallback_filters,
            vector_store=vector_store,
        )

        merged = raw_results + fallback_results

        category_filtered_results = _filter_by_source_category(
            results=merged,
            source_category=source_category,
            min_results=min(top_k, 3),
        )

        deduped = _deduplicate_by_policy_id(category_filtered_results)
        reranked = _rerank_results(
            deduped,
            preferred_domain=normalized_filters.get("domain"),
            preferred_source_category=source_category,
            strict_freshness=strict_freshness,
        )
        filtered = _filter_low_score(reranked)

    return [_compact_result(item) for item in filtered[:top_k]]


def retrieve_policy_chunks_for_context(
    query: str,
    filters: Optional[dict[str, Any]] = None,
    top_k: int = DEFAULT_TOP_K,
    vector_store: Optional[YouthPolicyVectorStore] = None,
) -> str:
    """
    Answer Generator에 넣기 좋은 context 문자열 생성.
    다음 단계에서 LLM 프롬프트에 바로 넣을 수 있다.
    """
    results = retrieve_policies(
        query=query,
        filters=filters,
        top_k=top_k,
        vector_store=vector_store,
    )

    if not results:
        return ""

    context_blocks = []

    for idx, item in enumerate(results, start=1):
        metadata = item.get("metadata") or {}

        block = f"""
[추천 항목 {idx}]
policy_id: {item.get("policy_id", "")}
policy_name: {item.get("policy_name", "")}
item_id: {item.get("item_id", "")}
title: {item.get("title", "")}
source_category: {metadata.get("source_category", "")}
domain: {item.get("domain", "")}
score: {item.get("score", 0)}
source_url: {metadata.get("source_url", "")}
application_url: {metadata.get("application_url", "")}
age_min: {metadata.get("age_min", -1)}
age_max: {metadata.get("age_max", -1)}
region_code: {metadata.get("region_code", "")}
needs_detail_check: {metadata.get("needs_detail_check", True)}
text:
{item.get("text", "")}
""".strip()

        context_blocks.append(block)

    return "\n\n---\n\n".join(context_blocks)
