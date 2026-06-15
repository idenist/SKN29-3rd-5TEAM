# 청년 정책 RAG 에이전트 — API 명세

> SK네트웍스 Family AI 캠프 29기 3rd Team5 | FastAPI 백엔드 | 2026.06.15
>
> Swagger UI: `http://localhost:8000/docs`

---

## 공통 사항

| 항목 | 내용 |
|---|---|
| Base URL | `http://localhost:8000` |
| Content-Type | `application/json` |
| 인증 | 없음 (내부 서비스) |
| 문자 인코딩 | UTF-8 |

### HTTP 상태 코드

| 코드 | 의미 | 발생 조건 |
|---|---|---|
| 200 | 성공 | 정상 응답 |
| 400 | 잘못된 요청 | 메시지 2자 미만 |
| 422 | 유효성 오류 | Pydantic 검증 실패 (필드 누락 등) |
| 500 | 서버 내부 오류 | 예상치 못한 예외 |
| 503 | 서비스 불가 | 서버 메모리 부족 |

### 오류 응답 포맷

```json
{ "detail": "오류 메시지" }
```

422는 `errors` 필드 추가:

```json
{
  "detail": "요청 형식이 올바르지 않습니다.",
  "errors": [...]
}
```

---

## 엔드포인트 목록

| Method | Path | 설명 |
|---|---|---|
| GET | `/` | 서버 확인 |
| GET | `/health` | 헬스체크 |
| POST | `/api/chat` | RAG 질의응답 |
| GET | `/api/policies` | 지원 항목 목록 조회 |
| GET | `/api/policies/{item_id}` | 지원 항목 상세 조회 |

---

## 1. 서버 확인

### `GET /`

```python
@app.get("/", tags=["Root"])
def root():
    return {"message": "청년 정책 RAG 에이전트 API 서버입니다. /docs 에서 API 명세를 확인하세요."}
```

**응답 (200)**

```json
{
  "message": "청년 정책 RAG 에이전트 API 서버입니다. /docs 에서 API 명세를 확인하세요."
}
```

---

## 2. 헬스체크

### `GET /health`

서버 기동 상태를 확인한다.

```python
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "youth-policy-rag-agent"}
```

**응답 (200)**

```json
{
  "status": "ok",
  "service": "youth-policy-rag-agent"
}
```

---

## 3. RAG 질의응답

### `POST /api/chat`

자연어 질문을 입력하면 RAG 기반으로 관련 청년 정책을 검색하고 답변을 반환한다.

```python
@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="청년 정책 질의응답",
    description="자연어 질문을 입력하면 RAG 기반으로 관련 청년 정책을 검색하고 답변을 반환합니다.",
)
async def chat_endpoint(request: ChatRequest, http_request: Request) -> ChatResponse:
```

**내부 처리 흐름**

```
메시지 입력
→ 입력 검증 (2자 미만 → 400)
→ run_rag_chat() 호출
   └─ Condition Extractor  나이·지역·고용상태·관심분야 추출
   └─ Router               source_category 결정
   └─ Retriever            Chroma Vector DB 검색 (top_k건)
   └─ Eligibility Checker  자격 가능성 판단
   └─ Answer Generator     최종 답변 생성
→ ChatResponse 반환
```

**요청 바디 (`ChatRequest`)**

```json
{
  "message": "서울에 사는 27세 취업준비생인데 받을 수 있는 청년 지원 정책 알려줘",
  "user_profile": {
    "age": 27,
    "region": "서울"
  },
  "top_k": 5
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message` | `string` | ✅ | 자연어 질문. 2자 미만 → 400 |
| `user_profile` | `object \| null` | ❌ | 사전 입력 조건 (Streamlit 사이드바 값) |
| `top_k` | `int` | ❌ | 검색 결과 수. `ge=1, le=20` (Pydantic 검증) |

**응답 바디 (`ChatResponse`)**

