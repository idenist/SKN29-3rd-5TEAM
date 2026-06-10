# opportunities / chunks 스키마 문서

## 1. 공통 key

모든 데이터 연결 기준은 `item_id`이다.

- 정책: `policy_...`
- 창업공고: `startup_...`
- 교육훈련: `training_...`

## 2. opportunities.json

백엔드 검색 결과 및 상세 화면에 사용하는 통합 데이터이다.

필수적으로 봐야 할 필드:

- `item_id`
- `source_category`
- `domain`
- `title`
- `summary`
- `target_text`
- `benefit_text`
- `region`
- `application_period_text`
- `program_period_text`
- `organization`
- `application_url`
- `source_url`
- `raw_text`
- `info_score`
- `needs_detail_check`

## 3. opportunity_chunks.jsonl

RAG 임베딩용 JSONL 파일이다.

각 라인은 하나의 chunk이며, `content`를 임베딩한다.

## 4. source_category

- `policy`: 온통청년 정책
- `startup_notice`: K-Startup 청년 HIGH 창업공고
- `training`: HRD 청년 HIGH 교육·훈련 과정

## 5. 화면 표시 원칙

- `application_url`이 없으면 신청 버튼을 숨긴다.
- `source_url`이 있으면 출처 보기로 표시한다.
- source_category별 뱃지를 표시한다.
  - policy: 청년정책
  - startup_notice: 창업지원
  - training: 교육·훈련

## 6. 주의사항

원본에 없는 신청방법, 제출서류, 조건은 임의 생성하지 않는다.
