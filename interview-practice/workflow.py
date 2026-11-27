"""질문이 내부·외부 답변 중 하나에 도달하는 과정을 연결한다 (p.9~11).

main에서 연 컬렉션과 최초 State(query, as_of)를 사용한다. 각 노드는 바뀐 키만 반환하고
LangGraph가 기존 State에 합친다. END의 State에는 분기 근거, 실제 답변 근거와 최종 답변이 남는다.
충분성은 후보와 분야를 기준으로 판단하므로 질문의 모든 세부 요구를 검사하지 않는다.
"""

from datetime import date
from functools import partial

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from answer import build_internal_context, generate_external_answer, generate_internal_answer
from conditions import extract_conditions
from external_search import refine_external_results, search_external
import config
from retriever import check_sufficiency, refine_candidates, search_chunks


class GraphState(TypedDict, total=False):
    """각 노드가 읽거나 갱신할 수 있는 공유 데이터의 타입을 정의한다.

    total=False이므로 모든 키가 처음부터 존재할 필요는 없다.
    invoke()에 query와 as_of를 전달하고, 노드를 거치며 값을 채운다.
    각 노드는 변경할 키만 반환하며, 기존의 다른 키는 유지된다.
    이 타입 선언만으로 값의 존재 여부나 자료형을 런타임에 검증하지는 않는다.
    """

    # 최초 입력
    query: str
    as_of: date

    # 조건 추출 및 검색
    conditions: dict
    retrieved_results: list  # Chroma가 반환한 원본 검색 결과
    candidates: list         # 필터링·중복 제거·재정렬·마감 처리 후 후보

    stage_counts: dict[str, int]   # 같은 데이터를 다시 처리하지 않고 단계별 개수를 출력한다.
    external_raw_count: int       # 외부 경로에서만 채운다.

    # 충분성 판단 및 분기
    sufficient: bool
    reason: str

    # 선택된 분기에 따라 둘 중 하나가 추가된다.
    internal_context: list   # 내부 정책 본문, 메타데이터, 자격 판정 근거
    external_results: list   # 정제된 Tavily 검색 결과

    # 최종 출력
    answer_source: str       # "internal" 또는 "external" (실행 경로)
    answer: str


def condition_node(state: GraphState):
    """State의 query를 조건 추출기에 전달해 conditions만 반환한다. 미확인 값은 None이다."""
    conditions = extract_conditions(state["query"])

    # 기존 query, as_of는 유지하고 conditions만 추가한다.
    return {"conditions": conditions}


def retrieve_node(state: GraphState, *, collection):
    """State의 질문으로 collection을 검색해 retrieved_results를 반환한다. 아직 자격을 판단하지 않는다."""
    results = search_chunks(collection, state["query"], config.FETCH_K, state["conditions"], config.FILTER_MODE)

    # pre에서는 제한된 범위, post에서는 전체 컬렉션에서 검색한 순위다.
    return {"retrieved_results": results}


def refine_node(state: GraphState):
    """검색 청크에 사용자 조건, 정책 ID, 분야 우선순위, 기준일을 차례로 적용한다.

    후보 목록 candidates와 단계별 개수를 반환한다. 처음 가져온 청크 범위 안에서만 후보를 고른다.
    """
    candidates, counts = refine_candidates(
        state["retrieved_results"], state["conditions"], state["as_of"], config.TOP_K
    )
    return {"candidates": candidates, "stage_counts": counts}


def sufficiency_node(state: GraphState):
    """후보와 관심 분야를 비교해 sufficient와 reason을 반환한다. 근거의 사실성까지 검증하지 않는다."""
    sufficient, reason = check_sufficiency(
        state["candidates"],
        state["conditions"]["interest_domain"],
    )

    # 조건부 엣지가 이후 sufficient 값을 읽어 실행 경로를 선택한다.
    # 이 노드 자체는 외부 검색이나 답변 생성을 수행하지 않는다.
    return {
        "sufficient": sufficient,
        "reason": reason,
    }


