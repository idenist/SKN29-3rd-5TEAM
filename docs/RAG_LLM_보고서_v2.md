# RAG/LLM 보고서 v2

## 1. 작업 개요

본 문서는 청년 정책 통합 탐색 에이전트 프로젝트에서 RAG/LLM 담당자가 수행한 백엔드 핵심 파이프라인 구현 내용을 정리한 v2 보고서이다.

v1 보고서에서는 온통청년 정책 데이터 중심의 RAG 파이프라인을 정리하였다. v2에서는 이후 수행한 통합 데이터 확장, `source_category` 기반 라우팅, 교육훈련/창업공고 대응, 창업공고 마감 상태 처리, 프론트 필터링을 위한 응답 필드 보강 내용을 추가로 반영하였다.

최종 목표는 사용자의 자연어 질문을 입력받아 청년 정책, 창업지원 공고, 교육훈련 과정을 통합 검색하고, 사용자 조건과 지원 항목 조건을 비교한 뒤, 신청/참여 가능성과 유의사항을 포함한 최종 답변을 생성하는 것이다.

---

## 2. 전체 RAG/LLM 파이프라인 구조

최종 파이프라인은 다음과 같다.

```text
사용자 질문
↓
Input Validator
↓
Condition Extractor
↓
Router
↓
Retriever
↓
Eligibility Checker
↓
Answer Generator
↓
FastAPI / Streamlit 응답 활용
```

| 단계 | 주요 역할 |
| --- | --- |
| Input Validator | 사용자 질문 공백 여부, 짧은 질문 여부 확인 |
| Condition Extractor | 나이, 지역, 고용 상태, 관심 도메인, 키워드 추출 |
| Router | 질문 의도에 따라 도메인과 데이터 유형 결정 |
| Retriever | Chroma Vector DB에서 관련 지원 항목 검색 |
| Eligibility Checker | 사용자 조건과 지원 항목 조건 비교 |
| Answer Generator | 검색 결과와 자격 판단 결과 기반 최종 답변 생성 |
| FastAPI / Streamlit | 응답 전달, 화면 표시, 필터링, 사용자 인터랙션 처리 |

---

## 3. 데이터 확장 및 통합 구조

### 3.1 기존 데이터

초기 데이터는 온통청년 정책 중심이었다.

```text
정책 수: 2,611개
chunk 수: 9,758개
기존 Chroma collection: youth_policy_chunks
```

기존 chunk는 `policy_id`, `policy_name`, `domain`, `content`, `source_url`, `application_url`, `info_score`, `needs_detail_check` 중심 구조였다.

### 3.2 확장 데이터

정책 수가 적어 서비스가 가벼워 보일 수 있다는 의견에 따라 정책 외 데이터까지 확장하였다.

```text
opportunities.json: 26,803건
opportunity_chunks.jsonl: 33,950 chunks

source_category별 구성:
- policy: 2,611개 온통청년 정책
- startup_notice: 3,789개 K-Startup 창업공고
- training: 20,403개 HRD/고용24 교육훈련 과정
```

통합 chunk 구조는 다음과 같다.

```json
{
  "chunk_id": "...",
  "item_id": "...",
  "source_category": "training",
  "domain": "education",
  "title": "...",
  "content": "...",
  "metadata": {
    "source_url": "...",
    "application_url": "...",
    "info_score": 80,
    "needs_detail_check": true
  }
}
```

### 3.3 기존 코드 호환 alias

기존 정책 중심 코드와의 호환성을 위해 다음 alias를 유지하였다.

| 통합 필드 | 기존 호환 필드 |
| --- | --- |
| `item_id` | `policy_id` |
| `title` | `policy_name` |
| `content` | `text` |
| `source_category` | 신규 필드 |

---

## 4. Vector DB 구축

### 4.1 기존 정책 Vector DB

기존 정책 전용 Vector DB는 다음 collection으로 구축하였다.

```text
collection_name: youth_policy_chunks
embedding_model: text-embedding-3-small
persist_dir: data/vector_db
```

### 4.2 통합 지원 정보 Vector DB

확장 데이터 적용 후에는 `opportunity_chunks.jsonl`을 사용하여 통합 Vector DB를 구축하였다.

