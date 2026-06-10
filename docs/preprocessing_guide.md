# 데이터 전처리 방식 설명서

## 1. 전처리 목적

온통청년 청년정책 API 원본 CSV는 컬럼명이 API 원본 기준이고, 백엔드/RAG에서 바로 사용하기에는 다음 문제가 있습니다.

- 컬럼명이 서비스 화면/백엔드에서 이해하기 어렵습니다.
- 정책명이 중복될 수 있습니다.
- 신청 URL, 제출서류, 심사방법 등 상세 필드 결측이 많습니다.
- RAG 임베딩에 바로 넣기 위한 청크 구조가 없습니다.
- 데이터 완성도와 상세 확인 필요 여부를 구분할 기준이 필요합니다.

따라서 `scripts/preprocess_policies.py`에서 원본을 보존한 상태로 표준 산출물을 생성합니다.

## 2. 입력/출력

### 입력

```text
data/raw/youthcenter_api/youth_policy_raw.csv
```

### 출력

```text
data/processed/policies_cleaned.csv
data/processed/policies.json
data/processed/chunks.jsonl
data/processed/missing_report.csv
data/processed/column_summary.csv
data/processed/duplicate_policy_name_report.csv
```

## 3. 전처리 전체 흐름

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

## 4. 단계별 설명

### 4.1 CSV 로드

`read_csv()` 함수는 다음 인코딩을 순차적으로 시도합니다.

```text
utf-8-sig → utf-8 → cp949 → euc-kr
```

CSV는 문자열 기준으로 읽습니다. 정책번호, 지역코드, 날짜처럼 숫자로 보이지만 식별자 성격이 있는 값이 있기 때문입니다.

### 4.2 컬럼명 표준 스키마 매핑

원본 API 컬럼명을 백엔드/RAG 담당자가 이해하기 쉬운 영문 snake_case 필드로 바꿉니다.

예시:

| 원본 | 표준 |
|---|---|
| `plcyNo` | `policy_id` |
| `plcyNm` | `policy_name` |
| `plcyExplnCn` | `policy_summary` |
| `plcySprtCn` | `support_content` |
| `aplyUrlAddr` | `application_url` |
| `refUrlAddr1` | `source_url` |

전체 매핑은 `docs/data_dictionary.md`와 `scripts/preprocess_policies.py`의 `COLUMN_MAP`을 기준으로 합니다.

### 4.3 결측치와 문자열 정리

`clean_text()`에서 다음 처리를 합니다.

- 실제 NaN 값은 빈 문자열로 변환
- `nan`, `none`, `null` 문자열은 빈 문자열로 변환
- 앞뒤 공백 제거
- 반복 공백 정리
- 과도한 줄바꿈 정리

주의: 결측값을 “정보 없음”, “해당 없음”, “온라인 신청” 같은 문구로 임의 보정하지 않습니다.

### 4.4 `policy_id` 기준 정리

- `policy_id`가 없는 행은 제거합니다.
- 중복 제거는 `policy_id` 기준으로 합니다.
- 같은 `policy_name`은 유지합니다. 정책명은 같아도 지역, 기관, 세부 사업이 다를 수 있기 때문입니다.

### 4.5 나이 조건 정제

원본 필드:

```text
sprtTrgtMinAge → age_min
sprtTrgtMaxAge → age_max
sprtTrgtAgeLmtYn → age_limit_yn
```

생성 필드:

```text
age_min
age_max
age_text
```

생성 규칙:

| 조건 | `age_text` |
|---|---|
| 연령 제한 없음 | `연령 제한 없음` |
| 최소/최대 모두 있음 | `만 N세 ~ M세` |
| 최소만 있음 | `만 N세 이상` |
| 최대만 있음 | `만 M세 이하` |
| 모두 없음 | 빈 문자열 |

### 4.6 신청기간 정제

원본 신청기간 `aplyYmd`는 그대로 `application_period_text`에 보존합니다.

추가로 정규식으로 날짜를 찾을 수 있으면 다음 필드를 생성합니다.

```text
application_start_date
application_end_date
```

날짜 추출이 불가능한 경우 빈 문자열로 둡니다. 예를 들어 “상시”, “예산 소진 시까지”, “기관 문의” 같은 값은 날짜를 임의로 만들지 않습니다.

### 4.7 사업기간 정제

사업 시작일/종료일은 가능한 경우 `YYYY-MM-DD` 형태로 정리합니다.

```text
bizPrdBgngYmd → business_start_date
bizPrdEndYmd → business_end_date
```

8자리 날짜가 아니면 원문을 최대한 보존합니다.

### 4.8 `domain` 생성

`large_category`와 `middle_category`를 합쳐 생성합니다.

```text
large_category > middle_category
```

예시:

```text
일자리 > 취업
주거 > 주택 및 거주지
교육 > 미래역량강화
```

둘 중 하나가 없으면 존재하는 값만 사용합니다.

