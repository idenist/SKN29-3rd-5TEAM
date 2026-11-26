"""최종 답변의 LLM-as-a-Judge 평가 (p.11~12).

main이 그래프 종료 후 최종 State를 전달하면 질문·기준일·선택 경로의 근거·답변을 채점한다.
세 점수와 이유를 담은 딕셔너리를 반환한다. 평가가 그래프를 재실행하거나 답변을 고치지는 않는다."""

import json

from config import CHAT_MODEL, get_openai_client


def evaluate_answer(state):
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
    response = get_openai_client().chat.completions.create(
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
