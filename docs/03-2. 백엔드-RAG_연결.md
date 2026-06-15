# 백엔드 / RAG 전달 문서

## 0. 전달 파일 목록

| 용도 | 파일 |
|---|---|
| 백엔드 기본 데이터 | `data/processed/opportunities.json` |
| RAG 임베딩 데이터 | `data/processed/opportunity_chunks.jsonl` |
| Ground Truth 평가셋 | `tests/evaluation_dataset.jsonl` |
| 검수 참고 | `data/processed/missing_report.csv` |
| 검수 참고 | `data/processed/column_summary.csv` |
| 검수 참고 | `data/processed/duplicate_title_report.csv` |

---

## 1. 백엔드 담당자

백엔드는 다음 파일을 사용한다.

```text
data/processed/opportunities.json
```

상세 연결 key는 `item_id`이다.

source_category에 따라 화면 뱃지를 나눌 수 있다.

- `policy`: 청년정책
- `startup_notice`: 창업지원
- `training`: 교육·훈련

`application_url`이 없으면 신청 버튼은 숨기고, `source_url`이 있으면 출처 보기 링크로 표시한다.

### 데이터 해석 주의사항

- `item_id`를 기본 key로 사용해야 한다. `title`은 중복될 수 있으므로 URL path, DB primary key, 상세 조회 key로 사용하면 안 된다.
- `info_score`는 추천 점수가 아니라 **데이터 완성도 점수**다. 사용자 적합도나 정책 우선순위로 해석하면 안 된다.
- `needs_detail_check=true`는 원본 상세 정보(신청방법, 제출서류, URL, 심사방법 등)가 부족할 수 있다는 의미다.
- 원본에 없는 신청방법, 제출서류, 자격조건은 임의로 생성하지 않는다.
- 결측치는 빈 문자열로 유지되어 있다. 프론트엔드에서 빈 값은 숨김 처리를 권장한다.

## 2. RAG 담당자

RAG는 다음 파일을 사용한다.

```text
data/processed/opportunity_chunks.jsonl
```

- `content`: 임베딩 대상
- `metadata`: Chroma metadata — `item_id`, `title`, `source_category`, `domain`, `section`, `source_url`, `application_url`, `needs_detail_check`, `info_score`
- `item_id`: 백엔드 상세 데이터 연결 key

### RAG 구현 주의사항

- `content`만 임베딩 본문으로 사용하고, 나머지는 metadata로 저장한다.
- 검색 결과는 `item_id` 기준으로 `opportunities.json` 상세 데이터와 조인한다.
- 답변 생성 시 원본에 없는 신청방법/제출서류/조건을 추측해서 만들면 안 된다.
- `needs_detail_check=true`인 경우 답변에 "상세 확인이 필요한 항목"임을 표시하거나 출처 링크 확인을 유도하는 것이 안전하다.

## 3. 검색 결과 표시 제안

training 데이터가 많으므로 전체 검색에서는 source_category별 균형 노출을 권장한다.

예시:

- 정책 3개
- 창업공고 3개
- 교육훈련 3개

또는 사용자 질의 의도에 따라 source_category 가중치를 적용한다.

- 주거/복지/수당 → policy 우선
- 창업/사업화/IR → startup_notice 우선
- 교육/국비/AI/파이썬 → training 우선


## 4. Ground Truth 평가 데이터셋

RAG 검색 품질 검증을 위해 아래 파일을 제공한다.

```text
tests/evaluation_dataset.jsonl
```

각 row는 사용자 질문 `question`과 정답으로 기대되는 `answer_item_ids`를 포함한다.

검증 스크립트:

```bash
python scripts/validate_evaluation_dataset.py
```

검증 결과 `missing_item_ids=0`으로, Ground Truth의 정답 ID가 최종 통합 데이터 `opportunities.json`에 모두 존재함을 확인했다.

---

## 5. 데이터 재생성 방법

```bash
cd youth-policy-rag-agent
python scripts/preprocess_opportunities.py
python scripts/check_data_quality.py
```

---

## 6. 추가 참고 문서

작업 전에 아래 문서를 확인하는 것을 권장한다.

| 문서 | 내용 |
|---|---|
| `docs/data_dictionary.md` | 필드별 의미, 타입, 화면 처리 기준 |
| `docs/preprocessing_guide.md` | 전처리 단계, `info_score`, `needs_detail_check`, `raw_text`, chunk 생성 방식 |
| `docs/backend_data_schema.md` | 백엔드/RAG 구현 시 스키마 주의사항 |