```text
입력 파일: data/processed/opportunity_chunks.jsonl
collection_name: youth_opportunity_chunks
검색 대상 필드: content
주요 metadata: item_id, title, source_category, domain, source_url, application_url
```

기존 코드 호환을 위해 다음 필드를 함께 저장하였다.

```text
policy_id = item_id
policy_name = title
item_id
title
source_category
domain
source_url
application_url
```

### 4.3 OpenAI Embedding RateLimit 대응

통합 데이터 임베딩 중 OpenAI Embedding API의 TPM 제한으로 429 RateLimitError가 발생하였다. 이는 코드 오류가 아니라 API 사용량 제한에 의한 문제였다.

대응 방향은 다음과 같다.

```text
batch_size를 30~50 수준으로 낮춤
실패 시 retry/backoff 적용
이미 구축한 Vector DB가 있으면 --reset 반복 실행 지양
개발 중에는 sample DB 또는 use_llm=False 테스트 활용
```

---

## 5. Retriever 구현 및 통합 데이터 대응

### 5.1 구현 파일

```text
backend/services/rag_service.py
backend/db/vector_store.py
```

### 5.2 주요 기능

Retriever는 Vector DB 검색 결과를 사용자 조건에 맞게 필터링하고, 지원 항목 단위로 정리한다.

```text
query 기반 Chroma 검색
사용자 나이/지역 필터링
domain 필터링
source_category 필터링
동일 item_id/policy_id 기준 중복 제거
score, info_score, needs_detail_check 기반 rerank
창업공고 deadline_status 계산
검색 결과 compact format 변환
Answer Generator용 context 문자열 생성
```

### 5.3 source_category 보존

통합 데이터 적용 중 Router가 `source_category=training`을 생성해도 Retriever 결과 metadata에서 `source_category`가 보존되지 않는 문제가 있었다.

이를 해결하기 위해 `_normalize_filters`, `_filter_by_source_category`, `_compact_result`에서 `source_category`를 명시적으로 보존하였다.

최종 compact result에는 다음 필드가 포함된다.

```text
item_id
title
policy_id
policy_name
source_category
domain
score
text
metadata
source_url
application_url
info_score
needs_detail_check
```

### 5.4 창업공고 마감 상태 처리

창업지원 공고 검색에서 오래된 마감 공고가 상위에 노출되는 문제가 있었다. 이를 해결하기 위해 Retriever 단계에서 신청/접수 종료일을 파싱하여 다음 필드를 추가하였다.

```text
deadline_rank
deadline_status
application_end_date
is_expired
```

값의 의미는 다음과 같다.

| 값 | 의미 |
| --- | --- |
| `deadline_status = open` | 아직 마감 전인 창업공고 |
| `deadline_status = expired` | 이미 마감된 창업공고 |
| `deadline_status = unknown` | 마감일 확인 불가 |
| `is_expired = true` | 마감된 창업공고 |
| `application_end_date` | 파싱된 신청/접수 종료일 |

마감일 파싱은 다음 형태를 처리한다.

```text
2025년 6월 19일
2025-06-19
2025.06.19
2025/06/19
3/21~4/9 11:00
03.21~04.09
```

제목에만 기간이 있는 경우를 처리하기 위해 `title + text`를 함께 검사하도록 수정하였다.

### 5.5 마감 공고 정렬 정책

백엔드에서 마감 공고를 무조건 삭제하지 않고, 프론트에서 필터링할 수 있도록 마감 상태만 태깅한다.

정렬 우선순위는 다음과 같다.

```text
1. 마감 전 공고(open)
2. 마감일 확인 불가 공고(unknown)
3. 마감된 공고(expired)
```

최종 테스트 결과 예시는 다음과 같다.

```text
1 [창업] 내 아이디어로 창업 가능할까? | startup_notice | open | 2026-06-17
2 2025년도 기술기반 예비창업가 사업화자금지원 추가 모집공고 | startup_notice | expired | 2025-06-19
3 [창업특강] 문화예술창업: 재도전과 성공전략 | startup_notice | expired | 2023-07-25
4 「창의적 지식재산(디자인) 사업화 지원사업」 예비창업자(팀) 모집공고 | startup_notice | expired | 2019-06-07
5 (한국에너지공단) 기술혁신형 창업기업 지원사업 (예비)창업자 모집(연장) | startup_notice | expired | 2018-08-30
```

