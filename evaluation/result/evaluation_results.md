# RAG 평가 결과

- 총 케이스 수: 10
- 통과 케이스 수: 10
- 통과율: 100.0%
- 평균 규칙 기반 점수: 1.000
- BLEU/ROUGE 계산 케이스 수: 10
- 평균 BLEU: 0.0212
- 평균 ROUGE-1 F1: 0.1451
- 평균 ROUGE-2 F1: 0.0581
- 평균 ROUGE-L F1: 0.1242

## 케이스별 결과

| ID | Pass | Rule Score | BLEU | ROUGE-L F1 | Query | 실패 항목 |
|---|---:|---:|---:|---:|---|---|
| TC001_startup_open_2026 | ✅ | 1.000 | 0.0249 | 0.0909 | 2026년에 신청 가능한 창업지원 공고 추천해줘 | - |
| TC002_startup_exclude_old | ✅ | 1.000 | 0.0002 | 0.0757 | 2019년에 했던 청년 창업 지원사업 말고 지금 신청 가능한 공고 알려줘 | - |
| TC003_react_fallback_unrealistic | ✅ | 1.000 | 0.0006 | 0.2014 | 화성에서 받을 수 있는 청년 우주창업 지원금 알려줘 | - |
| TC004_housing_monthly_rent | ✅ | 1.000 | 0.0081 | 0.0589 | 서울에 사는 25세 청년이 받을 수 있는 월세 지원 정책 알려줘 | - |
| TC005_training_ai_data | ✅ | 1.000 | 0.0001 | 0.0251 | 국민내일배움카드로 들을 수 있는 AI 데이터 분석 훈련 과정 추천해줘 | - |
| TC006_job_interview_allowance | ✅ | 1.000 | 0.0000 | 0.0976 | 면접수당 받을 수 있는 정책 알려줘 | - |
| TC007_finance_savings | ✅ | 1.000 | 0.0000 | 0.0290 | 청년도약계좌 같은 금융 정책 알려줘 | - |
| TC008_participation_committee | ✅ | 1.000 | 0.0000 | 0.0833 | 청년 참여위원회 모집 정보 알려줘 | - |
| TC009_short_query_warning | ✅ | 1.000 | 0.0000 | 0.0420 | 월세 | - |
| TC010_no_empty_query | ✅ | 1.000 | 0.1782 | 0.5385 |  | - |

## 해석 가이드

- 규칙 기반 점수는 route, next_action, 마감 공고 배제, recommendations 개수, ReAct trace 존재 여부 등을 자동 점검한 값이다.
- BLEU/ROUGE는 evaluation_dataset.jsonl의 reference_answer 또는 expected_answer가 있는 케이스에서만 계산된다.
- 추천형 RAG에서는 같은 정책을 맞게 추천해도 문장 표현 차이로 BLEU/ROUGE가 낮을 수 있으므로 참고 지표로 사용한다.
- LLM-as-a-Judge 평가는 judge_inputs.jsonl을 사용해 context_relevance, groundedness, answer_relevance, freshness_safety, react_trace_quality를 별도로 채점한다.
- must_not_have_any의 기본 검사 범위는 recommendations이다. fallback 답변에서 제외 사유로 언급된 후보명은 기본적으로 실패 처리하지 않는다.
- answer까지 금지어 검사가 필요한 경우 evaluation_dataset.jsonl에서 must_not_scope를 answer 또는 recommendations_and_answer로 지정한다.
- 자동 점수에서 실패한 케이스는 Swagger 응답의 tool_trace와 recommendations를 함께 확인한다.