# 청년 정책 RAG/LLM 평가 보고서

## 1. 평가 목적

본 평가는 청년 정책 통합 탐색 에이전트의 RAG 검색 품질, 답변 근거성, 최신성 안전성, ReAct 기반 분기 구조를 확인하기 위해 수행하였다.  
특히 마감된 공고 추천 방지, 내부 검색 결과 충분성 판단, 외부 공식 출처 fallback 계획 생성 여부를 중점적으로 검증하였다.

## 2. 평가 대상

- API Endpoint: `/chat` 또는 `/api/chat`
- 평가 스크립트: `evaluation/evaluate_rag.py`
- 평가 질의셋: `evaluation/evaluation_dataset.jsonl`
- 결과 저장 위치: `evaluation/result/`

## 3. 평가 데이터셋 구성

평가 질의셋은 총 10개 케이스로 구성하였다.

| 구분 | 포함 케이스 | 평가 목적 |
|---|---|---|
| 정상 추천 | 창업, 주거, 교육훈련, 일자리, 금융, 참여권리 | 도메인 라우팅과 추천 품질 확인 |
| 최신성 검증 | 2026년 신청 가능 공고, 과거 공고 제외 | 마감/과거 공고 추천 방지 확인 |
| ReAct fallback | 비현실적 또는 내부 결과 불충분 질문 | 외부 공식 출처 검색 계획 분기 확인 |
| 입력 검증 | 짧은 질문, 빈 질문 | warning/error 처리 확인 |
| 텍스트 유사도 | reference_answer 포함 전 케이스 | BLEU/ROUGE 참고 지표 산출 |

각 케이스에는 다음 항목을 포함하였다.

- `query`: 사용자 질문
- `expected_route`: 기대 라우팅 도메인
- `expected_behavior`: 기대 동작 설명
- `reference_answer`: BLEU/ROUGE 및 LLM-as-a-Judge 참고 기준 답변
- `must_have_any`, `must_not_have_any`: 답변 포함/제외 키워드
- `expected_next_action`: ReAct 다음 행동 기대값
- `expected_external_search_status`: 외부 검색 계획 상태 기대값
- `allow_expired`: 마감 공고 허용 여부

## 4. 평가 지표

### 4.1 규칙 기반 평가

`evaluate_rag.py`는 API 응답 JSON을 기준으로 다음 항목을 자동 점검한다.

| 지표 | 설명 |
|---|---|
| Route Match | 응답의 `route`가 기대 도메인과 일치하는지 확인 |
| Recommendation Count | 추천 결과 수가 기대 범위에 있는지 확인 |
| No Expired Recommendations | `deadline_status=expired` 또는 `is_expired=true` 추천 여부 확인 |
| ReAct Trace Presence | `tool_trace`가 존재하고 주요 노드 흐름이 기록되는지 확인 |
| Internal Search Sufficiency | `internal_search_sufficient`가 케이스 기대값과 일치하는지 확인 |
| Next Action | `next_action`이 `answer_generation` 또는 `external_search`로 적절히 설정되는지 확인 |
| External Search Plan | `external_search_status`, `external_search_targets`, `external_search_queries`가 적절한지 확인 |

### 4.2 BLEU/ROUGE 평가

각 케이스의 `reference_answer`와 실제 `answer`를 비교하여 다음 값을 계산한다.

| 지표 | 설명 |
|---|---|
| BLEU | n-gram precision 기반 답변 유사도 참고 지표 |
| ROUGE-1 F1 | unigram overlap 기반 유사도 |
| ROUGE-2 F1 | bigram overlap 기반 유사도 |
| ROUGE-L F1 | LCS 기반 문장 구조 유사도 |

단, 본 서비스는 정책 추천형 RAG이므로 BLEU/ROUGE는 보조 지표로 사용한다. 같은 정책을 올바르게 추천하더라도 표현 방식이 다르면 BLEU/ROUGE가 낮게 나올 수 있으므로, 최종 품질 판단은 규칙 기반 평가 및 LLM-as-a-Judge 결과와 함께 해석한다.