---

## 6. Condition Extractor

### 6.1 구현 파일

```text
backend/services/condition_extractor.py
backend/graph/prompts.py
```

### 6.2 추출 대상

조건 추출기는 사용자 자연어 질문에서 다음 정보를 추출한다.

```json
{
  "age": 25,
  "region": "서울",
  "income": null,
  "employment_status": "취업준비생",
  "company_type": null,
  "education_status": null,
  "major": null,
  "interest_domain": "교육",
  "keywords": ["K-Digital Training", "데이터 분석", "개발자", "교육 과정"],
  "region_code": "11000"
}
```

### 6.3 주요 기능

```text
OpenAI Chat Completion 기반 조건 추출
JSON parsing 실패 시 repair prompt 적용
최종 fallback rule-based extraction 적용
지역명에서 region_code 변환
관심 분야를 retriever용 domain filter로 변환
keywords를 검색 query에 보강
```

---

## 7. Router 및 source_category 분기

### 7.1 구현 파일

```text
backend/graph/nodes.py
backend/graph/workflow.py
```

### 7.2 도메인 라우팅

Router는 질문과 조건을 보고 다음 도메인 중 하나를 결정한다.

```text
일자리
주거
교육
복지문화
참여권리
금융
창업
기타
전체
```

### 7.3 source_category 라우팅

통합 데이터 대응을 위해 도메인 외에도 데이터 출처 유형을 판단한다.

```text
국비지원, 국민내일배움카드, K-Digital, KDT, 훈련과정, 부트캠프
→ training

창업공고, 창업지원사업, 사업화, 예비창업자, K-Startup, IR, 투자유치
→ startup_notice

정책, 수당, 지원금, 장려금, 월세, 전세, 청년도약계좌, 청년수당
→ policy
```

### 7.4 테스트 결과

```text
K-Digital Training 데이터 분석 개발자 교육 과정 추천해줘
→ route: 교육
→ source_category: training

청년 예비창업자 사업화 지원사업 알려줘
→ route: 창업
→ source_category: startup_notice

서울에 사는 25세 청년 월세 지원 정책 알려줘
→ route: 주거
→ source_category: policy
```

---

## 8. Eligibility Checker

### 8.1 구현 파일

```text
backend/services/policy_matcher.py
```

### 8.2 판단 등급

```text
가능성 높음
추가 확인 필요
가능성 낮음
```

### 8.3 판단 원칙

```text
연령 조건은 age_min, age_max로 우선 판단
지역 조건은 region_code 기반으로 판단
시도 코드와 시군구 코드는 prefix 기반으로 매칭
소득 조건은 명확히 확인 가능한 경우에만 판단
데이터에 없는 조건은 추가 확인 필요로 분류
불충족 조건이 있으면 가능성 낮음으로 분류
```

### 8.4 item_type_label 적용

`source_category`에 따라 항목 유형명을 다르게 표시하도록 수정하였다.

```python
def _get_item_type_label(source_category: str) -> str:
    if source_category == "training":
        return "교육훈련 과정"
    if source_category == "startup_notice":
        return "창업지원 공고"
    if source_category == "policy":
        return "정책"
    return "지원 정보"
```

이에 따라 기존 정책 중심 문구를 다음과 같이 개선하였다.

```text
전국 대상 정책
→ 전국 대상 창업지원 공고 / 교육훈련 과정 / 정책

검색된 정책 chunk
→ 검색된 창업지원 공고 chunk / 교육훈련 과정 chunk / 정책 chunk

정책 본문
→ 창업지원 공고 본문 / 교육훈련 과정 본문 / 정책 본문

정책 연령 조건
→ 창업지원 공고 연령 조건 / 교육훈련 과정 연령 조건 / 정책 연령 조건
```

### 8.5 출력 예시

