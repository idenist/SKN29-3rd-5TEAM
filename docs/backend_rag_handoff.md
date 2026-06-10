# 백엔드 / RAG 전달 문서

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

## 2. RAG 담당자

RAG는 다음 파일을 사용한다.

```text
data/processed/opportunity_chunks.jsonl
```

- `content`: 임베딩 대상
- `metadata`: Chroma metadata
- `item_id`: 백엔드 상세 데이터 연결 key

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
