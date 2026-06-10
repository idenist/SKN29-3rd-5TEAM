# RAG/LLM 보고서

## 1. 작업 개요

본 문서는 청년 정책 통합 탐색 에이전트 프로젝트에서 RAG/LLM 담당자가 수행한 백엔드 핵심 파이프라인 구현 내용을 정리한 보고서이다.

프로젝트의 목표는 사용자의 자연어 질문을 입력받아 청년 정책 데이터를 검색하고, 사용자 조건과 정책 조건을 비교한 뒤, 신청 가능성과 유의사항을 포함한 최종 답변을 생성하는 것이다.

구현 흐름은 다음과 같다.

```text
정책 chunk 전처리
→ Vector DB 구축
→ Retriever 구현
→ 조건 추출기 구현
→ Router 구현
→ Eligibility Checker 구현
→ Answer Generator 구현
→ LangGraph Workflow 구성
→ FastAPI /api/chat 연동
```

---

## 2. 전체 RAG/LLM 파이프라인 구조

최종적으로 구성한 RAG/LLM 파이프라인은 다음과 같다.

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
FastAPI ChatResponse 반환
```

각 단계의 역할은 다음과 같다.

| 단계 | 주요 역할 |
| --- | --- |
| Input Validator | 사용자 질문 공백 여부, 짧은 질문 여부 확인 |
| Condition Extractor | 나이, 지역, 고용 상태, 관심 도메인 등 사용자 조건 추출 |
| Router | 질문과 조건을 바탕으로 정책 도메인 결정 |
| Retriever | Chroma Vector DB에서 관련 정책 Top-k 검색 |
| Eligibility Checker | 사용자 조건과 정책 조건 비교 |
| Answer Generator | 검색 결과와 자격 판단 결과 기반 최종 답변 생성 |
| FastAPI Adapter | LangGraph 결과를 ChatResponse 스키마로 변환 |

---

## 3. 4.1 정책 chunk 구조 확인 및 Chroma 입력 포맷 변환

### 3.1 기존 chunk 구조

초기 `chunks.jsonl` 데이터는 다음과 같은 구조를 가지고 있었다.

```json
{
  "chunk_id": "...::summary",
  "policy_id": "...",
  "policy_name": "...",
  "domain": "...",
  "section": "summary",
  "content": "...",
  "source_url": "...",
  "application_url": "...",
  "needs_detail_check": true,
  "info_score": 90
}
```

Chroma에 효율적으로 저장하기 위해 다음과 같은 구조로 변환이 필요했다.

```json
{
  "id": "policy_id::section",
  "text": "검색 대상 본문",
  "metadata": {
    "policy_id": "...",
    "policy_name": "...",
    "domain": "...",
    "age_min": 19,
    "age_max": 39,
    "region_code": "11000",
    "source_url": "...",
    "info_score": 90,
    "needs_detail_check": true
  }
}
```

### 3.2 주요 변환 내용

수행한 변환 작업은 다음과 같다.

- `content` 필드를 Chroma 검색용 `text` 필드로 변환
- 정책 메타데이터를 `metadata` 객체로 정리
- `age_text` 기반으로 `age_min`, `age_max` 추출
- `region_code`를 정책 단위로 전파
- `source_url`, `application_url`, `domain`, `info_score`, `needs_detail_check` 보존
- Chroma에서 허용하는 메타데이터 타입으로 정규화

### 3.3 변환 중 발견한 문제와 수정

초기 변환 과정에서 `application_period_text: 20260622 ~ 20261231`과 같은 날짜 값이 연령으로 잘못 파싱되는 문제가 있었다.

예를 들어 날짜의 `22`, `20`이 각각 `age_min`, `age_max`로 오인되는 문제가 발생하였다.

이를 해결하기 위해 다음 기준으로 파싱 로직을 수정하였다.

```text
age_text 라인이 존재할 때만 연령 파싱
정책 본문 전체에서 임의로 숫자를 스캔하지 않음
정책 단위 profile을 만든 뒤 동일 policy_id의 chunk에 전파
```

### 3.4 최종 변환 결과

최종 변환 결과는 다음과 같다.

```json
{
  "total_count": 9758,
  "success_count": 9758,
  "error_count": 0,
  "parse_error_count": 0,
  "validation_error_count": 0,
  "empty_region_code_count": 0,
  "unknown_age_count": 4355,
  "invalid_age_range_count": 0,
  "policy_profile_count": 2611,
  "policy_with_age_count": 1456,
  "policy_with_region_count": 2611
}
```

최종적으로 `chunks_for_chroma.jsonl`을 생성하여 Chroma Vector DB 구축에 사용할 수 있는 상태로 만들었다.

---

## 4. 4.2 Vector DB 구축

### 4.1 구현 파일

```text
backend/db/vector_store.py
scripts/build_vector_db.py
```

### 4.2 Vector Store 구성

Chroma PersistentClient를 사용하여 로컬 Vector DB를 구축하였다.

주요 설정은 다음과 같다.

```python
collection_name = "youth_policy_chunks"
persist_dir = "data/vector_db"
embedding_model = "text-embedding-3-small"
hnsw_space = "cosine"
```

### 4.3 주요 기능

`YouthPolicyVectorStore` 클래스에 다음 기능을 구현하였다.

- Chroma collection 생성 및 로드
- OpenAI Embedding API를 이용한 문서 임베딩
- 정책 chunk upsert
- query embedding 생성
- cosine distance 기반 검색
- 검색 결과를 `VectorSearchResult` 객체로 변환

### 4.4 Vector DB 생성 명령어

```cmd
python scripts\build_vector_db.py --input data\processed\chunks_for_chroma.jsonl --persist-dir data\vector_db --collection-name youth_policy_chunks --reset
```

### 4.5 Smoke Test 결과

다음 질문으로 검색 테스트를 수행하였다.

```text
서울에 사는 25세 취업준비생이 받을 수 있는 청년 지원 정책 알려줘
```

상위 검색 결과는 다음과 같았다.

```text
1. 서울시 일자리카페 운영
2. 기장군 청년 면접수당 지원 사업
3. 2026년 서울청년정책네트워크 하반기 모집
4. 미취업 청년 어학 및 자격증 응시료 지원(성북구)
5. 서울시 청년수당
```

---

## 5. 4.3 Retriever 구현

### 5.1 구현 파일

```text
backend/services/rag_service.py
backend/db/vector_store.py
```

### 5.2 주요 기능

Retriever는 Vector DB 검색 결과를 사용자 조건에 맞게 필터링하고, 정책 단위로 정리하는 역할을 수행한다.

구현한 주요 기능은 다음과 같다.

- query 기반 Chroma 검색
- 사용자 나이 필터링
- 사용자 지역 필터링
- 정책 도메인 필터링
- 동일 정책 중복 제거
- 검색 score 기준 rerank
- 검색 결과 compact format 변환
- Answer Generator용 context 문자열 생성

### 5.3 지역 필터링 개선

초기에는 사용자 지역 코드 `11000`과 정책 지역 코드 `11110`, `11140` 등 서울시 구 단위 코드가 정확히 일치하지 않아 필터링 결과가 비는 문제가 있었다.

이를 해결하기 위해 시도 단위 코드와 시군구 코드 간 prefix 매칭을 추가하였다.

```text
사용자 지역 코드: 11000
정책 지역 코드: 11110,11140,...,11740
판정: 같은 서울 권역이므로 통과
```

### 5.4 Retriever 테스트 결과

```text
filtered count: 5