```text
1 2025년 아이디어 사업화 지원사업 예비창업자 모집 공고(3/21~4/9 11:00)
| startup_notice
| 추가 확인 필요
| ['지역 조건 충족: 전국 대상 창업지원 공고',
   '소득 조건: 검색된 창업지원 공고 chunk에서 명확한 소득 제한을 확인하지 못함',
   "고용 상태 조건 충족 가능성: 창업지원 공고 본문에 '창업자' 관련 표현이 있음"]
| ['창업지원 공고 연령 조건이 구조화되어 있지 않아 확인 필요']
```

---

## 9. Answer Generator

### 9.1 구현 파일

```text
backend/services/answer_generator.py
backend/graph/prompts.py
```

### 9.2 답변 포함 항목

```text
항목명
항목 유형
추천 이유
신청/참여 가능성
충족 조건
추가 확인이 필요한 조건
주요 내용
신청/접수 기간 또는 훈련 기간
신청/접수 방법
제출 서류
출처 URL
신청 URL
유의사항
```

### 9.3 통합 데이터 대응

기존 Answer Generator는 정책 중심 표현을 사용하였다. 통합 데이터 적용 후 다음 필드를 추가하였다.

```text
item_id
title
source_category
item_type_label
training_period
training_institution
training_target
training_cost
region
raw_text_excerpt
```

training 데이터는 다음 한글 필드를 인식한다.

```text
훈련과정명
훈련기관
훈련유형
훈련대상
지역
훈련기간
훈련비/지원정보
NCS코드
상세URL
```

startup_notice 데이터는 다음 한글 필드를 인식한다.

```text
공고명
분야
지원사업분류
요약
신청대상
신청기간
신청방법
접수기간
모집기간
제출서류
구비서류
문의처
기관명
주관기관
```

### 9.4 HTML 및 중복 제거

교육훈련 데이터에 포함된 HTML 태그가 답변에 노출되는 문제가 있었다. 이를 해결하기 위해 다음 처리를 추가하였다.

```text
HTML 태그 제거
중복 줄 제거
raw_text_excerpt 정리
training/startup_notice의 support_content fallback 처리
```

### 9.5 LLM no-result 문구 방어

검색 결과가 있는데도 LLM 답변 마지막에 다음 문구가 붙는 문제가 있었다.

```text
제공된 데이터에서 조건에 맞는 정책을 찾지 못했습니다.
```

이를 방지하기 위해 `generate_answer_with_llm()` 후처리에서 no-result 문구를 제거하였다.

---

## 10. LangGraph Workflow 및 통합 테스트

### 10.1 구현 파일

```text
backend/graph/nodes.py
backend/graph/workflow.py
```

### 10.2 GraphState

```python
class GraphState(TypedDict, total=False):
    user_query: str
    top_k: int
    use_llm: bool

    user_conditions: dict[str, Any]
    route: str
    route_reason: str
    filters: dict[str, Any]
    retriever_query: str
    retrieved_chunks: list[dict[str, Any]]
    eligibility_results: list[dict[str, Any]]

    answer: str
    warnings: list[str]
    errors: list[str]
```

### 10.3 top_k 및 use_llm 제어

개발 비용을 줄이기 위해 `use_llm` 값을 workflow state로 전달할 수 있도록 하였다.

```python
run_rag_workflow(
    query="K-Digital Training 데이터 분석 개발자 교육 과정 추천해줘",
    return_full_state=False,
    top_k=5,
    use_llm=False
)
```

### 10.4 통합 테스트 결과

#### 교육훈련

```text
질문: 국민내일배움카드 AI 데이터 분석 훈련 과정 추천해줘
route: 교육
source_category: training
errors: []
```

#### 창업지원 공고

```text
질문: 청년 예비창업자 사업화 지원사업 알려줘
route: 창업
source_category: startup_notice
errors: []
```

#### 정책

```text
질문: 서울에 사는 25세 청년 월세 지원 정책 알려줘
route: 주거
source_category: policy
errors: []
```

세 가지 데이터 유형 모두 전체 workflow에서 정상 흐름을 확인하였다.

```text
training 정상
startup_notice 정상
policy 정상
source_category 분기 정상
deadline_status / application_end_date 생성 정상
errors 없음
```

---

## 11. FastAPI 및 Streamlit 연동 준비

### 11.1 현재 상태

현재 RAG/LLM 핵심 로직은 정상 동작하며, 이후 주요 작업은 FastAPI 응답 구조 확인과 Streamlit 화면 표시 및 필터링이다.

