# RAG 평가 결과

- 총 케이스 수: 10
- 통과 케이스 수: 8
- 통과율: 80.0%
- 평균 규칙 기반 점수: 0.893
- BLEU/ROUGE 계산 케이스 수: 9
- 평균 BLEU: 0.0119
- 평균 ROUGE-1 F1: 0.0993
- 평균 ROUGE-2 F1: 0.0240
- 평균 ROUGE-L F1: 0.0768

## 케이스별 결과

| ID | Pass | Rule Score | BLEU | ROUGE-L F1 | Query | 실패 항목 |
|---|---:|---:|---:|---:|---|---|
| TC001_startup_open_2026 | ✅ | 1.000 | 0.0235 | 0.0865 | 2026년에 신청 가능한 창업지원 공고 추천해줘 | - |
| TC002_startup_exclude_old | ❌ | 0.929 | 0.0000 | 0.0410 | 2019년에 했던 청년 창업 지원사업 말고 지금 신청 가능한 공고 알려줘 | must_not_have_any |
| TC003_react_fallback_unrealistic | ✅ | 1.000 | 0.0751 | 0.2449 | 화성에서 받을 수 있는 청년 우주창업 지원금 알려줘 | - |
| TC004_housing_monthly_rent | ✅ | 1.000 | 0.0081 | 0.0589 | 서울에 사는 25세 청년이 받을 수 있는 월세 지원 정책 알려줘 | - |
| TC005_training_ai_data | ✅ | 1.000 | 0.0001 | 0.0250 | 국민내일배움카드로 들을 수 있는 AI 데이터 분석 훈련 과정 추천해줘 | - |
| TC006_job_interview_allowance | ✅ | 1.000 | 0.0000 | 0.0828 | 면접수당 받을 수 있는 정책 알려줘 | - |
| TC007_finance_savings | ✅ | 1.000 | 0.0000 | 0.0247 | 청년도약계좌 같은 금융 정책 알려줘 | - |
| TC008_participation_committee | ✅ | 1.000 | 0.0000 | 0.0460 | 청년 참여위원회 모집 정보 알려줘 | - |
| TC009_short_query_warning | ✅ | 1.000 | 0.0000 | 0.0816 | 월세 | - |
| TC010_no_empty_query | ❌ | 0.000 | - | - |  | request_success |

## 해석 가이드

- 규칙 기반 점수는 route, next_action, 마감 공고 배제, recommendations 개수, ReAct trace 존재 여부 등을 자동 점검한 값이다.
- BLEU/ROUGE는 evaluation_dataset.jsonl의 reference_answer 또는 expected_answer가 있는 케이스에서만 계산된다.
- 추천형 RAG에서는 같은 정책을 맞게 추천해도 문장 표현 차이로 BLEU/ROUGE가 낮을 수 있으므로 참고 지표로 사용한다.
- LLM-as-a-Judge 평가는 judge_inputs.jsonl을 사용해 context_relevance, groundedness, answer_relevance, freshness_safety, react_trace_quality를 별도로 채점한다.
- 자동 점수에서 실패한 케이스는 Swagger 응답의 tool_trace와 recommendations를 함께 확인한다.