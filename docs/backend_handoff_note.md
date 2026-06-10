# 백엔드/RAG 담당자 인수인계 노트

## 1. 전달 파일

- 백엔드 기본 데이터: `data/processed/policies.json`
- RAG 임베딩 데이터: `data/processed/chunks.jsonl`
- 검수 참고 데이터: `data/processed/missing_report.csv`, `data/processed/column_summary.csv`, `data/processed/duplicate_policy_name_report.csv`

## 2. 백엔드 담당자 핵심 안내

`policies.json`은 정책 1개당 JSON 객체 1개로 구성되어 있습니다.  
목록 API, 상세 API, 필터 API의 기본 데이터로 사용할 수 있습니다.

반드시 `policy_id`를 기준으로 조회해야 합니다.  
`policy_name`은 중복될 수 있으므로 URL path, DB primary key, 상세 조회 key로 사용하면 안 됩니다.

`application_url`이 비어 있으면 신청 버튼을 숨겨야 합니다.  
`source_url`이 있으면 출처 링크로 표시해야 합니다.

## 3. RAG 담당자 핵심 안내

`chunks.jsonl`은 Chroma 등 Vector DB에 바로 넣기 위한 JSON Lines 파일입니다.  
각 줄의 `content`를 embedding text로 사용하고, `policy_id`, `policy_name`, `domain`, `section`, `source_url`, `application_url`, `needs_detail_check`, `info_score`를 metadata로 넣으면 됩니다.

검색 결과에서 사용자가 특정 정책 상세를 보려는 경우 `policy_id`로 `policies.json`과 연결합니다.

## 4. 데이터 해석 주의사항

- `info_score`는 추천 점수가 아닙니다. 데이터 완성도 점수입니다.
- `needs_detail_check=true`는 원본 상세 정보가 부족할 수 있다는 의미입니다.
- 원본에 없는 신청방법, 제출서류, 자격조건은 임의로 생성하지 않습니다.
- 결측치는 빈 문자열로 유지되어 있습니다.

## 5. 재생성 방법

```bash
cd youth-policy-rag-agent
python scripts/preprocess_policies.py
python scripts/check_data_quality.py
```

## 추가 확인 문서

백엔드/RAG 담당자는 작업 전에 아래 문서를 반드시 확인하는 것을 권장합니다.

- `docs/data_dictionary.md`: 필드별 의미, 타입, 화면 처리 기준
- `docs/preprocessing_guide.md`: 전처리 단계, `info_score`, `needs_detail_check`, `raw_text`, `chunks.jsonl` 생성 방식
- `docs/backend_data_schema.md`: 백엔드/RAG 구현 시 스키마 주의사항

특히 `policy_id`를 기본 key로 사용해야 하며, `policy_name`은 중복될 수 있으므로 key로 사용하면 안 됩니다.