1. 서울시 일자리카페 운영
2. 2026년 서울청년정책네트워크 하반기 모집
3. 미취업 청년 어학 및 자격증 응시료 지원(성북구)
4. 서울시 청년수당
5. 취업날개 서비스 지원
```

도메인 필터를 `일자리`로 적용한 결과는 다음과 같았다.

```text
1. 서울시 일자리카페 운영
2. 조기재취업수당
3. 미취업 청년 어학 및 자격증 응시료 지원(성북구)
4. 서울형 청년인턴 직무캠프
5. 취업날개 서비스 지원
```

---

## 6. 4.4 조건 추출기 구현

### 6.1 구현 파일

```text
backend/services/condition_extractor.py
backend/graph/prompts.py
```

### 6.2 추출 대상 필드

조건 추출기는 사용자 자연어 질문에서 다음 정보를 JSON으로 추출한다.

```json
{
  "age": 25,
  "region": "서울",
  "income": null,
  "employment_status": "취업준비생",
  "company_type": null,
  "education_status": null,
  "major": null,
  "interest_domain": "일자리",
  "keywords": ["취업", "지원"],
  "region_code": "11000"
}
```

### 6.3 주요 기능

- OpenAI Chat Completion 기반 조건 추출
- JSON parsing 실패 시 repair prompt 적용
- 최종 fallback rule-based extraction 적용
- 지역명에서 region_code 변환
- 관심 분야를 retriever용 domain filter로 변환
- keywords를 검색 query에 보강

### 6.4 테스트 결과

입력 문장:

```text
서울에 사는 25세 취준생인데 받을 수 있는 취업 지원 정책 알려줘.
```

추출 결과:

```json
{
  "age": 25,
  "region": "서울",
  "employment_status": "취업준비생",
  "interest_domain": "일자리",
  "keywords": ["취업", "지원"],
  "region_code": "11000"
}
```

조건 추출 결과를 Retriever에 연결한 결과, 서울/25세/일자리 조건에 맞는 정책이 정상적으로 검색되었다.

---

## 7. 4.5 Router 구현

### 7.1 구현 파일

```text
backend/graph/nodes.py
backend/graph/workflow.py
```

### 7.2 Router 역할

Router는 사용자 질문과 추출된 조건을 보고 어떤 정책 도메인을 검색할지 결정한다.

지원 도메인은 다음과 같다.

```text
일자리
주거
교육
복지문화
참여권리
금융
창업
전체
```

### 7.3 라우팅 기준

```text
취업, 구직, 재직, 중소기업 → 일자리
월세, 전세, 주거, 임대 → 주거
대출, 저축, 자산, 계좌 → 금융
창업, 사업, 예비창업자 → 창업
교육, 자격증, 훈련, 학습 → 교육
도메인이 불명확하면 전체 검색
```

### 7.4 테스트 결과

```text
월세 지원 → 주거
청년도약계좌/저축 → 금융
예비창업자 → 창업
자격증/응시료 → 교육
청년 정책 아무거나 추천 → 전체
취업/취준생 → 일자리
```

Router 결과 예시는 다음과 같다.

```json
{
  "route": "일자리",
  "reason": "사용자 질문에 취업, 취준, 취준생 키워드가 포함됨 / 조건 추출 결과 interest_domain이 일자리로 판단됨",
  "filters": {
    "user_age": 25,
    "user_region_code": "11000",
    "domain": "일자리"
  }
}
```

---

## 8. 4.6 Eligibility Checker 구현

### 8.1 구현 파일

```text
backend/services/policy_matcher.py
backend/graph/prompts.py
```

### 8.2 판단 등급

Eligibility Checker는 사용자 조건과 정책 조건을 비교하여 신청 가능성을 다음 세 가지로 판단한다.

```text
가능성 높음
추가 확인 필요
가능성 낮음
```

### 8.3 판단 원칙

- 연령 조건은 구조화 필드인 `age_min`, `age_max`로 우선 판단
- 지역 조건은 `region_code` 기반으로 판단
- 시도 코드와 시군구 코드는 prefix 기반으로 매칭
- 소득 조건은 명확히 확인 가능한 경우에만 판단
- 정책 데이터에 없는 조건은 `추가 확인 필요`로 분류
- 불충족 조건이 있으면 `가능성 낮음`으로 분류
- LLM이 임의로 신청 가능 여부를 확정하지 않도록 rule-based 판단을 기본으로 사용

### 8.4 출력 예시

```json
{
  "policy_id": "R202406010001",
  "policy_name": "청년월세 한시 특별지원",
  "eligibility": "추가 확인 필요",
  "matched_conditions": [
    "연령 조건 충족: 25세는 지원 대상 19~34세에 포함됨",
    "지역 조건 충족: 전국 대상 정책",
    "소득 조건: 검색된 정책 chunk에서 명확한 소득 제한을 확인하지 못함"
  ],
  "missing_conditions": [
    "고용 상태 조건 확인 필요: 정책 본문에서 '취업준비생' 조건을 명확히 확인하지 못함"
  ],
  "cautions": [],
  "blockers": []
}
```

### 8.5 Retriever 연동 결과

서울 25세 취업준비생 조건으로 검색된 정책에 Eligibility Checker를 적용한 결과, 다음 정책들이 `추가 확인 필요`로 분류되었다.

```text
1. 서울시 일자리카페 운영
2. 미취업 청년 어학 및 자격증 응시료 지원(성북구)
3. 청년 국가기술자격시험 응시료 지원사업
4. 서울 매력일자리
5. 취업날개 서비스 지원
```

대부분의 정책이 `추가 확인 필요`로 분류된 이유는 신청기간, 제출서류, 소득 조건 등이 검색된 chunk에 명확히 포함되어 있지 않았기 때문이다.

---

## 9. 4.7 Answer Generator 구현

### 9.1 구현 파일

```text
backend/services/answer_generator.py
backend/graph/prompts.py
```

### 9.2 답변 포함 항목

Answer Generator는 최종 답변에 다음 항목을 포함한다.

```text
추천 정책명
추천 이유
신청 가능성
충족 조건
추가 확인이 필요한 조건
지원 내용
신청 기간
신청 방법
제출 서류
출처 URL
유의사항
```

### 9.3 답변 원칙

- 검색된 정책 데이터에 기반해서만 답변
- 출처 없는 내용 생성 금지
- 결측 필드는 `제공된 데이터에는 정보가 없습니다`로 안내
- 신청기간, 제출서류, 자격조건은 확정적으로 표현하지 않음
- source_url이 있으면 반드시 함께 제공
- LLM 호출 실패 시 rule-based 답변으로 fallback

### 9.4 구현 방식

Answer Generator는 두 가지 방식으로 동작한다.

| 방식 | 설명 |
| --- | --- |
| `generate_answer_with_llm` | LLM을 사용하여 자연스러운 최종 답변 생성 |
| `generate_answer_rule_based` | LLM 없이 안전한 정형 답변 생성 |

최종 진입점은 다음 함수이다.

```python
generate_answer(
    query=query,
    user_conditions=conditions,
    policies=enriched_policies,
    use_llm=True
)
```

### 9.5 테스트 결과

`use_llm=False`에서는 데이터 기반 정형 답변이 생성되었고, `use_llm=True`에서는 사용자에게 읽기 좋은 자연어 답변이 생성되었다.

결측 필드는 다음과 같이 처리되었다.

```text
신청 기간: 제공된 데이터에는 정보가 없습니다.
신청 방법: 제공된 데이터에는 정보가 없습니다.
제출 서류: 제공된 데이터에는 정보가 없습니다.
출처 URL: 제공된 데이터에는 출처 URL이 없습니다.
```

---

## 10. 4.8 LangGraph Workflow 구성

### 10.1 구현 파일

```text
backend/graph/nodes.py
backend/graph/workflow.py
```

### 10.2 GraphState 구조

LangGraph Workflow에서는 다음과 같은 상태 객체를 사용한다.

```python
class GraphState(TypedDict, total=False):
    user_query: str
    user_conditions: dict
    route: str
    route_reason: str
    filters: dict
    retriever_query: str
    retrieved_chunks: list[dict]
    eligibility_results: list[dict]
    answer: str
    warnings: list[str]
    errors: list[str]
