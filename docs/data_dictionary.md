# 데이터 설명서 / Data Dictionary

## 1. 문서 목적

이 문서는 백엔드, 프론트엔드, RAG 담당자가 `data/processed/policies.json`과 `data/processed/chunks.jsonl`을 같은 기준으로 이해하도록 만든 데이터 설명서입니다.

핵심 원칙은 다음과 같습니다.

- 정책을 식별할 때는 반드시 `policy_id`를 사용합니다.
- `policy_name`은 같은 이름이 여러 번 등장할 수 있으므로 고유 식별자로 사용하지 않습니다.
- 원본 데이터에 없는 신청방법, 제출서류, 조건, URL은 임의로 생성하지 않습니다.
- `info_score`는 추천 점수가 아니라 데이터 완성도 점수입니다.
- `needs_detail_check=true`는 사용자에게 답변하기 전 상세 확인이 필요한 데이터라는 뜻입니다.

## 2. 데이터 흐름 요약

```text
온통청년 원본 CSV
  ↓ scripts/preprocess_policies.py
정제 CSV / 정책 JSON / RAG 청크 JSONL / 품질 리포트
  ↓
백엔드 API, 프론트 화면, Chroma Vector DB 임베딩
```

## 3. 원본 데이터

| 항목 | 내용 |
|---|---|
| 원본 CSV | `data/raw/youthcenter_api/youth_policy_raw.csv` |
| 원본 JSON | `data/raw/youthcenter_api/youth_policy_raw.json` |
| 원본 성격 | 온통청년 청년정책 API 기반 데이터 |
| 보존 원칙 | 원본 파일은 절대 덮어쓰지 않음 |

## 4. 산출 데이터 요약

| 파일 | 용도 | 주요 사용자 |
|---|---|---|
| `data/processed/policies_cleaned.csv` | 사람이 보기 쉬운 검수용 정제 CSV | 데이터 담당자, PM |
| `data/processed/policies.json` | 정책 목록/상세 API용 표준 JSON | 백엔드, 프론트엔드 |
| `data/processed/chunks.jsonl` | RAG 임베딩용 청크 데이터 | RAG 담당자 |
| `data/processed/missing_report.csv` | 표준 필드별 결측 현황 | 데이터 담당자, PM |
| `data/processed/column_summary.csv` | 원본 컬럼별 결측/샘플 요약 | 데이터 담당자 |
| `data/processed/duplicate_policy_name_report.csv` | 정책명 중복 확인 리포트 | 백엔드, PM |

## 5. 현재 데이터 현황

| 항목 | 값 |
|---|---:|
| 정책 수 | 2,611건 |
| RAG 청크 수 | 9,758건 |
| `policy_id` 중복 | 0건 |
| `policy_id` 결측 | 0건 |
| `application_url` 결측 | 1,764건 |
| `source_url` 결측 | 952건 |
| `application_period_text` 결측 | 1,316건 |
| `needs_detail_check=true` | 2,409건 |
| `needs_detail_check=false` | 202건 |

주의: `needs_detail_check=true` 비율이 높은 이유는 온통청년 API 원본에서 신청 URL, 제출서류, 심사방법 등 상세 항목이 비어 있는 정책이 많기 때문입니다. 이 값은 데이터 오류가 아니라 “상세 검수 필요” 표시입니다.

## 6. 원본 컬럼 → 표준 필드 매핑

