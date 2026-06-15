# 데이터 전처리 가이드

## 1. 전처리 목적

본 문서는 청년 지원 통합 탐색 에이전트에서 사용하는 3개 출처 데이터(온통청년 정책, K-Startup 창업공고, HRD 교육훈련)의 전처리 기준과 흐름을 설명한다.

각 출처의 원본 데이터는 컬럼 구조와 품질이 모두 다르므로, 출처별로 전처리를 수행한 뒤 공통 스키마(`opportunities.json`)로 통합한다.

전처리의 주요 목표는 다음과 같다.

- 원본 컬럼명을 백엔드/RAG에서 사용하기 쉬운 표준 스키마로 변환
- 청년 관련성 기준으로 통합 대상 데이터를 선별
- 결측 필드 정리 및 데이터 완성도 점수(`info_score`) 생성
- RAG 임베딩용 청크(`opportunity_chunks.jsonl`) 생성
- 원본은 절대 수정하지 않고 표준 산출물만 새로 생성

---

## 2. 출처별 입력 데이터

| 출처 | source_category | 입력 파일 | 원본 건수 |
|---|---|---|---:|
| 온통청년 | `policy` | `data/raw/youthcenter_api/youth_policy_raw.csv` | 2,611건 |
| K-Startup / 창업진흥원 | `startup_notice` | `data/raw/kstartup_api/kstartup_announcements_raw.csv` | 29,017건 |
| 고용24 / HRD | `training` | HRD API 수집 데이터 | 99,900건 (중복 제거 후 99,430건) |

K-Startup과 HRD는 전체 데이터를 사용하지 않고 청년 관련성 기준으로 `HIGH`만 통합한다.

---

## 3. 온통청년 정책 전처리

### 3.1 전처리 흐름

```text
1. CSV 로드
2. 원본 컬럼명 → 표준 스키마 매핑
3. 공백/nan/null/none 문자열 정리
4. policy_id 결측 제거
5. policy_id 기준 중복 제거
6. 나이 조건 정제
7. 신청기간 정제
8. 사업기간 날짜 정제
9. domain 생성
10. info_score 계산
11. needs_detail_check 계산
12. raw_text 생성
13. policies.json 저장
14. chunks.jsonl 생성 및 저장
15. 품질 리포트 저장
```

### 3.2 CSV 로드

`read_csv()` 함수는 다음 인코딩을 순차적으로 시도한다.

```text
utf-8-sig → utf-8 → cp949 → euc-kr
```

CSV는 문자열 기준으로 읽는다. 정책번호, 지역코드, 날짜처럼 숫자로 보이지만 식별자 성격이 있는 값이 있기 때문이다.

### 3.3 컬럼명 표준 스키마 매핑

원본 API 컬럼명을 백엔드/RAG 담당자가 이해하기 쉬운 영문 snake_case 필드로 변환한다.

| 원본 | 표준 |
|---|---|
| `plcyNo` | `policy_id` |
| `plcyNm` | `policy_name` |
| `plcyExplnCn` | `policy_summary` |
| `plcySprtCn` | `support_content` |
| `aplyUrlAddr` | `application_url` |
| `refUrlAddr1` | `source_url` |

전체 매핑은 `scripts/preprocess_policies.py`의 `COLUMN_MAP`을 기준으로 한다.

### 3.4 결측치와 문자열 정리

`clean_text()`에서 다음 처리를 한다.

- 실제 NaN 값은 빈 문자열로 변환
- `nan`, `none`, `null` 문자열은 빈 문자열로 변환
- 앞뒤 공백 제거 및 반복 공백 정리
- 과도한 줄바꿈 정리

결측값을 "정보 없음", "해당 없음", "온라인 신청" 같은 문구로 임의 보정하지 않는다.

### 3.5 policy_id 기준 정리

- `policy_id`가 없는 행은 제거한다.
- 중복 제거는 `policy_id` 기준으로 한다.
- 같은 `policy_name`은 유지한다. 정책명이 같아도 지역, 기관, 세부 사업이 다를 수 있기 때문이다.

### 3.6 나이 조건 정제

원본 필드:

```text
sprtTrgtMinAge → age_min
sprtTrgtMaxAge → age_max
sprtTrgtAgeLmtYn → age_limit_yn
```

생성 규칙:

| 조건 | `age_text` |
|---|---|
| 연령 제한 없음 | `연령 제한 없음` |
| 최소/최대 모두 있음 | `만 N세 ~ M세` |
| 최소만 있음 | `만 N세 이상` |
| 최대만 있음 | `만 M세 이하` |
| 모두 없음 | 빈 문자열 |

### 3.7 신청기간 정제

원본 신청기간 `aplyYmd`는 그대로 `application_period_text`에 보존한다.

정규식으로 날짜를 찾을 수 있으면 `application_start_date`, `application_end_date`를 추가 생성한다. "상시", "예산 소진 시까지", "기관 문의" 같은 값은 날짜를 임의로 만들지 않는다.