```

### 10.3 노드 구조

```text
Input Validator
→ Condition Extractor
→ Router
→ Retriever
→ Eligibility Checker
→ Answer Generator
→ END
```

### 10.4 실행 함수

```python
run_rag_workflow(
    query="서울에 사는 25세 취준생인데 받을 수 있는 취업 지원 정책 알려줘.",
    return_full_state=False
)
```

### 10.5 Workflow 테스트 결과

Workflow 실행 결과 다음 필드가 정상 반환되었다.

```text
answer
user_conditions
route
route_reason
recommendations
warnings
errors
```

테스트 결과:

```text
route = 일자리
warnings = []
errors = []
```

따라서 전체 LangGraph Workflow는 정상적으로 실행되는 것을 확인하였다.

---

## 11. FastAPI `/api/chat` 연동

### 11.1 연동 방식

팀원이 작성한 `backend/api/chat.py` 파일 구조를 크게 수정하지 않고, RAG 연결용 adapter 파일을 별도로 작성하였다.

추가 파일:

```text
backend/services/rag_chat_service.py
```

### 11.2 Adapter 역할

`rag_chat_service.py`는 다음 역할을 수행한다.

```text
run_rag_workflow() 호출
→ workflow 결과 수신
→ ChatResponse 스키마에 맞게 변환
→ chat.py에 반환
```

### 11.3 chat.py 최소 수정 사항

팀원 파일은 다음 세 부분만 수정하였다.

```diff
- USE_MOCK = True
+ USE_MOCK = False