| 원본 컬럼 | 표준 필드 | 설명 |
|---|---|---|
| `plcyNo` | `policy_id` | 정책 고유 번호. 전체 시스템의 기본 key |
| `plcyNm` | `policy_name` | 정책명. 중복 가능 |
| `plcyKywdNm` | `keywords` | 정책 키워드 |
| `plcyExplnCn` | `policy_summary` | 정책 설명 |
| `lclsfNm` | `large_category` | 대분류 |
| `mclsfNm` | `middle_category` | 중분류 |
| `plcySprtCn` | `support_content` | 지원 내용 |
| `sprvsnInstCdNm` | `supervising_org` | 주관 기관 |
| `operInstCdNm` | `operating_org` | 운영 기관 |
| `bizPrdBgngYmd` | `business_start_date` | 사업 시작일 |
| `bizPrdEndYmd` | `business_end_date` | 사업 종료일 |
| `bizPrdEtcCn` | `business_period_note` | 사업 기간 기타 설명 |
| `aplyYmd` | `application_period_text` | 신청 기간 원문 |
| `plcyAplyMthdCn` | `application_method` | 신청 방법 |
| `aplyUrlAddr` | `application_url` | 신청 URL |
| `sbmsnDcmntCn` | `required_documents` | 제출 서류 |
| `srngMthdCn` | `screening_method` | 심사 방법 |
| `etcMttrCn` | `notes` | 기타 사항 |
| `refUrlAddr1` | `source_url` | 1차 출처 URL |
| `refUrlAddr2` | `source_url_2` | 2차 출처 URL |
| `sprtTrgtMinAge` | `age_min` | 최소 지원 연령 |
| `sprtTrgtMaxAge` | `age_max` | 최대 지원 연령 |
| `sprtTrgtAgeLmtYn` | `age_limit_yn` | 연령 제한 여부 원본값 |
| `earnMinAmt` | `income_min` | 소득 최소값 |
| `earnMaxAmt` | `income_max` | 소득 최대값 |
| `earnEtcCn` | `income_condition` | 소득 조건 설명 |
| `addAplyQlfcCndCn` | `additional_condition` | 추가 신청 자격 조건 |
| `ptcpPrpTrgtCn` | `participation_target` | 참여 제한 대상 |
| `zipCd` | `region_codes` | 지역 코드 |
| `frstRegDt` | `created_at` | 원본 최초 등록일 |
| `lastMdfcnDt` | `updated_at` | 원본 수정일 |

## 7. `policies.json` 필드 설명

| 필드 | 타입 | 설명 | 사용 시 주의사항 |
|---|---|---|---|
| `policy_id` | string | 정책 고유 ID | 반드시 기본 key로 사용 |
| `policy_name` | string | 정책명 | 중복 가능. key 사용 금지 |
| `domain` | string | `large_category > middle_category` 형태의 분야 | 필터/뱃지/RAG metadata 사용 가능 |
| `keywords` | string | 정책 키워드 | 검색 보조용 |
| `policy_summary` | string | 정책 설명 | 목록/상세/RAG 본문 사용 |
| `large_category` | string | 대분류 | 필터 사용 가능 |
| `middle_category` | string | 중분류 | 필터 사용 가능 |
| `support_content` | string | 지원 내용 | 상세 화면 핵심 본문 |
| `supervising_org` | string | 주관 기관 | 상세 화면 표시 |
| `operating_org` | string | 운영 기관 | 상세 화면 표시 |
| `age_min` | string | 정제된 최소 나이 | 빈 값 가능 |
| `age_max` | string | 정제된 최대 나이 | 빈 값 가능 |
| `age_text` | string | 화면 표시용 나이 조건 | 원본 나이값 기반 생성 |
| `application_period_text` | string | 신청 기간 원문 | 원문 보존 우선 |
| `application_start_date` | string | 추출 가능한 신청 시작일 | 추출 불가 시 빈 값 |
| `application_end_date` | string | 추출 가능한 신청 종료일 | 추출 불가 시 빈 값 |
| `business_start_date` | string | 사업 시작일 | YYYY-MM-DD로 가능한 범위 정제 |
| `business_end_date` | string | 사업 종료일 | YYYY-MM-DD로 가능한 범위 정제 |
| `business_period_note` | string | 사업 기간 설명 | 상세 화면 표시 |
| `application_method` | string | 신청 방법 | 비어 있으면 임의 생성 금지 |
| `application_url` | string | 신청 URL | 없으면 신청 버튼 숨김 |
| `required_documents` | string | 제출 서류 | 비어 있으면 임의 생성 금지 |
| `screening_method` | string | 심사 방법 | 비어 있으면 임의 생성 금지 |
| `income_min` | string | 소득 최소값 | 원본 기반. 숫자 필터는 추가 검증 필요 |
| `income_max` | string | 소득 최대값 | 원본 기반. 숫자 필터는 추가 검증 필요 |
| `income_condition` | string | 소득 조건 설명 | RAG 답변에 활용 가능 |
| `additional_condition` | string | 추가 자격 조건 | RAG 답변에 활용 가능 |
| `participation_target` | string | 참여 제한 대상 | 제외 조건 답변에 중요 |
| `region_codes` | string | 지역 코드 | 지역 필터 구현 시 별도 코드표 검토 필요 |
| `source_url` | string | 1차 출처 URL | 있으면 출처 링크로 표시 |
| `source_url_2` | string | 2차 출처 URL | 보조 출처 링크 |
| `notes` | string | 기타 사항 | 상세 화면 보조 정보 |
| `info_score` | integer | 데이터 완성도 점수 | 추천/랭킹 점수 아님 |
| `needs_detail_check` | boolean | 상세 확인 필요 여부 | true면 답변/화면에서 주의 표시 권장 |
| `raw_text` | string | 주요 필드를 합친 RAG 보조 원문 | RAG 본문 후보. 화면 노출용 아님 |
| `created_at` | string | 원본 등록일 | 관리 정보 |
| `updated_at` | string | 원본 수정일 | 관리 정보 |

