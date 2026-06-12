# RAG/LLM 평가 보고서 템플릿

## 1. 평가 목적

본 평가는 청년 정책 통합 탐색 에이전트의 RAG 검색 품질, 답변 근거성, 최신성 안전성, ReAct 워크플로우 동작 여부를 확인하기 위해 수행한다.

## 2. 평가 대상

- 대상 API: `/chat` 또는 `/api/chat`
- 대상 기능:
  - 사용자 조건 추출
  - 도메인/source_category 라우팅
  - Vector DB 검색
  - 정책/창업공고/교육훈련 추천
  - 마감 공고 필터링
  - Result Sufficiency Checker
  - 외부 공식 출처 fallback 계획 노드

## 3. 평가 데이터셋

평가 질의셋은 `evaluation_dataset.jsonl`에 정의한다.

주요 케이스는 다음과 같다.

| 유형 | 예시 | 검증 목적 |
|---|---|---|
| 정상 추천 | 2026년에 신청 가능한 창업지원 공고 추천 | open 공고 추천, 마감 공고 제외 |
| 과거 공고 제외 | 2019년에 했던 사업 말고 지금 신청 가능한 공고 | 오래된 공고 추천 방지 |
| ReAct fallback | 화성 청년 우주창업 지원금 | 불충분 검색 결과 차단, 외부 공식 출처 계획 |
| 주거 정책 | 서울 25세 월세 지원 | 주거 라우팅 및 조건 반영 |
| 교육훈련 | 국민내일배움카드 AI 데이터 분석 훈련 | training 데이터 라우팅 |
| 일자리 | 면접수당 정책 | 일자리/정책 라우팅 |
| 금융 | 청년도약계좌 | 금융 라우팅 |
| 참여권리 | 청년 참여위원회 | 참여권리 라우팅 |

## 4. 자동 평가 지표

`evaluate_rag.py`는 다음 항목을 규칙 기반으로 확인한다.

| 지표 | 설명 |
|---|---|
| route match | 기대 도메인과 실제 route 일치 여부 |
| next_action match | answer_generation/external_search 분기 적절성 |
| recommendation count | 기대 추천 개수 범위 충족 여부 |
| freshness safety | 마감 공고가 추천에 포함되지 않았는지 여부 |
| keyword check | 답변/응답 JSON에 필수 키워드 포함 여부 |
| forbidden keyword check | 오래된 연도/부적절한 공고명 포함 여부 |
| ReAct trace | tool_trace가 존재하고 단계가 기록되는지 여부 |
| external search plan | fallback 시 공식 출처 target/query가 생성되는지 여부 |

## 5. LLM-as-a-Judge 평가 지표

LLM Judge는 다음 5개 항목을 1~5점으로 평가한다.

| 항목 | 설명 |
|---|---|
| Context Relevance | 검색/추천 결과가 질문 도메인과 조건에 맞는가 |
| Groundedness | 답변이 recommendations/source_url/deadline_status에 기반하는가 |
| Answer Relevance | 사용자 질문에 직접 답하는가 |
| Freshness Safety | 마감/과거 공고를 부적절하게 추천하지 않는가 |
| ReAct Trace Quality | tool_trace와 next_action이 결과와 일관되는가 |

## 6. 실행 방법

```bash
cd <프로젝트 루트>
python evaluation/evaluate_rag.py --base-url http://127.0.0.1:8000 --endpoint /chat --write-judge-inputs
```

API prefix가 `/api/chat`이면 다음처럼 실행한다.

```bash
python evaluation/evaluate_rag.py --base-url http://127.0.0.1:8000 --endpoint /api/chat --write-judge-inputs
```

## 7. 결과 기록

| 날짜 | 평가 케이스 수 | 통과 수 | 통과율 | 주요 실패 원인 | 개선 내용 |
|---|---:|---:|---:|---|---|
| YYYY-MM-DD | 10 | - | - | - | - |

## 8. 대표 검증 사례

### 8.1 정상 open 공고 추천

- 질문: `2026년에 신청 가능한 창업지원 공고 추천해줘`
- 기대 결과:
  - `internal_search_sufficient = true`
  - `next_action = answer_generation`
  - `external_used = false`
  - `recommendations[].deadline_status != expired`

### 8.2 ReAct fallback

- 질문: `화성에서 받을 수 있는 청년 우주창업 지원금 알려줘`
- 기대 결과:
  - `internal_search_sufficient = false`
  - `next_action = external_search`
  - `external_search_status = planned_not_executed`
  - `external_search_targets = ["K-Startup"]`
  - `recommendations = []`

## 9. 개선 전후 비교

| 항목 | 개선 전 | 개선 후 |
|---|---|---|
| 마감 공고 처리 | 2016~2019년 공고가 답변에 포함될 수 있음 | expired 결과를 추천 후보에서 제외 |
| 검색 부족 판단 | 검색 결과가 있으면 그대로 답변 | Result Sufficiency Checker로 충분성 판단 |
| 외부 검색 분기 | 없음 | 공식 출처 fallback 계획 노드로 분기 |
| 추적 가능성 | 최종 답변 중심 | tool_trace로 router/retriever/checker/external_search 흐름 확인 |

## 10. 결론

본 시스템은 내부 Vector DB 검색 결과의 충분성을 판단한 뒤, 충분한 경우에만 답변을 생성한다. 검색 결과가 모두 마감되었거나 내부 근거가 부족한 경우에는 추천을 생성하지 않고 외부 공식 출처 검색 계획으로 분기한다. 이를 통해 오래된 정책 추천과 근거 부족 답변을 줄이고, 평가 기준의 ReAct 및 Groundedness 요구사항에 대응한다.