workflow 반환 필드는 다음과 같다.

```text
answer
user_conditions
route
route_reason
recommendations
warnings
errors
```

recommendations 내부에는 다음 필드가 포함된다.

```text
title / policy_name
source_category
eligibility
matched_conditions
missing_conditions
cautions
source_url
application_url
deadline_status
application_end_date
is_expired
```

### 11.2 FastAPI 확인 사항

FastAPI `/api/chat` 응답에서 다음 필드가 유지되는지 확인해야 한다.

```text
answer
route
route_reason
recommendations
warnings
errors
recommendations[].deadline_status
recommendations[].application_end_date
recommendations[].is_expired
```

### 11.3 Streamlit 필터링 방향

프론트에서는 창업공고 마감 여부를 다음과 같이 필터링할 수 있다.

```python
show_expired = st.checkbox("마감된 공고 포함", value=False)

if not show_expired:
    recommendations = [
        item for item in recommendations
        if item.get("deadline_status") != "expired"
    ]
```

데이터 유형 필터는 `source_category`를 기준으로 구현한다.

```text
전체
정책
창업지원 공고
교육훈련 과정
```

매핑은 다음과 같다.

```text
policy → 정책
startup_notice → 창업지원 공고
training → 교육훈련 과정
```

---

## 12. 이슈 및 해결 내역

### 12.1 날짜가 연령으로 파싱되는 문제

```text
문제: application_period_text의 날짜 숫자가 age_min, age_max로 잘못 파싱됨
해결: age_text 라인에서만 연령 파싱하도록 수정
```

### 12.2 OpenAI Embedding RateLimit

```text
문제: 통합 데이터 임베딩 중 429 RateLimitError 발생
해결: batch_size 축소, retry/backoff 적용, 반복 reset 지양
```

### 12.3 source_category 누락

```text
문제: Router가 source_category를 생성해도 Retriever 결과에서 보존되지 않음
해결: _normalize_filters, _compact_result에서 source_category 보존
```

### 12.4 training 답변이 정책처럼 표현되는 문제

```text
문제: 교육훈련 검색 결과가 정책 목록처럼 표현됨
해결: item_type_label, training 필드 추출, 훈련 기간/기관/대상/비용 분리 출력
```

### 12.5 창업공고 오래된 결과 노출

```text
문제: startup_notice 검색 결과에 2018년, 2019년, 2023년 마감 공고가 상위 노출됨
해결: deadline_status, application_end_date, is_expired 추가 및 open 우선 정렬
```

### 12.6 _rerank_results return 누락

```text
문제: non_expired가 3개 미만이면 _rerank_results가 None 반환
해결: 함수 마지막에 return ranked 추가
```

### 12.7 RequestsDependencyWarning

```text
문제: RequestsDependencyWarning: Unable to find acceptable character detection dependency
해결: pip install charset-normalizer
비고: 기능 실행에는 영향 없음
```

---

## 13. 최종 산출물

### 13.1 신규 및 수정 파일

```text
scripts/convert_chunks_for_chroma_v2.py
scripts/build_vector_db.py
scripts/build_opportunity_vector_db.py

backend/db/vector_store.py

backend/services/rag_service.py
backend/services/condition_extractor.py
backend/services/policy_matcher.py
backend/services/answer_generator.py

backend/graph/prompts.py
backend/graph/nodes.py
backend/graph/workflow.py
```

FastAPI 및 Streamlit 연동 단계에서 추가 확인 또는 수정이 필요한 파일은 다음과 같다.

```text
backend/api/chat.py
backend/main.py
frontend 또는 streamlit app 파일
```

### 13.2 생성 데이터

```text
data/processed/chunks_for_chroma.jsonl
data/processed/chunks_for_chroma_report.json
data/processed/opportunity_chunks.jsonl
data/processed/opportunities.json
data/vector_db/
```

### 13.3 Chroma Collection

```text
기존 정책 전용 collection:
youth_policy_chunks

통합 지원 정보 collection:
youth_opportunity_chunks
```

---

## 14. 현재 완성된 기능

