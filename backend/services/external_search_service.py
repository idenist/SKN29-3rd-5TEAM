"""
공식 외부 출처 fallback 설계 모듈.

현재 버전은 실제 외부 API를 호출하지 않고, 내부 검색 결과가 부족할 때
어떤 공식 출처를 조회해야 하는지 계획(plan)을 생성한다.
이후 K-Startup/온통청년/고용24 API 또는 MCP 도구 연동 시 이 파일의
search_* 함수를 실제 호출 구현으로 교체하면 된다.
"""

from __future__ import annotations

from typing import Any


OFFICIAL_SOURCE_MAP: dict[str, dict[str, str]] = {
    "startup_notice": {
        "name": "K-Startup",
        "kind": "창업지원 공고",
        "official_url": "https://www.k-startup.go.kr",
    },
    "policy": {
        "name": "온통청년",
        "kind": "청년정책",
        "official_url": "https://www.youthcenter.go.kr",
    },
    "training": {
        "name": "고용24/HRD-Net",
        "kind": "교육훈련 과정",
        "official_url": "https://www.work24.go.kr",
    },
}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def select_official_targets(source_category: str | None, route: str | None, query: str) -> list[dict[str, str]]:
    """source_category/route/query를 기준으로 조회해야 할 공식 출처를 선택한다."""
    source_category = _safe_str(source_category)
    route = _safe_str(route)
    query_text = _safe_str(query).lower()

    if source_category in OFFICIAL_SOURCE_MAP:
        return [OFFICIAL_SOURCE_MAP[source_category]]

    if route == "창업" or any(word in query_text for word in ["창업", "스타트업", "사업화"]):
        return [OFFICIAL_SOURCE_MAP["startup_notice"]]

    if any(word in query_text for word in ["훈련", "국비", "내일배움", "k-digital", "kdt", "교육과정"]):
        return [OFFICIAL_SOURCE_MAP["training"]]

    if route in {"주거", "금융", "복지문화", "참여권리", "일자리", "교육"}:
        return [OFFICIAL_SOURCE_MAP["policy"]]

    return list(OFFICIAL_SOURCE_MAP.values())


def build_external_search_queries(
    query: str,
    user_conditions: dict[str, Any] | None = None,
    route: str | None = None,
) -> list[str]:
    """공식 출처 조회에 사용할 검색어 후보를 만든다."""
    user_conditions = user_conditions or {}
    query = _safe_str(query)
    route = _safe_str(route)

    parts = [query]
    region = _safe_str(user_conditions.get("region"))
    interest_domain = _safe_str(user_conditions.get("interest_domain"))

    if region and region not in query:
        parts.append(region)

    if interest_domain and interest_domain not in query:
        parts.append(interest_domain)
    elif route and route not in query and route not in {"전체", "기타"}:
        parts.append(route)

    compact = " ".join(dict.fromkeys(" ".join(parts).split()))
    queries = [compact]

    if any(word in query for word in ["지금", "현재", "신청 가능한", "신청가능한", "모집 중", "모집중", "접수 중", "접수중", "2026"]):
        queries.append(f"{compact} 모집중")
        queries.append(f"{compact} 신청 가능")

    return list(dict.fromkeys(q for q in queries if q))


def plan_official_external_search(
    query: str | None = None,
    user_conditions: dict[str, Any] | None = None,
    route: str | None = None,
    filters: dict[str, Any] | None = None,
    sufficiency_reasons: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    외부 공식 출처 fallback 계획을 생성한다.

    주의: 현재 함수는 실제 네트워크 요청을 수행하지 않는다.
    반환값은 ReAct tool_trace와 API 응답에서 확인 가능한 계획 정보이다.
    """
    # 호환성: nodes.py에서 query=..., user_query=... 어느 이름으로 넘겨도 처리
    if query is None:
        query = kwargs.get("user_query") or kwargs.get("message") or ""

    filters = filters or {}
    user_conditions = user_conditions or {}
    sufficiency_reasons = sufficiency_reasons or []

    source_category = _safe_str(filters.get("source_category"))
    targets = select_official_targets(
        source_category=source_category,
        route=route,
        query=query,
    )
    queries = build_external_search_queries(
        query=query,
        user_conditions=user_conditions,
        route=route,
    )

    return {
        "status": "planned_not_executed",
        "reason": sufficiency_reasons,
        "targets": targets,
        "target_names": [target["name"] for target in targets],
        "queries": queries,
        "message": "공식 외부 출처 검색 계획을 생성했습니다. 실제 API 호출은 추후 K-Startup/온통청년/고용24 연동으로 교체 예정입니다.",
    }
