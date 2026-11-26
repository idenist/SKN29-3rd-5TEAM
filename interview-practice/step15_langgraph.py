from datetime import date
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import json
from step14_rag import client, CHAT_MODEL

# 기존 실습에서 작성한 기능을 그대로 재사용한다.
from step14_rag import (
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
    generate_external_answer
)


# ==================================================
# 1. 공유 State 정의
# ==================================================

class GraphState(TypedDict, total=False):
    query: str
    as_of: date
    conditions: dict
    retrieved_results: list
    candidates: list
    sufficient: bool
    reason: str
    internal_context: list
    external_results: list
    answer_source: str
    answer: str


# ==================================================
# 2. 노드 정의
# ==================================================

def condition_node(state):
    """사용자 조건을 추출한다."""
    conditions = extract_conditions(state["query"])

    return {"conditions": conditions}


def retrieve_node(state):
    """Chroma에서 의미 검색을 수행한다."""
    collection = get_collection()
    results = search_chunks(collection, state["query"])

    return {"retrieved_results": results}


def refine_node(state):
    """내부 검색 후보를 정리한다."""
    conditions = state["conditions"]

    results = filter_results(
        state["retrieved_results"],
        conditions["age"],
        conditions["region"]
    )

    results = deduplicate_results(results)

    results = rerank_results(
        results,
        conditions["interest_domain"]
    )

    results = filter_expired_results(
        results,
        as_of=state["as_of"]
    )

    # 원본 검색 결과는 유지하고 정리된 후보를 별도로 저장한다.
    return {"candidates": results}


def sufficiency_node(state):
    """내부 검색 결과가 충분한지 판단한다."""
    sufficient, reason = check_sufficiency(
        state["candidates"],
        state["conditions"]["interest_domain"]
    )

    return {
        "sufficient": sufficient,
        "reason": reason
    }


def internal_answer_node(state):
    """내부 후보의 자격을 판단하고 LLM으로 답변을 생성한다."""
    conditions = state["conditions"]

    context = build_internal_context(
        state["candidates"],
        conditions["age"],
        conditions["region"]
    )

    answer = generate_internal_answer(
        state["query"],
        context,
        state["as_of"]
    )

    return {
        "internal_context": context,
        "answer_source": "internal",
        "answer": answer
    }


def external_answer_node(state):
    """Tavily 검색 결과를 정제하고 답변을 구성한다."""
    results = search_external(state["query"])
    results = refine_external_results(results)

    answer = generate_external_answer(results)

    return {
        "external_results": results,
        "answer_source": "external",
        "answer": answer
    }


# ==================================================
# 3. 다음 노드를 결정하는 라우팅 함수
# ==================================================

def route_after_sufficiency(state):
    """충분성 판단 결과에 따라 실행 경로를 선택한다."""

    if state["sufficient"]:
        return "internal"

    return "external"


# ==================================================
# 4. 그래프 구성
# ==================================================

workflow = StateGraph(GraphState)

# 노드 등록
workflow.add_node("condition", condition_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("refine", refine_node)
workflow.add_node("sufficiency", sufficiency_node)
workflow.add_node("internal_answer", internal_answer_node)
workflow.add_node("external_answer", external_answer_node)

# 일반 엣지: 항상 정해진 다음 노드를 실행한다.
workflow.add_edge(START, "condition")
workflow.add_edge("condition", "retrieve")
workflow.add_edge("retrieve", "refine")
workflow.add_edge("refine", "sufficiency")

# 조건부 엣지: 라우팅 함수의 반환값에 따라
# 다음에 실행할 노드를 결정한다.
workflow.add_conditional_edges(
    "sufficiency",
    route_after_sufficiency,
    {
        "internal": "internal_answer",
        "external": "external_answer"
    }
)

# 어느 경로로 답변을 생성하든 실행을 종료한다.
workflow.add_edge("internal_answer", END)
workflow.add_edge("external_answer", END)

app = workflow.compile()

def evaluate_answer(state):
    """
    RAG 워크플로우의 최종 State를 받아
    LLM-as-a-Judge 방식으로 품질을 평가한다.
    """

    # 실행 경로에 따라 실제 답변에 사용한 근거를 가져온다.
    if state["answer_source"] == "internal":
        context = state["internal_context"]
    else:
        context = state["external_results"]

    # 평가 기준 정의
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

    # 평가 대상 데이터 구성
    evaluation_data = {
        "query": state["query"],
        "as_of": str(state["as_of"]),
        "context": context,
        "answer": state["answer"]
    }

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": json.dumps(
                    evaluation_data,
                    ensure_ascii=False
                )
            }
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    return json.loads(
        response.choices[0].message.content
    )

# ==================================================
# 5. 워크플로우 실행
# ==================================================

result = app.invoke({
    "query": "월세 지원 정책 알려줘",
    "as_of": date.today()
})


# ==================================================
# 6. 핵심 결과만 출력
# ==================================================

print("추출 조건:", result["conditions"])
print("검색 청크 수:", len(result["retrieved_results"]))
print("최종 후보 수:", len(result["candidates"]))
print("충분성 판단:", result["sufficient"])
print("판단 근거:", result["reason"])
print("실행 경로:", result["answer_source"])
print("최종 State의 키:", result.keys())

print("\n[최종 답변]")
print(result["answer"])

evaluation = evaluate_answer(result)

print("\n[LLM-as-a-Judge 평가]")

for key, value in evaluation.items():
    print(f"{key}: {value}")