```json
{
  "answer": "서울 거주 27세 취업준비생에게 적합한 청년 정책을 안내합니다...",
  "recommendations": [
    {
      "item_id": "policy_20260605005400113228",
      "title": "청년미래적금",
      "source_category": "policy",
      "domain": "금융·복지·문화 > 취약계층 및 금융지원",
      "summary": "청년의 자산 형성을 지원하는 적금 상품",
      "eligibility": "가능성 높음",
      "source_url": "https://www.youthcenter.go.kr/...",
      "application_url": "https://...",
      "is_expired": false,
      "deadline_status": "open"
    }
  ],
  "user_conditions": {
    "age": 27,
    "region": "서울",
    "region_code": "11000",
    "employment_status": "취업준비생",
    "interest_domain": "일자리",
    "income": null,
    "keywords": ["취업", "지원"]
  },
  "route": "policy",
  "source_category": "policy",
  "warnings": [],
  "session_id": "user-abc-123"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `answer` | `string` | LLM 생성 최종 답변 |
| `recommendations` | `array` | 추천 항목 목록 |
| `recommendations[].item_id` | `string` | 고유 ID (`opportunities.json` 연결 키) |
| `recommendations[].title` | `string` | 항목명 |
| `recommendations[].source_category` | `string` | `"policy"` \| `"startup_notice"` \| `"training"` |
| `recommendations[].domain` | `string` | 분야 |
| `recommendations[].summary` | `string \| null` | 요약 설명 |
| `recommendations[].eligibility` | `string` | `"가능성 높음"` \| `"추가 확인 필요"` \| `"가능성 낮음"` |
| `recommendations[].source_url` | `string \| null` | 출처 URL |
| `recommendations[].application_url` | `string \| null` | 신청 URL. `null`이면 신청 버튼 숨김 |
| `recommendations[].is_expired` | `boolean` | 마감 여부 (`startup_notice` 해당) |
| `recommendations[].deadline_status` | `string` | `"open"` \| `"expired"` \| `"unknown"` |
| `user_conditions` | `object` | Condition Extractor 추출 결과 |
| `route` | `string` | Router 결정 도메인 |
| `source_category` | `string` | 검색에 사용된 source_category |
| `warnings` | `array[string]` | fallback 발생 시 경고 메시지 |

**오류 응답**

| 상태 | 발생 조건 | 응답 예시 |
|---|---|---|
| 400 | 메시지 2자 미만 | `{"detail": "질문이 너무 짧습니다. 구체적으로 입력해 주세요."}` |
| 422 | 필드 누락 등 | `{"detail": "요청 형식이 올바르지 않습니다.", "errors": [...]}` |
| 500 | 예상치 못한 예외 | `{"detail": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}` |
| 503 | 서버 메모리 부족 | `{"detail": "서버 리소스가 부족합니다. 잠시 후 다시 시도해 주세요."}` |

---

## 4. 지원 항목 목록 조회

### `GET /api/policies`

`opportunities.json` 기반으로 지원 항목 목록을 반환한다.

```python
@router.get(
    "/policies",
    summary="지원 항목 목록 조회",
    ...
)
```

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `page` | `int` | ❌ | `1` | 페이지 번호 |
| `page_size` | `int` | ❌ | `20` | 페이지당 항목 수 (최대 100) |
| `source_category` | `string` | ❌ | `null` | `policy` \| `startup_notice` \| `training` |
| `domain` | `string` | ❌ | `null` | 도메인 부분 일치 필터 |
| `keyword` | `string` | ❌ | `null` | 제목/요약 키워드 검색 |

**요청 예시**

```
GET /api/policies?source_category=policy&keyword=청년수당&page=1
```

**응답 바디**

```json
{
  "total": 2611,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "item_id": "policy_20260605005400113228",
      "title": "청년미래적금",
      "source_category": "policy",
      "domain": "금융·복지·문화 > 취약계층 및 금융지원",
      "summary": "청년의 자산 형성을 지원하는 적금 상품",
      "organization": "금융위원회",
      "application_period_text": "상시",
      "info_score": 90,
      "needs_detail_check": true,
      "source_url": "https://...",
      "application_url": "https://..."
    }
  ]
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `total` | `int` | 전체 항목 수 |
| `page` | `int` | 현재 페이지 |
| `page_size` | `int` | 페이지당 항목 수 |
| `items[].item_id` | `string` | 고유 ID |
| `items[].title` | `string` | 항목명 |
| `items[].source_category` | `string` | `"policy"` \| `"startup_notice"` \| `"training"` |
| `items[].domain` | `string` | 분야 |
| `items[].summary` | `string \| null` | 요약 설명 |
| `items[].organization` | `string \| null` | 주관 기관 |
| `items[].application_period_text` | `string \| null` | 신청기간 원문 |
| `items[].info_score` | `int \| null` | 데이터 완성도 점수 (0~100). 추천 우선순위 아님 |
| `items[].needs_detail_check` | `boolean \| null` | `true`이면 원문 확인 필요 |
| `items[].source_url` | `string \| null` | 출처 URL |
| `items[].application_url` | `string \| null` | 신청 URL. `null`이면 신청 버튼 숨김 |

