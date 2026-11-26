"""LangGraph와 사후 평가 (p.9~12). step14의 함수를 호출해 질문과 기준일을 최종 State로 바꾸고 원할 때 별도로 채점한다. 현재 workflow 및 evaluation으로 나누기 전의 실행본이다.

이젠, 안쉼 재현 실습: LangGraph 및 LLM-as-a-Judge (실습 15~16).

포트폴리오 p.9~12의 주요 검색·답변·평가 흐름을 재현하는 학습용 코드다.
기존 step14_rag.py의 함수를 재사용하므로 해당 파일과 기존 Chroma DB가 필요하다.
이 파일에서는 기능의 구현 자체보다 State, Node, Edge, 조건 분기를 학습한다.
기존 프로젝트의 전체 구조나 과거 성능 수치를 그대로 재현한 것은 아니다.
"""

import json
from datetime import date

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# 이전 실습에서 구현한 검색·자격 판정·답변 생성 함수들을 재사용한다.
# step14_rag.py의 main()은 import할 때 실행되지 않는다.
from step14_rag import (
    client,
    CHAT_MODEL,
    extract_conditions,
    get_collection,
    search_chunks,
    filter_results,
    deduplicate_results,
    rerank_results,
    filter_expired_results,
    check_sufficiency,
    build_internal_context,
    generate_internal_answer,
    search_external,
    refine_external_results,
    generate_external_answer,
)


# ============================================================
# 1. 실험 설정
# ============================================================

QUERY = "월세 지원 정책 알려줘"

# None: 실행 당일의 날짜를 사용한다 (현재 데이터에서는 외부 검색 경로).
# 과거 날짜: 마감 필터링을 기준으로 내부 검색 경로를 확인하는 실험용 설정.
# 실제 과거 모집 여부까지 검증하는 것은 아니다.
AS_OF = None
# AS_OF = date(2026, 6, 1)

# True: 답변을 생성한 후 별도로 LLM 평가를 수행한다 (추가 API 호출).
# False: 답변 생성까지만 실행한다.
RUN_EVALUATION = True


# ============================================================
# 2. 공유 State 정의 (포트폴리오 p.9~10)
# ============================================================

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

    # 충분성 판단 및 분기
    sufficient: bool
    reason: str

    # 선택된 분기에 따라 둘 중 하나가 추가된다.
    internal_context: list   # 내부 정책 본문, 메타데이터, 자격 판정 근거
    external_results: list   # 정제된 Tavily 검색 결과

    # 최종 출력
    answer_source: str       # "internal" 또는 "external" (실행 경로)
    answer: str


# ============================================================
# 3. 노드 정의 (포트폴리오 p.9~11)
# ============================================================
# Node: State에서 필요한 데이터를 읽고, 실제 작업을 수행한 뒤
# 변경할 데이터를 딕셔너리로 반환하는 함수다.
# 검색 알고리즘 자체는 step14_rag.py에 있으며, 여기서는 호출만 담당한다.


def condition_node(state: GraphState):
    """자연어 질문에서 나이, 지역, 관심 분야를 추출한다 (p.9~10)."""
    conditions = extract_conditions(state["query"])

    # 기존 query, as_of는 유지하고 conditions만 추가한다.
    return {"conditions": conditions}


def retrieve_node(state: GraphState):
    """질문을 임베딩하여 Chroma에서 유사한 청크를 검색한다 (p.10)."""
    collection = get_collection()
    results = search_chunks(collection, state["query"])

    # 아직 나이·지역 필터링을 적용하지 않은 원본 결과다.
    return {"retrieved_results": results}


def refine_node(state: GraphState):
    """내부 검색 결과를 정책 단위 후보로 정리한다 (p.10~11)."""
    conditions = state["conditions"]

    # 1. 사용자가 제공한 나이·지역과 맞지 않는 후보를 제외한다.
    # 정보가 없는 조건은 검색 단계에서 생략한다.
    results = filter_results(
        state["retrieved_results"],
        conditions["age"],
        conditions["region"],
    )

    # 2. 같은 정책(item_id)의 여러 청크 중 대표 청크만 선택한다.
    results = deduplicate_results(results)

    # 3. 관심 분야 일치 여부를 우선하고, 그다음 유사도로 정렬한다.
    results = rerank_results(results, conditions["interest_domain"])

    # 4. 기준일보다 신청 마감일이 앞선 공고를 제외한다.
    results = filter_expired_results(results, as_of=state["as_of"])

    # 원본 retrieved_results는 덮어쓰지 않고 별도 키에 보관한다.
    return {"candidates": results}


