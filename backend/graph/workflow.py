from typing import Any

from langgraph.graph import END, StateGraph

from backend.graph.nodes import (
    GraphState,
    input_validator_node,
    condition_extractor_node,
    router_node,
    retriever_node,
    result_sufficiency_checker_node,
    external_search_placeholder_node,
    eligibility_checker_node,
    answer_generator_node,
)


def _route_after_sufficiency_check(state: GraphState) -> str:
    """검색 결과 충분성 판단 결과에 따라 다음 노드를 선택한다."""
    if state.get("next_action") == "external_search":
        return "external_search"
    return "eligibility_checker"


def build_rag_workflow():
    """
    청년 정책 RAG 전체 LangGraph workflow.

    흐름:
    Input Validator
    → Condition Extractor
    → Router
    → Retriever
    → Result Sufficiency Checker
    → External Search Placeholder or Eligibility Checker
    → Answer Generator
    → END
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("input_validator", input_validator_node)
    workflow.add_node("condition_extractor", condition_extractor_node)
    workflow.add_node("router", router_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("result_sufficiency_checker", result_sufficiency_checker_node)
    workflow.add_node("external_search", external_search_placeholder_node)
    workflow.add_node("eligibility_checker", eligibility_checker_node)
    workflow.add_node("answer_generator", answer_generator_node)

    workflow.set_entry_point("input_validator")

    workflow.add_edge("input_validator", "condition_extractor")
    workflow.add_edge("condition_extractor", "router")
    workflow.add_edge("router", "retriever")
    workflow.add_edge("retriever", "result_sufficiency_checker")
    workflow.add_conditional_edges(
        "result_sufficiency_checker",
        _route_after_sufficiency_check,
        {
            "external_search": "external_search",
            "eligibility_checker": "eligibility_checker",
        },
    )
    workflow.add_edge("external_search", "eligibility_checker")
    workflow.add_edge("eligibility_checker", "answer_generator")
    workflow.add_edge("answer_generator", END)

    return workflow.compile()


def run_rag_workflow(
    query: str,
    return_full_state: bool = True,
    top_k: int = 5,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    RAG workflow 실행 함수.
    FastAPI /api/chat 또는 Streamlit에서 이 함수를 호출하면 된다.
    """
    app = build_rag_workflow()

    initial_state: GraphState = {
        "user_query": query,
        "warnings": [],
        "errors": [],
        "tool_trace": [],
        "external_used": False,
        "internal_search_sufficient": False,
        "next_action": "internal_retriever",
        "top_k": top_k,
        "use_llm": use_llm,
    }

    result = app.invoke(initial_state)

    if return_full_state:
        return dict(result)

    return {
        "answer": result.get("answer", ""),
        "user_conditions": result.get("user_conditions", {}),
        "route": result.get("route", ""),
        "route_reason": result.get("route_reason", ""),
        "recommendations": result.get("eligibility_results", []),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
        "tool_trace": result.get("tool_trace", []),
        "internal_search_sufficient": result.get("internal_search_sufficient", False),
        "sufficiency_reasons": result.get("sufficiency_reasons", []),
        "next_action": result.get("next_action", ""),
        "external_used": result.get("external_used", False),
    }


# 기존 Router 단독 테스트 함수가 필요하면 유지
def build_router_workflow():
    workflow = StateGraph(GraphState)

    workflow.add_node("input_validator", input_validator_node)
    workflow.add_node("condition_extractor", condition_extractor_node)
    workflow.add_node("router", router_node)

    workflow.set_entry_point("input_validator")

    workflow.add_edge("input_validator", "condition_extractor")
    workflow.add_edge("condition_extractor", "router")
    workflow.add_edge("router", END)

    return workflow.compile()


def run_router_workflow(query: str) -> dict[str, Any]:
    app = build_router_workflow()

    initial_state: GraphState = {
        "user_query": query,
        "warnings": [],
        "errors": [],
    }

    result = app.invoke(initial_state)

    return {
        "query": result.get("user_query"),
        "conditions": result.get("user_conditions", {}),
        "route": result.get("route"),
        "reason": result.get("route_reason"),
        "filters": result.get("filters", {}),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }


if __name__ == "__main__":
    import json

    test_query = "서울에 사는 25세 취준생인데 받을 수 있는 취업 지원 정책 알려줘."
    result = run_rag_workflow(test_query, return_full_state=False)

    print(json.dumps(result, ensure_ascii=False, indent=2))