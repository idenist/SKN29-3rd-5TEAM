# RAG 평가 결과

- 총 케이스 수: 10
- 통과 케이스 수: 7
- 통과율: 70.0%
- 평균 규칙 기반 점수: 0.836

## 케이스별 결과

| ID | Pass | Score | Query | 실패 항목 |
|---|---:|---:|---|---|
| TC001_startup_open_2026 | ✅ | 1.000 | 2026년에 신청 가능한 창업지원 공고 추천해줘 | - |
| TC002_startup_exclude_old | ❌ | 0.929 | 2019년에 했던 청년 창업 지원사업 말고 지금 신청 가능한 공고 알려줘 | must_not_have_any |
| TC003_react_fallback_unrealistic | ❌ | 0.429 | 화성에서 받을 수 있는 청년 우주창업 지원금 알려줘 | must_have_any, must_not_have_any, internal_search_sufficient, next_action, external_search_status, external_search_targets, max_recommendations, no_expired_recommendations |
| TC004_housing_monthly_rent | ✅ | 1.000 | 서울에 사는 25세 청년이 받을 수 있는 월세 지원 정책 알려줘 | - |
| TC005_training_ai_data | ✅ | 1.000 | 국민내일배움카드로 들을 수 있는 AI 데이터 분석 훈련 과정 추천해줘 | - |
| TC006_job_interview_allowance | ✅ | 1.000 | 면접수당 받을 수 있는 정책 알려줘 | - |
| TC007_finance_savings | ✅ | 1.000 | 청년도약계좌 같은 금융 정책 알려줘 | - |
| TC008_participation_committee | ✅ | 1.000 | 청년 참여위원회 모집 정보 알려줘 | - |
| TC009_short_query_warning | ✅ | 1.000 | 월세 | - |
| TC010_no_empty_query | ❌ | 0.000 |  | request_success |

## 해석 가이드

- 규칙 기반 점수는 route, next_action, 마감 공고 배제, recommendations 개수, ReAct trace 존재 여부 등을 자동 점검한 값이다.
- LLM-as-a-Judge 평가는 judge_inputs.jsonl을 사용해 context_relevance, groundedness, answer_relevance, freshness_safety, react_trace_quality를 별도로 채점한다.
- 자동 점수에서 실패한 케이스는 Swagger 응답의 tool_trace와 recommendations를 함께 확인한다.