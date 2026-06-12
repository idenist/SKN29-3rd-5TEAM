# 데이터 스키마 설계서

## 1. 프로젝트 데이터 개요

본 프로젝트는 청년 지원 정보를 RAG 기반으로 통합 탐색하기 위해 3개 공식 출처의 데이터를 공통 스키마로 정리했다.

최종 백엔드용 데이터는 `data/processed/opportunities.json`이며, RAG 임베딩용 데이터는 `data/processed/opportunity_chunks.jsonl`이다.

## 2. 출처별 데이터 설명

| source_category | 출처 | 설명 | 통합 기준 |
|---|---|---|---|
| `policy` | 온통청년 | 청년정책 데이터 | 전체 정책 데이터 |
| `startup_notice` | K-Startup / 창업진흥원 | 창업지원 사업공고 | `youth_relevance = high` |
| `training` | 고용24/HRD | 국민내일배움카드 훈련과정 | `youth_relevance = high` |

## 3. source_category 설명

- `policy`: 온통청년 청년정책
- `startup_notice`: K-Startup 청년 HIGH 창업지원 공고
- `training`: HRD/고용24 청년 HIGH 교육·훈련 과정

## 4. domain 설명

`domain`은 검색 필터와 라우팅에 활용되는 분야 값이다.

예시:

- `startup`
- `education`
- `일자리 > 취업`
- `일자리 > 창업`
- `주거 > 주택 및 거주지`
- `복지문화 > 취약계층 및 금융지원`

## 5. 주요 참조 필드 목록

백엔드/RAG 작업 시 반드시 확인해야 할 핵심 필드는 다음과 같다.

| 필드 | 용도 |
|---|---|
| `item_id` | 모든 데이터 연결 기준 key |
| `source_category` | 데이터 유형 분기 및 뱃지 표시 |
| `domain` | 검색 필터 및 라우팅 |
| `title` | 항목명 표시 |
| `summary` | 요약 설명 |
| `target_text` | 지원/훈련 대상 |
| `benefit_text` | 지원내용 또는 훈련 정보 |
| `region` | 지역 필터 |
| `application_period_text` | 신청기간 원문 |
| `program_period_text` | 사업/훈련 운영기간 |
| `organization` | 운영기관 |
| `application_url` | 신청 버튼 링크 (없으면 버튼 숨김) |
| `source_url` | 출처 보기 링크 |
| `raw_text` | RAG 검색용 통합 텍스트 |
| `info_score` | 데이터 완성도 점수 |
| `needs_detail_check` | 상세 확인 필요 여부 |

## 6. opportunities.json 필드 설명

| 필드 | 설명 |
|---|---|
| `item_id` | 통합 데이터 고유 ID. 백엔드/RAG 연결 기준 |
| `original_id` | 원본 데이터 ID |
| `source_name` | 데이터 출처명 |
| `source_category` | 데이터 유형 |
| `domain` | 분야 |
| `title` | 정책명, 공고명, 훈련과정명 |
| `summary` | 요약 설명 |
| `benefit_text` | 지원내용 또는 훈련 정보 |
| `target_text` | 지원대상 또는 훈련대상 |
| `region` | 지역 |
| `age_min` | 최소 나이 조건 |
| `age_max` | 최대 나이 조건 |
| `application_period_text` | 신청기간 원문 |
| `application_start_date` | 신청 시작일 |
| `application_end_date` | 신청 종료일 |
| `program_period_text` | 사업/훈련 운영기간 |
| `program_start_date` | 사업/훈련 시작일 |
| `program_end_date` | 사업/훈련 종료일 |
| `organization` | 운영기관 |
| `location` | 장소 |
| `application_method` | 신청방법 |
| `application_url` | 신청 URL |
| `source_url` | 원문 출처 URL |
| `contact` | 문의처 |
| `tags` | 태그 |
| `raw_text` | RAG 검색용 통합 텍스트 |
| `info_score` | 데이터 완성도 점수. 추천 점수가 아님 |
| `needs_detail_check` | 상세 확인 필요 여부 |
| `collected_at` | 수집 또는 정제 기준일 |
| `youth_relevance` | 청년 관련성 |
| `youth_only` | 청년 전용 여부 |
| `youth_preference` | 청년 우대 여부 |
| `startup_stage` | 창업 단계 |
| `is_digital_training` | 디지털 교육 여부 |
| `is_job_seeker_friendly` | 구직자 친화 과정 여부 |
| `training_type` | 교육훈련 유형 |
| `is_open` | 모집/운영 가능 여부 |

## 7. opportunity_chunks.jsonl 필드 설명

각 라인은 하나의 JSON 객체다.

| 필드 | 설명 |
|---|---|
| `chunk_id` | 청크 고유 ID |
| `item_id` | opportunities.json과 연결되는 key |
| `source_category` | 데이터 유형 |
| `domain` | 분야 |
| `title` | 제목 |
| `content` | 임베딩 대상 텍스트 |
| `metadata` | Vector DB 저장용 메타데이터 |

## 8. item_id 사용 원칙

모든 연결 기준은 `item_id`이다.

- 온통청년 정책: `policy_{policy_id}`
- K-Startup 창업공고: `startup_...`
- HRD 교육훈련: `training_...`

`policy_id`는 온통청년 원본 내부 key이므로 통합 데이터 전체의 key로 직접 사용하지 않는다.

## 9. 화면 표시 원칙

- `application_url`이 없으면 신청 버튼을 숨긴다.
- `source_url`이 있으면 출처 링크로 표시한다.
- 원본에 없는 신청방법, 제출서류, 자격조건은 임의 생성하지 않는다.
- `source_category`에 따라 화면 뱃지를 다음과 같이 표시한다.

| source_category | 뱃지 표시 |
|---|---|
| `policy` | 청년정책 |
| `startup_notice` | 창업지원 |
| `training` | 교육·훈련 |