### 4.3 LLM-as-a-Judge 평가

`--write-judge-inputs` 옵션을 사용하면 `evaluation/result/judge_inputs.jsonl`이 생성된다.  
LLM Judge는 다음 항목을 1~5점으로 평가하도록 설계하였다.

| 항목 | 평가 내용 |
|---|---|
| Context Relevance | 검색/추천 결과가 질문 조건과 관련 있는가 |
| Groundedness | 답변이 응답 JSON의 근거에 기반하는가 |
| Answer Relevance | 사용자 질문 및 reference_answer와 의미적으로 부합하는가 |
| Freshness Safety | 마감/과거 공고를 부적절하게 추천하지 않는가 |
| ReAct Trace Quality | tool_trace와 next_action이 결과와 일관되는가 |
| Reference Alignment | 기준 답변의 핵심 기대 내용과 일치하는가 |

## 5. 실행 방법

```bash
python evaluation/evaluate_rag.py \
  --dataset evaluation/evaluation_dataset.jsonl \
  --base-url http://127.0.0.1:8000 \
  --endpoint /chat \
  --write-judge-inputs
```

API 라우터가 `/api/chat`인 경우:

```bash
python evaluation/evaluate_rag.py \
  --dataset evaluation/evaluation_dataset.jsonl \
  --base-url http://127.0.0.1:8000 \
  --endpoint /api/chat \
  --write-judge-inputs
```

## 6. 생성 산출물

| 파일 | 설명 |
|---|---|
| `evaluation/result/evaluation_results.json` | 케이스별 상세 평가 결과 및 원본 응답 JSON |
| `evaluation/result/evaluation_results.md` | 평가 결과 요약표 |
| `evaluation/result/judge_inputs.jsonl` | LLM-as-a-Judge 입력 프롬프트 |

## 7. 결과 요약

> 아래 항목은 평가 실행 후 `evaluation/result/evaluation_results.md` 내용을 기반으로 채운다.

- 총 케이스 수: 
- 통과 케이스 수: 
- 통과율: 
- 평균 규칙 기반 점수: 
- 평균 BLEU: 
- 평균 ROUGE-1 F1: 
- 평균 ROUGE-2 F1: 
- 평균 ROUGE-L F1: 

## 8. 주요 검증 결과

### 8.1 오래된 정책/마감 공고 추천 방지

- `deadline_status=expired` 또는 `is_expired=true`인 항목이 최신성 질문에서 추천되지 않는지 확인하였다.
- 과거 공고 제외 질문에서 2016~2019년 마감 공고가 답변에 포함되지 않는지 확인하였다.

### 8.2 ReAct 기반 분기 검증

- 내부 검색 결과가 충분한 경우 `next_action=answer_generation`으로 이동하는지 확인하였다.
- 내부 검색 결과가 모두 마감이거나 부족한 경우 `next_action=external_search`로 분기하는지 확인하였다.
- 외부 API는 아직 실제 호출하지 않지만 `external_search_status=planned_not_executed`와 공식 출처 대상이 기록되는지 확인하였다.

### 8.3 Groundedness 검증

- 답변에 포함된 정책명, 신청 기간, 마감 여부, 출처 URL이 recommendations의 필드에 기반하는지 확인하였다.
- 내부 데이터에서 찾지 못한 경우 임의 정책을 생성하지 않고 no-result 답변을 반환하는지 확인하였다.

## 9. 한계 및 개선 방향

- BLEU/ROUGE는 생성 답변의 문장 표현 차이에 민감하므로 정책 추천 정확도를 직접 대변하지 않는다.
- 외부 공식 출처 검색은 현재 계획 생성 단계이며, 추후 K-Startup/온통청년/고용24 API 또는 MCP Tool로 교체할 수 있다.
- 향후 정답 정책 ID 기반 Top-k Hit Rate를 추가하면 검색 품질을 더 정량적으로 측정할 수 있다.
- LLM-as-a-Judge 자동 실행까지 연결하면 Groundedness와 Answer Relevance를 반복적으로 추적할 수 있다.