def sufficiency_node(state: GraphState):
    """내부 검색 후보가 답변 근거로 충분한지 판단한다 (p.11)."""
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
    """내부 후보의 자격을 판단하고 LLM 답변을 생성한다 (p.10~11)."""
    conditions = state["conditions"]

    # Python의 규칙 기반 자격 판정 결과를 검색 근거와 함께 묶는다.
    context = build_internal_context(
        state["candidates"],
        conditions["age"],
        conditions["region"],
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
    """Tavily 검색·정제 후 별도의 답변 양식으로 응답한다 (p.11)."""
    # 충분성 판단에서 False가 나왔을 때만 이 노드가 실행된다.
    results = search_external(state["query"])
    results = refine_external_results(results)

    # 외부 검색 결과에는 검증된 자격 메타데이터가 없으므로
    # 내부 자격 판정 로직을 그대로 적용하지 않는다.
    # 이 답변은 LLM 생성이 아니라 제목·본문 일부·출처를 조립한 것이다.
    answer = generate_external_answer(results)

    return {
        "external_results": results,
        "answer_source": "external",
        "answer": answer,
    }


# ============================================================
# 4. 조건부 엣지의 라우팅 함수 (포트폴리오 p.11)
# ============================================================


def route_after_sufficiency(state: GraphState):
    """충분성 판단 이후 어떤 경로로 진행할지 결정한다."""
    # 반환 문자열은 아래 add_conditional_edges()의 매핑 키와 일치한다.
    if state["sufficient"]:
        return "internal"

    return "external"


# ============================================================
# 5. 그래프 구성 및 컴파일 (포트폴리오 p.9~10)
# ============================================================


def build_workflow():
    """노드와 엣지를 연결하고 실행 가능한 그래프를 반환한다.

    START → condition → retrieve → refine → sufficiency
                                               ├─ True  → internal_answer → END
                                               └─ False → external_answer → END
    """
    workflow = StateGraph(GraphState)

    # 노드 등록: 그래프에서 사용할 이름과 실행할 함수를 연결한다.
    workflow.add_node("condition", condition_node)
    workflow.add_node("retrieve", retrieve_node)
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


# ============================================================
# 6. LLM-as-a-Judge 평가 (포트폴리오 p.11~12)
# ============================================================


def evaluate_answer(state: GraphState):
    """그래프가 반환한 최종 State를 별도의 LLM 호출로 평가한다.

    평가 입력: 사용자 질문, 기준일, 실제 선택된 검색 근거, 최종 답변
    평가 출력: 검색 관련성, 근거 충실도, 답변 적절성 (각 1~5점), 평가 이유

    이 함수는 그래프의 노드가 아니다. 답변 생성이 종료된 후 호출한다.
    따라서 평가 점수는 현재 워크플로우의 분기나 답변을 변경하지 않는다.
    """
    # 실제 답변 생성 경로에 맞는 근거만 평가자에게 전달한다.
    if state["answer_source"] == "internal":
        context = state["internal_context"]
    else:
        context = state["external_results"]

    # 이전 실습의 세 가지 평가 항목과 채점 프롬프트를 유지한다.
    system_prompt = """
    당신은 RAG 서비스의 품질 평가자입니다.

    다음 세 가지 항목을 각각 1~5점으로 평가하세요.

    1. context_relevance:
       검색된 근거가 사용자 질문과 관련 있는가?

    2. groundedness:
       답변의 주장이 제공된 검색 근거에 충실한가?

    3. answer_relevance:
       답변이 사용자의 질문을 적절하게 해결하는가?

    점수 기준:
    1점: 매우 부족
    2점: 부족
    3점: 보통
    4점: 양호
    5점: 매우 양호

    근거에 없는 사실을 추측하지 마세요.

    다음 형식의 JSON으로 반환하세요.
    {
        "context_relevance": 0,
        "groundedness": 0,
        "answer_relevance": 0,
        "reason": "평가 근거"
    }
    """

    # date 객체는 JSON에서 바로 표현할 수 없으므로 문자열로 변환한다.
    evaluation_data = {
        "query": state["query"],
        "as_of": str(state["as_of"]),
        "context": context,
        "answer": state["answer"],
    }

    # 생성에 사용한 모델을 이번에는 평가자의 역할로 호출한다.
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(evaluation_data, ensure_ascii=False),
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    # JSON Mode는 JSON 형식을 요구하지만 점수 범위·타입이나
    # 평가의 객관성·사실 정확성까지 보장하지는 않는다.
    return json.loads(response.choices[0].message.content)


# ============================================================
# 7. 핵심 결과 출력
# ============================================================


def print_workflow_result(state: GraphState):
    """전체 청크 본문 대신 핵심 처리 결과와 최종 답변만 보여준다."""
    print("\n[LangGraph 실행 결과]")
    print("질문:", state["query"])
    print("마감 판단 기준일:", state["as_of"])
    print("추출 조건:", state["conditions"])
    print("검색 청크 수:", len(state["retrieved_results"]))
    print("최종 후보 수:", len(state["candidates"]))
    print("충분성 판단:", state["sufficient"])
    print("판단 근거:", state["reason"])
    print("실행 경로:", state["answer_source"])
    print("최종 State의 키:", list(state.keys()))

    print("\n[최종 답변]")
    print(state["answer"])


def print_evaluation(evaluation):
    """LLM 평가 결과와 그 이유를 출력한다."""
    print("\n[LLM-as-a-Judge 평가]")
    for key, value in evaluation.items():
        print(f"{key}: {value}")


# ============================================================
# 8. 전체 실행 흐름
# ============================================================


def main():
    # 데이터 적재는 이전 실습(step14_rag.py)에서 완료했다는 전제다.
    # 여기서는 기존 Chroma DB를 재사용하고 정책을 다시 임베딩하지 않는다.
    as_of = date.today() if AS_OF is None else AS_OF

    # A. 그래프를 구성하고 최초 State를 전달하여 실행한다.
    app = build_workflow()
    result = app.invoke({
        "query": QUERY,
        "as_of": as_of,
    })

    # B. END에 도달한 최종 State를 확인한다.
    print_workflow_result(result)

    # C. 필요할 때만 답변 생성 이후에 품질 평가를 수행한다.
    if RUN_EVALUATION:
        evaluation = evaluate_answer(result)
        print_evaluation(evaluation)


# 파일을 직접 실행할 때만 워크플로우 및 평가를 실행한다.
# import할 때는 실행하지 않으므로 다른 실험에서도 함수를 재사용할 수 있다.
if __name__ == "__main__":
    main()