- # from backend.services.rag_service import run_rag_chat
+ from backend.services.rag_chat_service import run_rag_chat

- raw = run_rag_chat(...)
- result = ChatResponse(**raw)
+ result = run_rag_chat(...)
```

이 방식으로 팀원의 API 구조를 유지하면서 RAG 파이프라인을 연결하였다.

### 11.4 API 테스트

초기 `/chat`으로 요청했을 때는 다음 오류가 발생하였다.

```json
{"detail": "Not Found"}
```

원인은 `main.py`에서 router prefix가 `/api`로 등록되어 있었기 때문으로 판단하였다.

이후 `/api/chat`으로 요청하여 정상 응답을 확인하였다.

테스트 명령어:

```cmd
curl -X POST "http://127.0.0.1:8000/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"서울에 사는 25세 취준생인데 받을 수 있는 취업 지원 정책 알려줘.\",\"top_k\":5}"
```

정상 응답에서 다음 필드들이 확인되었다.

```text
answer
user_conditions
route
recommendations
warnings
```

응답 결과:

```text
route: 일자리
user_conditions:
  age: 25
  region: 서울
  employment_status: 취업준비생
  interest_domain: 일자리

recommendations:
  1. 서울시 일자리카페 운영
  2. 미취업 청년 어학 및 자격증 응시료 지원(성북구)
  3. 청년 국가기술자격시험 응시료 지원사업
  4. 서울 매력일자리
  5. 취업날개 서비스 지원