### 3.8 사업기간 정제

사업 시작일/종료일은 가능한 경우 `YYYY-MM-DD` 형태로 정리한다.

```text
bizPrdBgngYmd → business_start_date
bizPrdEndYmd → business_end_date
```

8자리 날짜가 아니면 원문을 최대한 보존한다.

### 3.9 domain 생성

`large_category`와 `middle_category`를 합쳐 생성한다.

```text
large_category > middle_category
```

예시:

```text
일자리 > 취업
주거 > 주택 및 거주지
교육 > 미래역량강화
```

### 3.10 info_score 생성

`info_score`는 데이터 완성도 점수이며, 추천 점수가 아니다.

계산 대상 필드:

```text
policy_id, policy_name, policy_summary, support_content,
supervising_org, age_text, application_period_text,
application_method, application_url, source_url
```

계산 방식:

```text
채워진 핵심 필드 수 / 전체 핵심 필드 수 × 100
```

### 3.11 needs_detail_check 생성

다음 중 하나라도 해당하면 `true`다.

- `application_method` 없음
- `application_url` 없음
- `required_documents` 없음
- `screening_method` 없음
- `support_content` 없음
- `source_url` 없음
- `info_score < 70`

`true`라도 해당 정책을 제거하라는 뜻이 아니다. 답변 및 화면에서 "상세 확인 필요"로 취급하라는 의미다.

### 3.12 raw_text 생성

RAG 보조용으로 주요 필드를 사람이 읽을 수 있는 형태로 합친 텍스트다. 화면에 그대로 노출하기 위한 필드가 아니다.

포함 필드: 정책명, 분야, 키워드, 정책요약, 지원내용, 주관기관, 운영기관, 나이조건, 신청기간, 신청방법, 제출서류, 심사방법, 소득조건, 추가자격조건, 참여제한대상, 비고, 신청URL, 출처URL

### 3.13 chunks.jsonl 생성

정책 1개당 최대 4개 section 청크를 생성한다.

| section | 포함 필드 |
|---|---|
| `summary` | `policy_summary`, `support_content` |
| `eligibility` | `age_text`, `income_condition`, `additional_condition`, `participation_target`, `region_codes` |
| `application` | `application_period_text`, `application_method`, `required_documents`, `screening_method`, `application_url` |
| `source` | `supervising_org`, `operating_org`, `source_url`, `source_url_2`, `notes` |

본문이 모두 비어 있는 section은 청크를 만들지 않는다.

### 3.14 실행 방법

```bash
cd youth-policy-rag-agent
python scripts/preprocess_policies.py
python scripts/check_data_quality.py
```

### 3.15 온통청년 산출물

```text
data/processed/policies_cleaned.csv
data/processed/policies.json
data/processed/chunks.jsonl
data/processed/missing_report.csv
data/processed/column_summary.csv
data/processed/duplicate_policy_name_report.csv
```

---

## 4. K-Startup 창업공고 전처리

### 4.1 개요

K-Startup 전체 창업공고 29,017건 중 청년과의 관련성이 명확한 `HIGH` 데이터 3,789건만 통합한다.

### 4.2 청년 관련성 판단 컬럼

| 컬럼 | 설명 |
|---|---|
| `biz_pbanc_nm` | 사업공고명 |
| `intg_pbanc_biz_nm` | 통합공고사업명 |
| `pbanc_ctnt` | 공고 내용 |
| `aply_trgt` | 신청 대상 |
| `aply_trgt_ctnt` | 신청 대상 상세 |
| `biz_trgt_age` | 사업 대상 연령 |
| `prfn_matr` | 우대사항 |
| `supt_biz_clsfc` | 지원사업 분류 |
| `biz_enyy` | 사업 업력 |
| `aply_excl_trgt_ctnt` | 신청 제외 대상 |

### 4.3 HIGH 분류 기준

다음 조건 중 하나라도 명확히 해당하면 `HIGH`로 분류한다.

**청년 키워드 명시**

```text
청년, 청년창업, 청년기업, 청년창업센터, 청년 스타트업,
청년 예비창업자, 청년창업자, 청년층
```

**청년 연령 기준 명확**

```text
만 19세, 만 34세 이하, 만 39세 이하, 19세~39세, 20세~39세
```

단, `만 40세 이상`이 함께 포함된 경우 청년 전용으로 보지 않고 `MEDIUM`으로 분류한다. 단, 청년 키워드 또는 청년 우대 조건이 명확하면 `HIGH`가 우선한다.

**청년 우대 조건**

```text
청년 우대, 청년 가점, 청년기업 우대, 청년창업자 우대, 청년층 우대, 청년 참여 우대
```

청년 우대 공고는 청년 전용이 아니더라도 `HIGH`로 분류한다.

