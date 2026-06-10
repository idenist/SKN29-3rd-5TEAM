# RAG / Graph 최적화 청킹 전략

## 1. 현재 청킹 방식

현재 청킹은 `item_id`당 기본 `search_profile` chunk를 생성하는 방식이다.

각 chunk의 `content`는 다음 정보를 조합한다.

- 제목
- 요약
- 대상
- 지원내용 또는 훈련정보
- 지역
- 신청기간 또는 운영기간
- raw_text

## 2. metadata 설계

각 chunk에는 다음 metadata를 포함한다.

- `item_id`
- `source_category`
- `domain`
- `title`
- `source_url`
- `application_url`
- `info_score`
- `needs_detail_check`
- `youth_relevance`
- `startup_stage`
- `training_type`
- `is_digital_training`
- `is_job_seeker_friendly`

## 3. Vector DB 입력 방식

- 임베딩 대상: `content`
- 저장 metadata: `metadata`
- 상세 데이터 연결 key: `item_id`
- 백엔드 상세 정보 조회: `opportunities.json`에서 `item_id`로 연결

## 4. Graph DB 확장 가능성

Graph DB 확장 시 다음 값을 노드/관계 후보로 사용할 수 있다.

- `item_id`
- `source_category`
- `domain`
- `organization`
- `region`
- `training_type`
- `startup_stage`

예시 관계:

```text
청년지원항목 -[:BELONGS_TO]-> domain
청년지원항목 -[:PROVIDED_BY]-> organization
청년지원항목 -[:AVAILABLE_IN]-> region
청년지원항목 -[:HAS_SOURCE]-> source_category
```

## 5. 향후 개선안

현재는 item 단위 search_profile chunk를 사용한다.

향후 raw_text가 긴 데이터에 대해서는 다음 전략을 검토한다.

- Recursive Character Splitting
- chunk_size: 800~1000자
- chunk_overlap: 100~150자
- 의미 단위 Semantic Chunking
- source_category별 chunk size 차등 적용

## 6. 청크 품질 리포트

청크 수와 길이 통계는 다음 파일에 기록한다.

```text
data/reports/chunk_length_report.csv
```