---

## 5. 지원 항목 상세 조회

### `GET /api/policies/{item_id}`

`item_id` 기준으로 단일 지원 항목의 전체 필드를 반환한다.

```python
@router.get(
    "/policies/{item_id}",
    summary="지원 항목 상세 조회",
    ...
)
```

**경로 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `item_id` | `string` | ✅ | 예: `policy_20260605005400113228` |

**요청 예시**

```
GET /api/policies/policy_20260605005400113228
```

**응답 바디**

```json
{
  "item_id": "policy_20260605005400113228",
  "title": "청년미래적금",
  "source_category": "policy",
  "domain": "금융·복지·문화 > 취약계층 및 금융지원",
  "summary": "청년의 자산 형성을 지원하는 적금 상품",
  "target_text": "만 19~34세 청년",
  "benefit_text": "우대금리 최대 연 2%p",
  "region": "전국",
  "organization": "금융위원회",
  "application_period_text": "상시",
  "application_start_date": null,
  "application_end_date": null,
  "program_period_text": "2026.01.01 ~ 2026.12.31",
  "application_method": "금융기관 방문 또는 앱 신청",
  "required_documents": "신분증, 통장사본",
  "income_condition": "중위소득 180% 이하",
  "additional_condition": "무주택 청년",
  "participation_target": "취업준비생 제외 대상 없음",
  "region_codes": "11000,26000,27000",
  "source_url": "https://...",
  "source_url_2": null,
  "application_url": "https://...",
  "notes": "중복 가입 불가",
  "info_score": 90,
  "needs_detail_check": true,
  "created_at": "2026-06-05",
  "updated_at": "2026-06-10"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `item_id` | `string` | 고유 ID |
| `title` | `string` | 항목명 |
| `source_category` | `string` | `"policy"` \| `"startup_notice"` \| `"training"` |
| `domain` | `string \| null` | 분야 |
| `summary` | `string \| null` | 요약 설명 |
| `target_text` | `string \| null` | 지원 대상 원문 |
| `benefit_text` | `string \| null` | 지원 내용 |
| `region` | `string \| null` | 지역 원문 |
| `organization` | `string \| null` | 주관 기관 |
| `application_period_text` | `string \| null` | 신청기간 원문 |
| `application_start_date` | `string \| null` | 정제된 신청 시작일 |
| `application_end_date` | `string \| null` | 정제된 신청 종료일 |
| `program_period_text` | `string \| null` | 사업기간 원문 |
| `application_method` | `string \| null` | 신청 방법 |
| `required_documents` | `string \| null` | 제출 서류 |
| `income_condition` | `string \| null` | 소득 조건 |
| `additional_condition` | `string \| null` | 추가 자격 조건 |
| `participation_target` | `string \| null` | 참여 제한 대상 |
| `region_codes` | `string \| null` | 지역 코드 (쉼표 구분) |
| `source_url` | `string \| null` | 1차 출처 URL |
| `source_url_2` | `string \| null` | 2차 출처 URL |
| `application_url` | `string \| null` | 신청 URL. `null`이면 신청 버튼 숨김 |
| `notes` | `string \| null` | 기타 사항 |
| `info_score` | `int \| null` | 데이터 완성도 점수 (0~100) |
| `needs_detail_check` | `boolean \| null` | 원문 확인 필요 여부 |
| `created_at` | `string \| null` | 최초 등록일 |
| `updated_at` | `string \| null` | 최종 수정일 |

**오류 응답 (404)**

```json
{
  "detail": "item_id 'policy_99999' 를 찾을 수 없습니다."
}
```

---

## 6. 구현 규칙 요약

| 규칙 | 내용 |
|---|---|
| `application_url = null` | 프론트엔드에서 신청 버튼 숨김 처리 |
| `source_url` 있음 | 출처 보기 링크로 표시 |
| `needs_detail_check = true` | 답변에 "원문 확인 필요" 문구 삽입 |
| `info_score` | 데이터 완성도 점수. 추천 우선순위로 오해 금지 |
| `item_id` | 시스템 전체 단일 식별 키. `title`로 조회 불가 (중복 존재) |
| `source_category = training` | 전체 데이터의 60%. 균형 노출 필요 (정책 3 / 창업 3 / 훈련 3 권장) |
| 원본 미포함 정보 | 신청방법·제출서류·조건 임의 생성 금지 |