def internal_answer_node(state: GraphState):
    """남은 후보별로 자격을 한 번 판단해 internal_context를 만들고 질문과 함께 LLM에 전달한다.

    답변·근거·경로를 반환해 평가에서 다시 판정하지 않게 한다. 세부 신청 자격은 미확인이다.
    """
    conditions = state["conditions"]

    # Python의 규칙 기반 자격 판정 결과를 검색 근거와 함께 묶는다.
    context = build_internal_context(
        state["candidates"],
        conditions["age"],
        conditions["region"],
        state["as_of"],
    )

    # LLM은 판정과 검색 근거를 전달받아 자연어 답변을 작성한다.
    answer = generate_internal_answer(
        state["query"],
        context,
        state["as_of"],
    )

    return {
        "internal_context": context,
        "answer_source": "internal",
        "answer": answer,
    }


def external_answer_node(state: GraphState):
    """질문으로 Tavily를 한 번 검색하고 정제한 결과와 원본 개수, 경로, 템플릿 답변을 반환한다.

    정제 결과는 평가에도 재사용한다. 공식 웹사이트의 현재 검색 결과는 과거 기준일과 다를 수 있다.
    """
    # 충분성 판단에서 False가 나왔을 때만 이 노드가 실행된다.
    raw_results = search_external(state["query"])
    results = refine_external_results(raw_results)

    # 외부 검색 결과에는 검증된 자격 메타데이터가 없으므로
    # 내부 자격 판정 로직을 그대로 적용하지 않는다.
    # 이 답변은 LLM 생성이 아니라 제목·본문 일부·출처를 조립한 것이다.
    answer = generate_external_answer(results)

    return {
        "external_results": results,
        "external_raw_count": len(raw_results),
        "answer_source": "external",
        "answer": answer,
    }


def route_after_sufficiency(state: GraphState):
    """State의 sufficient를 읽어 조건부 엣지의 목적지 키 internal 또는 external을 반환한다."""
    # 반환 문자열은 아래 add_conditional_edges()의 매핑 키와 일치한다.
    if state["sufficient"]:
        return "internal"

    return "external"


def build_workflow(collection):
    """준비한 Chroma 컬렉션을 검색 노드에 연결하고 컴파일한 그래프를 반환한다.

    각 호출의 질문과 기준일은 invoke에 전달한다. 이 함수에서는 API를 호출하지 않는다.

    START → condition → retrieve → refine → sufficiency
                                               ├─ True  → internal_answer → END
                                               └─ False → external_answer → END
    """
    workflow = StateGraph(GraphState)

    # 노드 등록: 그래프에서 사용할 이름과 실행할 함수를 연결한다.
    workflow.add_node("condition", condition_node)
    workflow.add_node("retrieve", partial(retrieve_node, collection=collection))
    workflow.add_node("refine", refine_node)
    workflow.add_node("sufficiency", sufficiency_node)
    workflow.add_node("internal_answer", internal_answer_node)
    workflow.add_node("external_answer", external_answer_node)

    # 일반 엣지: 노드의 실행 순서를 지정한다.
    workflow.add_edge(START, "condition")
    workflow.add_edge("condition", "retrieve")
    workflow.add_edge("retrieve", "refine")
    workflow.add_edge("refine", "sufficiency")

    # 조건부 엣지: sufficiency 노드 실행 후 라우팅 함수가
    # 갱신된 State를 읽고, 반환값에 대응하는 노드를 선택한다.
    workflow.add_conditional_edges(
        "sufficiency",
        route_after_sufficiency,
        {
            "internal": "internal_answer",
            "external": "external_answer",
        },
    )

    # 내부·외부 답변 생성 중 선택된 경로 하나를 수행한 후 종료한다.
    workflow.add_edge("internal_answer", END)
    workflow.add_edge("external_answer", END)

    # compile()은 그래프를 실행 가능한 형태로 만든다.
    # 실제 검색 및 API 호출은 invoke()에서 일어난다.
    return workflow.compile()