### 4.4 MEDIUM / LOW 처리 기준

**MEDIUM** — 청년도 신청 가능하지만 청년 전용/우대가 명확하지 않은 경우

```text
예비창업자, 초기창업자, 창업 3년 이내, 창업 7년 이내,
스타트업, 창업기업, 청년 연령대가 포함되지만 40세 이상도 함께 포함된 경우
```

**LOW** — 청년 관련성이 낮거나 일반 기업 대상 성격이 강한 경우

현재 단계에서 MEDIUM / LOW는 통합하지 않고 참고용으로만 보관한다.

### 4.5 전처리 결과

| 분류 | 건수 | 비율 |
|---|---:|---:|
| HIGH | 3,789 | 13.06% |
| MEDIUM | 25,208 | 86.87% |
| LOW | 20 | 0.07% |

### 4.6 실행 방법

```bash
python scripts/preprocess_kstartup_youth.py \
  --input data/raw/kstartup_api/kstartup_announcements_raw.csv \
  --output-dir data/processed
```

### 4.7 K-Startup 산출물

```text
data/processed/startup_youth_high_only.json      # 백엔드 통합 대상
data/processed/startup_youth_high_chunks.jsonl   # RAG 통합 대상
```

---

## 5. HRD 교육훈련 전처리

### 5.1 사용 컬럼

| 컬럼 | 설명 |
|---|---|
| `title` | 훈련과정명 |
| `subTitle` | 훈련기관명 |
| `trainTarget` | 훈련대상 |
| `address` | 지역 |
| `traStartDate`, `traEndDate` | 훈련기간 |
| `courseMan`, `realMan` | 훈련비 또는 지원 정보 |
| `certificate` | 관련 자격증 |
| `ncsCd` | NCS 코드 |
| `titleLink` | 상세 URL |
| `titleIcon`, `contents` | 훈련 유형/설명 보조 텍스트 |

### 5.2 raw_text 생성

훈련과정명, 기관, 대상, 지역, 기간, 비용, 자격증, NCS 코드, 상세 URL을 합쳐 RAG 검색용 `raw_text`를 생성한다.

### 5.3 youth_relevance 기준

**HIGH** — 청년에게 직접적으로 적합하거나 청년 취업에 유용한 과정

- 청년 직접 키워드 포함
- 디지털/IT/AI/데이터/개발 관련 과정
- 구직자/미취업자/취업준비/취업연계/양성과정 성격이 강한 과정

**MEDIUM** — 청년도 수강 가능하지만 청년 특화 근거가 약한 일반 훈련 과정

- 일반 국민내일배움카드 과정
- 일반 자격증 과정
- 회계/세무/조리/요양보호/기능사 등 일반 직업훈련

**LOW** — 청년 지원 서비스와 관련성이 낮거나 기업/중장년 중심 과정

- 사업주훈련, 기업 단체훈련, 법정의무교육
- 관리자/임원 교육, 중장년/시니어/고령자 중심 교육

### 5.4 training_type 분류 기준

```text
IT/디지털, 데이터/AI, 개발, 디자인/UX,
사무/회계, 서비스, 보건/복지, 제조/기술, 조리/식음료, 기타
```

### 5.5 전처리 결과

| 분류 | 건수 |
|---|---:|
| 원본 건수 | 99,900건 |
| 중복 제거 후 | 99,430건 |
| HIGH | 20,403건 |
| MEDIUM | 78,921건 |
| LOW | 106건 |

### 5.6 HRD 산출물

```text
data/processed/training_youth_high_only.json      # 백엔드 통합 대상
data/processed/training_youth_high_chunks.jsonl   # RAG 통합 대상
```

---

## 6. 품질 리포트

온통청년 전처리 시 다음 리포트가 생성된다.

| 파일 | 용도 |
|---|---|
| `missing_report.csv` | 표준 필드별 결측 개수와 결측률 확인 |
| `column_summary.csv` | 원본 컬럼별 비결측 개수, 결측 개수, 샘플 값 |
| `duplicate_policy_name_report.csv` | 정책명 중복 목록 — 중복 제거용이 아니라 `policy_name`을 key로 쓰면 안 된다는 검증용 |

---

## 7. 공통 주의사항

- 원본 CSV/데이터는 절대 수정하지 않는다.
- 없는 값은 임의로 채우지 않는다 ("정보 없음", "온라인 신청" 등 금지).
- 통합 데이터에서 모든 연결 기준은 `item_id`다.
- `policy_name` / `title`은 중복될 수 있으므로 key로 사용하지 않는다.
- `info_score`는 추천 점수가 아닌 데이터 완성도 점수다.
- `needs_detail_check=true`는 신청방법/URL/서류/출처 등 상세 확인이 필요할 수 있다는 의미다.
- K-Startup / HRD의 MEDIUM / LOW는 참고용으로만 보관하고 통합하지 않는다.