```text
사용자 자연어 질문 입력
조건 추출
도메인 라우팅
source_category 라우팅
정책/창업공고/교육훈련 통합 검색
연령/지역/고용상태/소득 조건 기반 신청/참여 가능성 판단
교육훈련 과정 필드 분리 출력
창업공고 마감 상태 계산
LLM 기반 최종 답변 생성
rule-based fallback 답변 생성
결측 필드 안내
출처 URL 및 신청 URL 제공
LangGraph Workflow 통합 실행
프론트 필터링을 위한 deadline_status 제공
```

---

## 15. 남은 작업 및 개선 사항

### 15.1 FastAPI 응답 구조 최종 확인

FastAPI `/api/chat` 응답에서 다음 필드가 누락되지 않는지 확인한다.

```text
recommendations[].deadline_status
recommendations[].application_end_date
recommendations[].is_expired
recommendations[].source_category
recommendations[].eligibility
```

### 15.2 Streamlit 화면 구현

Streamlit에서 다음 기능을 구현한다.

```text
질문 입력
답변 출력
추천 항목 카드 표시
정책/창업지원 공고/교육훈련 과정 유형 필터
마감된 공고 포함 여부 체크박스
출처 URL 버튼
신청 URL 버튼
```

### 15.3 마감 공고 필터링

기본값은 마감된 공고를 숨기는 방향을 추천한다.

```text
기본: deadline_status != expired
옵션: 마감된 공고 포함
```

### 15.4 정책 도메인 정밀도 개선

월세 정책 질문에서 일부 주거 관련성이 약한 policy 결과가 섞이는 문제가 있었다.

개선 방향:

```text
domain rerank 강화
질문 키워드 기반 rerank 추가
월세/주거/임대/보증금 키워드 가중치 추가
```

### 15.5 중복 결과 처리

교육훈련 과정의 경우 동일 과정명이 다른 회차로 여러 번 노출될 수 있다.

개선 방향:

```text
동일 과정 다른 회차는 프론트에서 묶어서 표시
필요 시 title 정규화 기반 중복 제거 옵션 추가
```

---

## 16. 결론

본 작업을 통해 청년 정책 추천 서비스의 RAG/LLM 핵심 파이프라인을 통합 지원 정보 탐색 구조로 확장하였다.

초기에는 온통청년 정책 데이터 중심의 검색 파이프라인을 구축하였으나, 이후 정책 수가 적어 서비스가 가벼워 보일 수 있다는 문제를 해결하기 위해 창업지원 공고와 교육훈련 과정 데이터를 함께 통합하였다. 이를 위해 기존 `policy_id`, `policy_name` 중심 구조를 `item_id`, `title`, `source_category` 기반 구조로 확장하되, 기존 코드와의 호환을 위해 alias를 유지하였다.

또한 Router에서 도메인뿐 아니라 `source_category`를 함께 판단하도록 개선하여 사용자의 질문이 정책, 창업지원 공고, 교육훈련 과정 중 어떤 데이터 유형을 원하는지 구분할 수 있게 하였다. Retriever는 이 정보를 바탕으로 Chroma Vector DB에서 관련 항목을 검색하고, Eligibility Checker는 source_category에 따라 정책, 창업지원 공고, 교육훈련 과정에 맞는 문구로 신청/참여 가능성을 판단한다.

Answer Generator는 기존 정책 중심 답변에서 벗어나 교육훈련 과정의 훈련기간, 훈련기관, 훈련대상, 훈련비 등의 필드를 별도로 출력하도록 개선하였다. 창업공고에 대해서는 신청/접수 종료일을 파싱하여 `deadline_status`, `application_end_date`, `is_expired`를 제공함으로써 프론트에서 마감 공고를 필터링할 수 있는 기반을 마련하였다.

현재 시스템은 다음 흐름을 정상적으로 수행한다.

```text
사용자 질문
→ 조건 추출
→ 도메인 및 source_category 라우팅
→ 정책/창업공고/교육훈련 통합 검색
→ 신청/참여 가능성 판단
→ 최종 답변 생성
→ deadline_status 포함 결과 반환
```

따라서 RAG/LLM 백엔드 핵심 기능은 시연 가능한 수준으로 완성되었으며, 이후 주요 작업은 FastAPI 응답 구조 확인과 Streamlit 화면 구현 및 필터링 적용이다.