### 4.9 `info_score` 생성

`info_score`는 데이터 완성도 점수입니다. 사용자에게 추천할 만한 정책인지 판단하는 점수가 아닙니다.

계산 기준 필드:

```text
policy_id
policy_name
policy_summary
support_content
supervising_org
age_text
application_period_text
application_method
application_url
source_url
```

계산 방식:

```text
채워진 핵심 필드 수 / 전체 핵심 필드 수 × 100
```

예시:

```text
10개 중 8개가 채워져 있으면 info_score = 80
```

### 4.10 `needs_detail_check` 생성

`needs_detail_check`는 상세 확인이 필요한 정책인지 표시하는 boolean 값입니다.

다음 중 하나라도 해당하면 `true`입니다.

- `application_method` 없음
- `application_url` 없음
- `required_documents` 없음
- `screening_method` 없음
- `support_content` 없음
- `source_url` 없음
- `info_score < 70`

이 값이 `true`라고 해서 정책을 제거하라는 뜻은 아닙니다. 사용자 답변이나 화면 표시에서 “상세 확인 필요”로 취급하라는 뜻입니다.

### 4.11 `raw_text` 생성

`raw_text`는 RAG 보조용으로 주요 필드를 사람이 읽을 수 있는 형태로 합친 텍스트입니다.

포함 후보:

```text
정책명
분야
키워드
정책요약
지원내용
주관기관
운영기관
나이조건
신청기간
신청방법
제출서류
심사방법
소득조건
추가자격조건
참여제한대상
비고
신청URL
출처URL
```

화면에 그대로 노출하기 위한 필드는 아닙니다.

### 4.12 `policies.json` 저장

백엔드 API와 상세 화면의 기준 파일입니다.

권장 사용 방식:

```python
policy_map = {policy["policy_id"]: policy for policy in policies}
```

금지 방식:

```python
policy_map = {policy["policy_name"]: policy for policy in policies}
```

`policy_name`은 중복될 수 있으므로 key로 쓰면 안 됩니다.

### 4.13 `chunks.jsonl` 생성

RAG 임베딩용 파일입니다. 한 줄이 하나의 JSON 객체입니다.

정책 1개당 최대 4개 section 청크를 생성합니다.

| section | 포함 필드 |
|---|---|
| `summary` | `policy_summary`, `support_content` |
| `eligibility` | `age_text`, `income_condition`, `additional_condition`, `participation_target`, `region_codes` |
| `application` | `application_period_text`, `application_method`, `required_documents`, `screening_method`, `application_url` |
| `source` | `supervising_org`, `operating_org`, `source_url`, `source_url_2`, `notes` |

본문이 모두 비어 있는 section은 청크를 만들지 않습니다.

## 5. 품질 리포트 설명

### 5.1 `missing_report.csv`

표준 필드별 결측 개수와 결측률을 확인하는 파일입니다.

사용 예:

- 신청 URL 결측이 얼마나 많은지 확인
- 출처 URL 결측이 얼마나 많은지 확인
- RAG 답변에서 주의해야 할 필드 확인

### 5.2 `column_summary.csv`

원본 컬럼별 다음 정보를 제공합니다.

- 컬럼명
- 비어 있지 않은 값 개수
- 결측 개수
- 샘플 값

PM이나 백엔드 담당자가 “원본에 이런 컬럼이 있었나?”를 확인할 때 사용합니다.

### 5.3 `duplicate_policy_name_report.csv`

`policy_name`이 중복되는 정책 목록입니다.

이 파일의 목적은 중복 제거가 아닙니다. 정책명이 중복될 수 있으므로 백엔드가 `policy_name`을 key로 쓰면 안 된다는 점을 검증하기 위한 리포트입니다.

## 6. 실행 방법

```bash
cd youth-policy-rag-agent
python scripts/preprocess_policies.py
python scripts/check_data_quality.py
```

## 7. 재실행 시 주의사항

- 원본 CSV는 덮어쓰지 않습니다.
- 전처리 산출물은 `data/processed/` 아래에서 새로 생성됩니다.
- 원본에 없는 정보를 사람이 임의로 추가하지 않습니다.
- API를 새로 수집하는 경우에도 최종 연결 기준은 `policy_id`입니다.

## 8. 백엔드/RAG 담당자에게 꼭 전달할 문장

```text
이 데이터는 policy_id 기준으로만 연결해야 합니다.
policy_name은 중복 가능하므로 key로 사용하면 안 됩니다.
info_score는 추천 점수가 아니라 데이터 완성도 점수입니다.
needs_detail_check=true인 정책은 신청방법/URL/서류/출처 등 상세 확인이 필요할 수 있습니다.
application_url이 없으면 신청 버튼을 숨기고, source_url이 있으면 출처 링크로 표시해야 합니다.
원본에 없는 신청방법, 제출서류, 자격 조건은 임의로 생성하면 안 됩니다.
```