## 8. `chunks.jsonl` 필드 설명

`chunks.jsonl`은 JSON Lines 형식입니다. 한 줄이 하나의 청크입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `chunk_id` | string | `{policy_id}::{section}` 형식의 청크 ID |
| `policy_id` | string | 정책 연결 key |
| `policy_name` | string | 검색 결과 제목 표시용 |
| `domain` | string | 분야 metadata |
| `section` | string | `summary`, `eligibility`, `application`, `source` 중 하나 |
| `content` | string | 임베딩할 본문 |
| `source_url` | string | 출처 URL metadata |
| `application_url` | string | 신청 URL metadata |
| `needs_detail_check` | boolean | 상세 확인 필요 여부 metadata |
| `info_score` | integer | 데이터 완성도 metadata |

## 9. 청크 섹션 구성

| section | 포함되는 주요 내용 | 용도 |
|---|---|---|
| `summary` | 정책 설명, 지원 내용 | 정책 검색의 기본 본문 |
| `eligibility` | 나이, 소득, 추가 자격, 참여 제한, 지역 | 사용자 조건 기반 검색 |
| `application` | 신청 기간, 신청 방법, 제출 서류, 심사 방법, 신청 URL | 신청 관련 질문 대응 |
| `source` | 주관/운영 기관, 출처 URL, 기타 사항 | 출처 확인 및 관리 정보 |

현재 청크 수는 다음과 같습니다.

| section | 청크 수 |
|---|---:|
| `summary` | 2,611 |
| `eligibility` | 2,611 |
| `application` | 1,925 |
| `source` | 2,611 |

## 10. 백엔드 화면 처리 권장 규칙

| 상황 | 처리 방식 |
|---|---|
| `application_url`이 빈 값 | 신청 버튼 숨김 |
| `source_url`이 존재 | 출처 링크 표시 |
| `source_url`이 빈 값 | 출처 버튼 숨김 또는 “출처 확인 필요” 표시 |
| `required_documents`가 빈 값 | 제출서류 영역 숨김 |
| `application_method`가 빈 값 | 신청방법 영역 숨김 |
| `needs_detail_check=true` | “상세 정보 확인 필요” 뱃지 표시 권장 |
| `info_score`가 낮음 | 운영자 검수 우선순위로만 사용 |

## 11. 금지사항

- 정책명을 key로 사용하지 않습니다.
- 신청 URL이 없는데 임의 버튼 링크를 만들지 않습니다.
- 제출서류가 없는데 일반적인 서류 목록을 추측해서 넣지 않습니다.
- 신청방법이 없는데 “온라인 신청” 등으로 임의 보정하지 않습니다.
- `info_score`를 사용자 추천 점수로 사용하지 않습니다.
- RAG 답변에서 원본에 없는 자격 조건을 만들어내지 않습니다.
