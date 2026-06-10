# 청년 정책 통합 탐색 에이전트 - 데이터 산출물

온통청년 청년정책 데이터를 기반으로 RAG 질의응답 시스템을 만들기 위한 데이터 엔지니어링 산출물입니다.  
데이터 담당자는 원본 API 데이터를 보존하고, 백엔드/RAG 담당자가 바로 사용할 수 있는 `policies.json`과 `chunks.jsonl`을 제공합니다.

## 1. 데이터 담당 산출물 설명

- `data/raw/youthcenter_api/youth_policy_raw.csv`: 온통청년 API에서 확보한 원본 CSV입니다. 절대 덮어쓰지 않습니다.
- `data/raw/youthcenter_api/youth_policy_raw.json`: 원본 CSV를 JSON records 형태로 변환한 보존용 파일입니다.
- `data/processed/policies_cleaned.csv`: 전처리 후 사람이 검토하기 쉬운 CSV입니다.
- `data/processed/policies.json`: 백엔드 API와 화면 표시에서 사용하는 정책 단위 JSON입니다.
- `data/processed/chunks.jsonl`: RAG/Chroma 임베딩용 청크 파일입니다.
- `data/processed/missing_report.csv`: 표준 필드별 결측 현황입니다.
- `data/processed/column_summary.csv`: 원본 컬럼별 결측/샘플 요약입니다.
- `data/processed/duplicate_policy_name_report.csv`: 정책명 중복 확인용 리포트입니다.
- `docs/data_dictionary.md`: 정책 데이터 필드 설명서입니다. 백엔드/RAG 담당자가 가장 먼저 확인해야 합니다.
- `docs/preprocessing_guide.md`: 전처리 방식과 파생 필드 생성 기준을 설명합니다.

## 2. 폴더 구조

```text
youth-policy-rag-agent/
├─ README.md
├─ data/
│  ├─ raw/
│  │  ├─ youthcenter_api/
│  │  │  ├─ youth_policy_raw.csv
│  │  │  └─ youth_policy_raw.json
│  │  └─ source_pdfs/
│  ├─ processed/
│  │  ├─ policies.json
│  │  ├─ chunks.jsonl
│  │  ├─ policies_cleaned.csv
│  │  ├─ missing_report.csv
│  │  ├─ column_summary.csv
│  │  └─ duplicate_policy_name_report.csv
│  └─ vector_db/
├─ scripts/
│  ├─ collect_youthcenter.py
│  ├─ check_data_quality.py
│  ├─ crawl_policy_detail.py
│  ├─ parse_pdf.py
│  ├─ preprocess_policies.py
│  └─ build_vector_db.py
└─ docs/
   ├─ 데이터_전처리_문서.md
   ├─ data_dictionary.md
   ├─ preprocessing_guide.md
   ├─ backend_data_schema.md
   └─ backend_handoff_note.md
```

## 3. 실행 순서

```bash
cd youth-policy-rag-agent
python scripts/preprocess_policies.py
python scripts/check_data_quality.py
```

선택적으로 원본 수집 로직을 확장할 경우:

```bash
python scripts/collect_youthcenter.py
```


## 4. 문서 읽는 순서

백엔드/RAG 담당자는 아래 순서로 문서를 확인하는 것을 권장합니다.

1. `docs/data_dictionary.md`: 필드별 의미, 사용처, 금지사항 확인
2. `docs/preprocessing_guide.md`: 전처리 로직과 파생 필드 생성 기준 확인
3. `docs/backend_data_schema.md`: 백엔드/RAG 구현 시 스키마와 주의사항 확인
4. `docs/backend_handoff_note.md`: 실제 인수인계 요약 확인

## 5. 스크립트 용도

### `scripts/collect_youthcenter.py`
온통청년 API 수집 스크립트 자리입니다. 현재 MVP에서는 이미 확보한 원본 CSV를 사용합니다. 추후 API 키 기반 재수집 로직을 추가할 수 있습니다.

### `scripts/check_data_quality.py`
`policies.json`, `chunks.jsonl`, `missing_report.csv`를 기준으로 정책 수, 청크 수, `policy_id` 중복 여부, 주요 결측 현황을 확인합니다.

### `scripts/preprocess_policies.py`
원본 CSV를 로드하고 다음 처리를 수행합니다.

- 컬럼명 표준 스키마 매핑
- 결측치 정리
- `policy_id` 기준 중복 제거
- 나이 조건 정제
- 신청기간 정제
- `domain` 생성
- `info_score` 생성
- `needs_detail_check` 생성
- `raw_text` 생성
- `policies.json` 저장
- `chunks.jsonl` 저장

### 확장용 스크립트

- `scripts/crawl_policy_detail.py`: MVP 1차 범위에서는 실제 구현하지 않고, 추후 정책 상세 페이지 크롤링용입니다.
- `scripts/parse_pdf.py`: MVP 1차 범위에서는 실제 구현하지 않고, 추후 PDF 파싱용입니다.
- `scripts/build_vector_db.py`: MVP 1차 범위에서는 실제 구현하지 않고, 추후 Chroma Vector DB 생성용입니다.

## 6. 백엔드/RAG 담당자가 사용하는 방법

### 백엔드 담당자

`data/processed/policies.json`을 정책 목록/상세 API의 기본 데이터로 사용합니다.  
모든 연결 기준은 `policy_id`입니다. `policy_name`은 중복될 수 있으므로 key로 사용하면 안 됩니다.

### RAG 담당자

`data/processed/chunks.jsonl`을 한 줄씩 읽어 Chroma 등의 Vector DB에 임베딩합니다.  
각 청크에는 `chunk_id`, `policy_id`, `policy_name`, `domain`, `section`, `content`가 포함되어 있어 바로 metadata로 사용할 수 있습니다.

## 7. 주의사항

- 원본 데이터는 절대 덮어쓰지 않습니다.
- 결측치는 임의로 채우지 않습니다.
- 출처 없는 보완 정보는 추가하지 않습니다.
- 정책명은 중복될 수 있으므로 식별자로 사용하지 않습니다.
- 모든 연결 기준은 `policy_id`입니다.
- `chunks.jsonl`은 RAG 담당자가 바로 Chroma 임베딩에 사용할 수 있어야 합니다.
