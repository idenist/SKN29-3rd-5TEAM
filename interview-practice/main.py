"""실습 실행과 결과 읽기 (p.9~12).

config의 질문·기준일을 입력으로 받고 DB 준비 → 그래프 실행 → 선택적 평가 순으로 진행한다.
워크플로우의 최종 State에서 단계별 후보 수, 경로, 답변을 출력한다. 평가 점수는 분기에 쓰지 않는다.
"""

from datetime import date

import config
from evaluation import evaluate_answer
from indexing import build_chunks, get_collection, index_chunks
from policies import POLICIES
from workflow import build_workflow


def print_result(state, verbose=False):
    """최종 State에 저장된 수와 근거를 표시한다. 출력 과정에서는 검색이나 자격 판정을 반복하지 않는다.

    verbose가 참이면 청크별 거리 환산 점수와 State 키도 출력한다. 임베딩 전체는 출력하지 않는다.
    """
    conditions = state["conditions"]
    print("[사용자 질문]", state["query"])
    print("[마감 판단 기준일]", state["as_of"])
    print("\n[추출 조건]")
    for key, label in (("age", "나이"), ("region", "지역"), ("interest_domain", "관심 분야")):
        value = conditions[key]
        print(label, value if value is not None else "없음")

    print("\n[내부 검색]")
    print("의미 검색", len(state["retrieved_results"]), "개 청크")
    for stage, count in state["stage_counts"].items():
        unit = "개 청크" if stage == "조건 필터링" else "개 정책"
        print(stage, count, unit)
    print("\n[충분성 판단]", state["sufficient"], "·", state["reason"])
    print("[실행 경로]", state["answer_source"])
    if state["answer_source"] == "external":
        print("[외부 검색] 원본", state["external_raw_count"], "건 / 정제 후", len(state["external_results"]), "건")
    print("\n[최종 답변]")
    print(state["answer"])

    if verbose:
        print("\n[검색 청크와 코사인 유사도]")
        for result in state["retrieved_results"]:
            print(result["chunk_id"], round(result["score"], 3))
        print("[최종 State 키]", ", ".join(state))


def main():
    """설정과 정책 레코드를 읽어 필요할 때만 적재한 뒤 질문 하나를 실행하고 결과를 출력한다.

    평가를 켜면 그래프 종료 후 최종 State로 세 항목을 채점한다. 외부 서비스 실패는 호출자에게 전달된다.
    """
    try:
        collection = get_collection(config.DATASET)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("[데이터셋]", config.DATASET, collection.name, "·", config.FILTER_MODE)
    if config.DATASET == "sample" and (config.UPDATE_INDEX or collection.count() == 0):
        index_chunks(collection, build_chunks(POLICIES))

    as_of = config.AS_OF if config.AS_OF is not None else date.today()
    graph = build_workflow(collection)
    state = graph.invoke({"query": config.QUERY, "as_of": as_of})
    print_result(state, config.VERBOSE)

    if config.RUN_EVALUATION:
        evaluation = evaluate_answer(state)
        print("\n[LLM-as-a-Judge 평가]")
        for key, label in (("context_relevance", "검색 관련성"), ("groundedness", "근거 충실도"),
                           ("answer_relevance", "답변 적절성"), ("reason", "평가 근거")):
            print(label, evaluation.get(key))


if __name__ == "__main__":
    main()
