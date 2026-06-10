# 백엔드/RAG 데이터 스키마 문서

이 문서는 `data/processed/policies.json`과 `data/processed/chunks.jsonl`의 필드 의미와 사용 규칙을 설명합니다.

관련 문서:

- `docs/data_dictionary.md`: 전체 데이터 설명서와 필드별 사용 기준
- `docs/preprocessing_guide.md`: 전처리 방식과 파생 필드 생성 기준
- `docs/데이터_전처리_문서.md`: 데이터 전처리 요약 문서

## 1. 핵심 식별자 규칙

- 기본 key는 반드시 `policy_id`를 사용합니다.
- `policy_id`는 온통청년 원본의 `plcyNo`에서 매핑한 값입니다.
- `policy_name`은 같은 이름의 정책이 여러 개 존재할 수 있으므로 key로 사용하면 안 됩니다.
- 프론트엔드, 백엔드 API, RAG 검색 결과 연결은 모두 `policy_id` 기준으로 처리합니다.

## 2. `policies.json` 필드 설명

| 필드 | 설명 | 사용처 |
|---|---|---|
| `policy_id` | 정책 고유 ID. 원본 `plcyNo` 기반 | 기본 key, 상세 조회, RAG 결과 연결 |
| `policy_name` | 정책명 | 목록/상세 화면 표시. 단, key로 사용 금지 |
| `domain` | 대분류와 중분류를 결합한 분야값 | 필터, 화면 뱃지, RAG metadata |
| `keywords` | 원본 정책 키워드 | 검색 보조 |
| `policy_summary` | 정책 설명 요약 | 목록/상세 설명 |
| `large_category` | 대분류명 | 필터 |
| `middle_category` | 중분류명 | 필터 |
| `support_content` | 지원 내용 | 상세 화면 및 RAG 본문 |
| `supervising_org` | 주관 기관 | 상세 화면 |
| `operating_org` | 운영 기관 | 상세 화면 |
| `age_min` | 정제된 최소 나이 | 조건 필터 |
| `age_max` | 정제된 최대 나이 | 조건 필터 |
| `age_text` | 화면 표시용 나이 조건 | 상세 화면 |
| `application_period_text` | 원본 신청기간 텍스트 | 상세 화면 |
| `application_start_date` | 추출 가능한 경우 정제한 신청 시작일 | 정렬/필터 |
| `application_end_date` | 추출 가능한 경우 정제한 신청 종료일 | 정렬/필터 |
| `business_start_date` | 사업 시작일 | 상세 화면 |
| `business_end_date` | 사업 종료일 | 상세 화면 |
| `business_period_note` | 사업 기간 기타 설명 | 상세 화면 |
| `application_method` | 신청 방법 | 상세 화면 |
| `application_url` | 신청 URL | 신청 버튼 링크 |
| `required_documents` | 제출 서류 | 상세 화면 |
| `screening_method` | 심사 방법 | 상세 화면 |
| `income_min` | 소득 최소값 원본 기반 정제값 | 조건 표시/필터 후보 |
| `income_max` | 소득 최대값 원본 기반 정제값 | 조건 표시/필터 후보 |
| `income_condition` | 소득 조건 설명 | 상세 화면 및 RAG 본문 |
| `additional_condition` | 추가 신청 자격 조건 | 상세 화면 및 RAG 본문 |
| `participation_target` | 참여 제한 대상 | 상세 화면 및 RAG 본문 |
| `region_codes` | 지역 코드 문자열 | 지역 필터 후보 |
| `source_url` | 1차 출처 URL | 출처 링크 |
| `source_url_2` | 2차 출처 URL | 추가 출처 링크 |
| `notes` | 기타 사항 | 상세 화면 |
| `info_score` | 데이터 완성도 점수 | 검수 우선순위 판단 |
| `needs_detail_check` | 상세 확인 필요 여부 | 운영자 검수 표시 |
| `raw_text` | 주요 필드를 합친 RAG 보조 원문 | RAG 본문 후보 |
| `created_at` | 원본 최초 등록일 | 관리 정보 |
| `updated_at` | 원본 수정일 | 관리 정보 |

## 3. `chunks.jsonl` 필드 설명

`chunks.jsonl`은 한 줄에 JSON 객체 하나가 들어가는 JSON Lines 형식입니다. RAG 담당자는 각 줄을 읽어서 임베딩하면 됩니다.

| 필드 | 설명 |
|---|---|
| `chunk_id` | 청크 고유 ID. `{policy_id}::{section}` 형식 |
| `policy_id` | 연결할 정책 ID. 백엔드 상세 조회의 기준 |
| `policy_name` | 정책명. 검색 결과 제목 표시용이며 key로 사용 금지 |
| `domain` | 정책 분야 metadata |
| `section` | 청크 구분. `summary`, `eligibility`, `application`, `source` 중 하나 |
| `content` | 임베딩할 본문 텍스트 |
| `source_url` | 출처 URL metadata |
| `application_url` | 신청 URL metadata |
| `needs_detail_check` | 상세 확인 필요 여부 metadata |
| `info_score` | 데이터 완성도 점수 metadata |

## 4. 백엔드 구현 주의사항

1. `policy_id`를 기본 key로 사용해야 합니다.
2. `policy_name`은 중복될 수 있으므로 key로 쓰면 안 됩니다.
3. `needs_detail_check`가 `true`인 정책은 원본 데이터에 신청 방법, 제출 서류, URL, 심사 방법 등 주요 상세 정보가 부족할 수 있다는 뜻입니다.
4. `info_score`는 추천 점수가 아니라 데이터 완성도 점수입니다. 사용자의 적합도나 정책 우선순위로 해석하면 안 됩니다.
5. `application_url`이 없으면 신청 버튼을 숨겨야 합니다.
6. `source_url`이 있으면 출처 링크로 표시해야 합니다.
7. 원본에 없는 신청방법, 제출서류, 조건은 임의 생성하면 안 됩니다.
8. 결측 필드는 빈 문자열로 유지합니다. 프론트엔드에서 빈 값은 숨김 처리하는 것을 권장합니다.

## 5. RAG 구현 주의사항

- `chunks.jsonl`의 `content`만 임베딩 본문으로 사용하고, 나머지는 metadata로 저장하는 방식을 권장합니다.
- 검색 결과는 `policy_id` 기준으로 `policies.json`의 상세 데이터와 조인합니다.
- 답변 생성 시 원본에 없는 신청방법/제출서류/조건을 추측해서 만들면 안 됩니다.
- `needs_detail_check=true`인 경우 답변에 “상세 확인이 필요한 항목”임을 표시하거나 출처 링크 확인을 유도하는 것이 안전합니다.
