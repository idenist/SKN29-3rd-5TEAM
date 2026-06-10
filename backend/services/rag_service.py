from typing import Any, Optional

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
        "domain": "일자리"
    }
    """
    filters = filters or {}

    user_age = filters.get("user_age", filters.get("age"))
    user_region_code = filters.get("user_region_code", filters.get("region_code"))
    domain = filters.get("domain")

    normalized = {}

    if user_age is not None:
        normalized["user_age"] = _safe_int(user_age)

    if user_region_code:
        normalized["user_region_code"] = str(user_region_code).strip()

    if domain:
        normalized["domain"] = str(domain).strip()

    return normalized


def _get_info_score(item: dict[str, Any]) -> int:
    metadata = item.get("metadata") or {}
    return _safe_int(metadata.get("info_score"), default=0)


def _get_needs_detail_check(item: dict[str, Any]) -> bool:
    metadata = item.get("metadata") or {}
    return bool(metadata.get("needs_detail_check", True))


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
        policy_id = str(item.get("policy_id", ""))

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

    item_domain = str(item.get("domain", ""))

    return domain in item_domain or item_domain in domain


def _rerank_results(
    results: list[dict[str, Any]],
    preferred_domain: str | None = None,
) -> list[dict[str, Any]]:
    """
    최종 노출 순서 재정렬.

    기준:
    1. preferred_domain 일치 우선
    2. score 높은 순
    3. info_score 높은 순
    4. needs_detail_check=False 우선
    """
    return sorted(
        results,
        key=lambda item: (
            _domain_match(item, preferred_domain),
            _safe_float(item.get("score")),
            _get_info_score(item),
            not _get_needs_detail_check(item),
        ),
        reverse=True,
    )


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
    """
    metadata = item.get("metadata") or {}

    return {
        "policy_id": item.get("policy_id", ""),
        "policy_name": item.get("policy_name", ""),
        "domain": item.get("domain", ""),
        "score": round(_safe_float(item.get("score")), 4),
        "text": item.get("text", ""),
        "metadata": {
            "source_url": metadata.get("source_url", item.get("source_url", "")),
            "age_min": _safe_int(metadata.get("age_min"), default=-1),
            "age_max": _safe_int(metadata.get("age_max"), default=-1),
            "region_code": metadata.get("region_code", ""),
            "info_score": _safe_int(metadata.get("info_score"), default=0),
            "needs_detail_check": metadata.get("needs_detail_check", True),
            "source": metadata.get("source", ""),
            "chunk_id": item.get("chunk_id", ""),
        },
    }


def retrieve_policies(
    query: str,
    filters: Optional[dict[str, Any]] = None,
    top_k: int = DEFAULT_TOP_K,
    vector_store: Optional[YouthPolicyVectorStore] = None,
) -> list[dict[str, Any]]:
    """
    사용자 질문을 받아 관련 정책 chunk를 검색한다.

    처리 흐름:
    1. 사용자 질문 semantic search
    2. 나이/지역 필터 적용
    3. domain 필터가 있으면 우선 적용
    4. 결과 부족 시 domain 제외 fallback
    5. policy_id 기준 중복 제거
    6. score/info_score 기준 재정렬
    7. 낮은 score 제거
    """
    if not query or not query.strip():
        return []

    normalized_filters = _normalize_filters(filters)

    fetch_k = max(DEFAULT_FETCH_K, top_k * 15)

    # 1차 검색: 필터 포함
    raw_results = search_policy_chunks(
        query=query,
        top_k=fetch_k,
        fetch_k=fetch_k,
        filters=normalized_filters,
        vector_store=vector_store,
    )

    deduped = _deduplicate_by_policy_id(raw_results)
    reranked = _rerank_results(
        deduped,
        preferred_domain=normalized_filters.get("domain"),
    )
    filtered = _filter_low_score(reranked)
    
    # 도메인 필터 때문에 결과가 부족하면 domain만 제거하고 fallback
    if len(filtered) < top_k and normalized_filters.get("domain"):
        fallback_filters = {
            key: value
            for key, value in normalized_filters.items()
            if key != "domain"
        }

        fallback_results = search_policy_chunks(
            query=query,
            top_k=fetch_k,
            fetch_k=fetch_k,
            filters=fallback_filters,
            vector_store=vector_store,
        )

        merged = raw_results + fallback_results
        deduped = _deduplicate_by_policy_id(merged)
        reranked = _rerank_results(
            deduped,
            preferred_domain=normalized_filters.get("domain"),
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
[정책 {idx}]
policy_id: {item.get("policy_id", "")}
policy_name: {item.get("policy_name", "")}
domain: {item.get("domain", "")}
score: {item.get("score", 0)}
source_url: {metadata.get("source_url", "")}
age_min: {metadata.get("age_min", -1)}
age_max: {metadata.get("age_max", -1)}
region_code: {metadata.get("region_code", "")}
needs_detail_check: {metadata.get("needs_detail_check", True)}
text:
{item.get("text", "")}
""".strip()

        context_blocks.append(block)

    return "\n\n---\n\n".join(context_blocks)