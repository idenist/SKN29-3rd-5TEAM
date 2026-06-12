"""
LLM-as-a-Judge 프롬프트 템플릿.

사용 방법:
- evaluate_rag.py 실행 시 --write-judge-inputs 옵션을 주면 judge_inputs.jsonl이 생성된다.
- judge_inputs.jsonl의 messages를 OpenAI client 또는 사내 평가 도구에 전달해 채점한다.
- evaluation_dataset.jsonl의 reference_answer는 BLEU/ROUGE 계산과 LLM Judge 참고 기준으로 함께 사용한다.
"""

from __future__ import annotations


JUDGE_SYSTEM_PROMPT = """당신은 청년 정책 RAG 서비스의 평가자입니다.
답변이 사용자 질문, 기대 동작, 기준 답변, 응답 JSON에 얼마나 잘 맞는지 엄격하게 평가하세요.
정책명, 신청 기간, 마감 여부, 출처 URL, 자격 조건은 제공된 응답 JSON에 있는 정보만 기준으로 판단하세요.
응답 JSON에 없는 사실을 추측하지 마세요.
BLEU/ROUGE 점수는 참고용일 뿐이며, 최종 평가는 근거성·최신성·사용자 의도 반영 여부를 더 중요하게 보세요.
반드시 JSON만 출력하세요."""


JUDGE_USER_PROMPT_TEMPLATE = """
[평가 대상 질문]
{query}

[테스트 케이스 기대 동작]
{expected_behavior}

[기준 답변 / Reference Answer]
{reference_answer}

[중점 평가 항목]
{judge_focus}

[서비스 응답 JSON]
{response_json}

다음 기준으로 1~5점 정수 점수를 부여하세요.

1. context_relevance: 검색/추천 결과가 질문의 도메인과 조건에 관련 있는가?
2. groundedness: 답변이 recommendations/source_url/deadline_status 등 제공된 근거에 기반하는가?
3. answer_relevance: 사용자의 질문과 reference_answer의 핵심 의도에 직접적으로 답하는가?
4. freshness_safety: 마감/과거 공고를 부적절하게 추천하지 않는가?
5. react_trace_quality: tool_trace, internal_search_sufficient, next_action, external_search_status가 결과와 일관되는가?
6. reference_alignment: reference_answer의 핵심 기대 내용과 의미적으로 일치하는가? 단, 표현 차이는 감점하지 않는다.

아래 JSON 형식만 출력하세요.
{{
  "context_relevance": 1,
  "groundedness": 1,
  "answer_relevance": 1,
  "freshness_safety": 1,
  "react_trace_quality": 1,
  "reference_alignment": 1,
  "overall": 1,
  "pass": false,
  "strengths": ["..."],
  "issues": ["..."],
  "suggestion": "..."
}}
""".strip()


def build_judge_prompt(
    query: str,
    expected_behavior: str,
    judge_focus: list[str],
    response_json: str,
    reference_answer: str = "",
) -> list[dict[str, str]]:
    """OpenAI chat.completions/messages 형태로 바로 넘길 수 있는 프롬프트 메시지 생성."""
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": JUDGE_USER_PROMPT_TEMPLATE.format(
                query=query,
                expected_behavior=expected_behavior,
                reference_answer=reference_answer or "제공된 기준 답변 없음",
                judge_focus=", ".join(judge_focus or []),
                response_json=response_json,
            ),
        },
    ]
