"""
backend/services/hybrid_retriever.py

Vector DB(Chroma) 검색 결과와 Graph DB(Neo4j) 검색 결과를 병합하는 Hybrid RAG 유틸.

설계 원칙:
- 기존 rag_service.py 의 Retriever 결과를 INPUT으로 받음 (기존 코드 수정 없음)
- Graph 결과를 보조 소스로 추가하되, Vector 결과가 없어도 동작
- Graph 결과가 없어도 기존 Vector 결과만으로 동작 (graceful degradation)
- Answer Generator가 인식하는 context 문자열 포맷 동일하게 유지
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def merge_vector_and_graph(
    vector_chunks: list[dict],
    graph_chunks: list[dict],
    max_total: int = 8,
    graph_weight: float = 0.3,
) -> list[dict]:
    """
    Vector 검색 결과와 Graph 검색 결과를 병합한다.

    전략:
    - Vector 결과를 우선 배치 (신뢰도 높음)
    - Graph 결과 중 Vector에 없는 item_id만 추가 (중복 제거)
    - max_total 초과 시 Vector 결과 우선 보존

    Args:
        vector_chunks: Retriever(Chroma) 반환 compact chunk 리스트
        graph_chunks:  GraphService.search_by_conditions() 반환 리스트
        max_total:     최종 반환 최대 건수
        graph_weight:  Graph 결과 비율 (0.3 → 전체 8개 중 최대 2~3개)

    Returns:
        merged: 병합된 chunk 리스트 (from_graph 필드로 출처 구분 가능)
    """
    if not graph_chunks:
        return vector_chunks[:max_total]

    vector_ids = {c.get("item_id") for c in vector_chunks}

    # Graph에서 Vector에 없는 것만
    graph_only = [c for c in graph_chunks if c.get("item_id") not in vector_ids]

    # 비율 계산
    graph_slots = max(1, int(max_total * graph_weight))
    vector_slots = max_total - min(len(graph_only), graph_slots)

    merged = vector_chunks[:vector_slots] + graph_only[:graph_slots]

    logger.info(
        "Hybrid merge — vector=%d, graph_new=%d, total=%d",
        min(len(vector_chunks), vector_slots),
        min(len(graph_only), graph_slots),
        len(merged),
    )
    return merged


def build_graph_context(graph_chunks: list[dict]) -> str:
    """
    Graph 검색 결과를 Answer Generator 프롬프트에 결합할 컨텍스트 문자열로 변환.

    Answer Generator의 기존 context 문자열 뒤에 append하는 방식으로 사용.
    graph_chunks가 비어있으면 빈 문자열 반환 → 기존 프롬프트에 영향 없음.
    """
    if not graph_chunks:
        return ""

    lines = ["\n\n[Graph DB 관계 검색 추가 결과]"]
    for i, chunk in enumerate(graph_chunks, 1):
        title   = chunk.get("title") or chunk.get("policy_name", "")
        domain  = chunk.get("domain", "")
        cat     = chunk.get("source_category", "")
        item_id = chunk.get("item_id", "")
        lines.append(f"{i}. {title} | {domain} | {cat} | {item_id}")

    lines.append("[Graph 결과는 관계 기반 검색으로 보완된 항목입니다]")
    return "\n".join(lines)


def deduplicate_by_item_id(chunks: list[dict]) -> list[dict]:
    """item_id 기준 중복 제거. 먼저 나온 항목 우선."""
    seen = set()
    result = []
    for c in chunks:
        iid = c.get("item_id") or c.get("policy_id", "")
        if iid and iid not in seen:
            seen.add(iid)
            result.append(c)
    return result