```

---

## 12. 이슈 및 해결 내역

### 12.1 Chroma metadata 변환 문제

문제:

```text
기존 chunks.jsonl은 Chroma 입력 구조가 아니었음
```

해결:

```text
text + metadata 구조로 변환
Chroma 허용 타입으로 메타데이터 정규화
```

### 12.2 날짜가 연령으로 파싱되는 문제

문제:

```text
application_period_text의 날짜 숫자가 age_min, age_max로 잘못 파싱됨
```

해결:

```text
age_text 라인에서만 연령 파싱하도록 수정
```

### 12.3 서울 시도 코드와 구 단위 코드 불일치

문제:

```text
사용자 지역 11000과 정책 지역 11110, 11140 등이 불일치하여 필터링 실패
```

해결:

```text
시도 prefix 기반 지역 매칭 로직 추가
```

### 12.4 Python module import 오류

문제:

```text
python backend\graph\workflow.py 실행 시 ModuleNotFoundError: No module named 'backend'
```

해결:

```cmd
python -m backend.graph.workflow
```

또한 `__init__.py` 파일을 각 패키지 폴더에 추가하였다.

### 12.5 FastAPI 경로 오류

문제:

```json
{"detail": "Not Found"}
```

해결:

```text
/chat이 아니라 /api/chat으로 호출
```

### 12.6 ChatResponse 이중 변환 오류

문제:

```text
ChatResponse() argument after ** must be a mapping, not ChatResponse
```

원인:

```text
run_rag_chat()이 이미 ChatResponse 객체를 반환하는데, chat.py에서 다시 ChatResponse(**raw)를 호출함
```

해결:

```python
result = run_rag_chat(...)
```

으로 수정하였다.

### 12.7 RequestsDependencyWarning

문제:

```text
RequestsDependencyWarning: Unable to find acceptable character detection dependency
```

해결 방법:

```cmd
pip install charset-normalizer
```

이 경고는 실행 실패를 유발하지 않으므로 기능 검증에는 영향이 없었다.

---

## 13. 최종 산출물

### 13.1 신규 및 수정 파일

```text
scripts/convert_chunks_for_chroma_v2.py
scripts/build_vector_db.py

backend/db/vector_store.py

