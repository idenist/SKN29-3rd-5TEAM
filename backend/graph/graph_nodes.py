"""
backend/graph/graph_nodes.py

LangGraph 워크플로우에 추가할 Graph RAG 노드 2개.

기존 nodes.py 를 수정하지 않고, 이 파일을 import해서 workflow.py에서 연결한다.

추가 노드:
    graph_retrieve_node  — Neo4j 조건 검색
    hybrid_merge_node    — Vector + Graph 결과 병합

GraphState 에 추가 필요한 필드:
    graph_chunks: list[dict]  (없으면 [] 로 초기화됨)
    graph_context: str        (없으면 "" 로 초기화됨)
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ── GraphService 싱글턴 (연결 실패해도 앱 기동 유지) ──────────

_graph_service = None

def get_graph_service():
    """
    GraphService 싱글턴 반환.
    NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD 환경변수 없으면 None 반환.
    """
    global _graph_service
    if _graph_service is not None:
        return _graph_service

    uri      = os.getenv("NEO4J_URI", "")
    user     = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    if not uri or not password:
        logger.info("NEO4J_URI / NEO4J_PASSWORD 미설정 — Graph 검색 비활성화")
        _graph_service = None
        return None

    from backend.db.graph_service import GraphService
    _graph_service = GraphService(uri=uri, user=user, password=password)
    return _graph_service


# ── 노드 함수 ──────────────────────────────────────────────────

def graph_retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    [LangGraph 노드] Neo4j에서 사용자 조건 기반 관계 검색.

    입력 state 필드:
        filters:    Router가 생성한 필터 dict (domain, user_region_code 등)
        route:      Router가 결정한 도메인 문자열

    출력 state 필드:
        graph_chunks: list[dict]  — 검색 결과 (실패 시 [])
    """
    svc = get_graph_service()
    if svc is None or not svc.is_connected():
        logger.info("graph_retrieve_node — Graph 서비스 없음, 건너뜀")
        return {**state, "graph_chunks": []}

    filters       = state.get("filters", {})
    route         = state.get("route", "")
    region_code   = filters.get("user_region_code") or filters.get("region_code", "")
    source_cat    = filters.get("source_category")

    # route → domain 매핑 (Router가 한글 도메인을 쓰므로 그대로 전달)
    domain = route if route not in ("전체", "기타", "") else None

    try:
        graph_chunks = svc.search_by_conditions(
            domain=domain,
            region_code=region_code or None,
            source_category=source_cat,
            limit=5,
        )
        logger.info("graph_retrieve_node — %d건 반환 (domain=%s, region=%s)", len(graph_chunks), domain, region_code)
    except Exception as e:
        logger.warning("graph_retrieve_node 오류: %s", e)
        graph_chunks = []

    return {**state, "graph_chunks": graph_chunks}


def hybrid_merge_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    [LangGraph 노드] Vector 검색 결과(retrieved_chunks)와 Graph 결과(graph_chunks)를 병합.

    입력 state 필드:
        retrieved_chunks: list[dict]  — Chroma Retriever 결과
        graph_chunks:     list[dict]  — Neo4j 검색 결과

    출력 state 필드:
        retrieved_chunks: list[dict]  — 병합 결과 (Eligibility Checker, Answer Generator가 그대로 사용)
        graph_context:    str         — Answer Generator 프롬프트에 append할 Graph 컨텍스트
    """
    from backend.services.hybrid_retriever import (
        merge_vector_and_graph,
        build_graph_context,
        deduplicate_by_item_id,
    )

    vector_chunks = state.get("retrieved_chunks", [])
    graph_chunks  = state.get("graph_chunks", [])

    if not graph_chunks:
        # Graph 결과 없으면 기존 흐름 그대로
        return {**state, "graph_context": ""}

    merged = merge_vector_and_graph(vector_chunks, graph_chunks, max_total=8)
    merged = deduplicate_by_item_id(merged)

    graph_context = build_graph_context(
        [c for c in merged if c.get("from_graph")]
    )

    logger.info(
        "hybrid_merge_node — vector=%d, graph=%d, merged=%d",
        len(vector_chunks), len(graph_chunks), len(merged),
    )

    return {
        **state,
        "retrieved_chunks": merged,
        "graph_context": graph_context,
    }