backend/services/rag_service.py
backend/services/condition_extractor.py
backend/services/policy_matcher.py
backend/services/answer_generator.py
backend/services/rag_chat_service.py

backend/graph/prompts.py
backend/graph/nodes.py
backend/graph/workflow.py

backend/api/chat.py
```

### 13.2 생성 데이터

```text
data/processed/chunks_for_chroma.jsonl
data/processed/chunks_for_chroma_report.json
data/vector_db/
```

### 13.3 API Endpoint

```text
POST /api/chat
```

---

## 14. 현재 완성된 기능

현재까지 완성된 기능은 다음과 같다.

```text
사용자 자연어 질문 입력
조건 추출
정책 도메인 라우팅
Chroma 기반 정책 검색
연령/지역/고용상태/소득 조건 기반 신청 가능성 판단
LLM 기반 최종 답변 생성
결측 필드 안내
출처 URL 제공
FastAPI /api/chat 응답 반환
```

---

## 15. 한계 및 개선 사항

### 15.1 신청기간, 신청방법, 제출서류 정보 부족

현재 검색 결과가 summary chunk 중심으로 반환되는 경우, 신청기간, 신청방법, 제출서류 정보가 누락될 수 있다.

개선 방향:

```text
동일 policy_id의 detail chunk를 추가로 조회
summary + eligibility + application chunk를 합쳐 Answer Generator에 전달
```

### 15.2 대부분의 정책이 `추가 확인 필요`로 분류됨

현재 Eligibility Checker는 보수적으로 판단한다. 신청기간, 서류, 소득 조건이 불명확하면 `추가 확인 필요`로 분류된다.

개선 방향:

```text
핵심 조건: 연령, 지역, 명시적 자격조건
보조 조건: 신청기간, 제출서류, source_url
으로 분리하여 등급 산정 기준 조정
```

### 15.3 top_k 파라미터 미반영

현재 API 요청의 `top_k`는 chat.py에서 전달되지만, workflow 내부 Retriever에서는 `top_k=5`로 고정되어 있다.

개선 방향:

```text
GraphState에 top_k 추가
run_rag_workflow(query, top_k=5) 형태로 수정
retriever_node에서 state["top_k"] 사용
```

### 15.4 LLM 답변의 표현 안정성

LLM 답변에서 사용자 입력 조건을 확정 사실처럼 표현할 가능성이 있다.

개선 방향:

```text
"사용자 입력 기준" 표현을 강제
응원, 감상, 권유성 문장 최소화
정책 정보 안내 중심으로 답변 종료
```

### 15.5 source_url 결측 정책

일부 정책은 source_url이 비어 있어 원문 확인이 어렵다.

개선 방향:

```text
application_url을 source_url fallback으로 사용
source_url이 없으면 담당 기관 또는 온통청년 상세 페이지 URL 보강
```

---

## 16. 결론

본 작업을 통해 청년 정책 추천 서비스의 RAG/LLM 핵심 파이프라인을 구현하였다.

초기 정책 chunk 데이터를 Chroma에 적재 가능한 형태로 변환하고, OpenAI Embedding과 Chroma Vector DB를 이용해 정책 검색 기반을 구축하였다. 이후 사용자 질문에서 조건을 추출하고, 질문 의도에 맞는 정책 도메인을 라우팅한 뒤, 검색 결과에 대해 신청 가능성을 보수적으로 판단하는 Eligibility Checker를 구현하였다.

최종적으로 Answer Generator를 통해 검색 결과와 자격 판단 결과를 사용자에게 설명 가능한 형태로 제공하였고, 전체 과정을 LangGraph Workflow로 연결하였다. 또한 팀원이 작성한 FastAPI `chat.py` 구조를 최대한 유지하면서 별도 adapter를 통해 `/api/chat` 엔드포인트에 실제 RAG 파이프라인을 연동하였다.

현재 시스템은 다음 흐름을 정상적으로 수행한다.

```text
사용자 질문
→ 조건 추출
→ 도메인 라우팅
→ 정책 검색
→ 신청 가능성 판단
→ 최종 답변 생성
→ FastAPI 응답 반환
```

따라서 RAG/LLM 백엔드 핵심 기능은 시연 가능한 수준으로 완성되었다.
