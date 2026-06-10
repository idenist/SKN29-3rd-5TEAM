# 청년 지원 통합 탐색 에이전트 데이터 파이프라인

## 1. 프로젝트 개요

본 패키지는 청년 지원 정보를 RAG 기반으로 탐색하기 위한 최종 데이터 산출물이다.

기존 v2 통합 데이터에 평가계획서의 데이터 전처리 요구 항목을 반영하여,
데이터 설명서, 전처리 파이프라인 문서, KoNLPy 형태소 분석 스크립트, 불용어 처리 리포트, BoW/TF-IDF 리포트, 청킹 전략 문서를 추가했다.

최종 백엔드 데이터는 `data/processed/opportunities.json`이며,
RAG 임베딩 데이터는 `data/processed/opportunity_chunks.jsonl`이다.

## 2. 현재 통합된 데이터 출처

| source_category | 데이터 | 출처 | 통합 기준 | 건수 |
|---|---|---|---|---:|
| `policy` | 청년정책 | 온통청년 Open API | 전체 정책 데이터 | 2,611 |
| `startup_notice` | 창업지원 공고 | K-Startup / 창업진흥원 Open API | `youth_relevance = high` | 3,789 |
| `training` | 교육·취업 훈련 과정 | 고용24/HRD 국민내일배움카드 훈련과정 API | `youth_relevance = high` | 20,403 |

## 3. 데이터 출처 URL

1. 온통청년 Open API  
   - https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiGuide
   - https://www.data.go.kr/data/15143273/openapi.do

2. K-Startup / 창업진흥원 Open API  
   - https://www.data.go.kr/data/15125364/openapi.do
   - https://nidview.k-startup.go.kr/view/public/kisedKstartupService/announcementInformation

3. 고용24/HRD Open API  
   - https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do

## 4. 최종 데이터 수량

| 항목 | 수량 |
|---|---:|
| 최종 통합 데이터 `opportunities.json` | 26,803건 |
| 최종 RAG 청크 `opportunity_chunks.jsonl` | 33,950개 |
| 온통청년 정책 | 2,611건 |
| K-Startup 청년 HIGH 창업공고 | 3,789건 |
| HRD 청년 HIGH 교육훈련 | 20,403건 |
| 신청 URL 보유 데이터 | 2,538건 |
| 출처 URL 보유 데이터 | 25,851건 |

## 5. 최종 산출물

| 파일 | 용도 |
|---|---|
| `data/processed/opportunities.json` | 백엔드 검색 결과 및 상세 페이지용 통합 데이터 |
| `data/processed/opportunity_chunks.jsonl` | Chroma 등 Vector DB 임베딩용 JSONL |
| `data/processed/opportunities_with_keywords.json` | 형태소/키워드 분석 결과가 추가된 평가용 데이터 |
| `data/reports/konlpy_keyword_report.csv` | KoNLPy 또는 fallback 기반 키워드 빈도 리포트 |
| `data/reports/bow_keyword_report.csv` | BoW 키워드 빈도 리포트 |
| `data/reports/tfidf_keyword_report.csv` | TF-IDF 기반 주요 키워드 리포트 |
| `data/reports/word2vec_fasttext_status_report.csv` | Word2Vec/FastText 적용 상태 및 샘플 결과 |
| `data/reports/missing_value_report.csv` | 필드별 결측 리포트 |
| `data/reports/duplicate_check_report.csv` | `item_id` 중복 확인 리포트 |
| `data/reports/chunk_length_report.csv` | 청크 길이 통계 |
| `docs/data_dictionary.md` | 데이터 설명서 |
| `docs/chunking_strategy.md` | RAG/Graph 입력용 청킹 전략 문서 |
| `docs/text_preprocessing.md` | 텍스트 전처리 및 형태소 분석 문서 |
| `docs/data_pipeline_summary.md` | 데이터 수집→정제→통합 파이프라인 문서 |
| `docs/evaluation_checklist.md` | 평가 지표 대응표 |

## 6. 폴더 구조

```text
youth-support-data-final-evaluation-package/
├─ README.md
├─ requirements.txt
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ reports/
├─ scripts/
└─ docs/
```

## 7. 데이터 수집 및 전처리 흐름

```text
1. 온통청년 / K-Startup / HRD 데이터 수집
2. 원본 raw 데이터 보존
3. 출처별 전처리
4. 컬럼 표준화
5. 결측치 및 중복 확인
6. 청년 관련성 high/medium/low 분류
7. high 데이터 중심으로 서비스 통합
8. 공통 스키마 `opportunities.json` 생성
9. RAG용 `opportunity_chunks.jsonl` 생성
10. KoNLPy 형태소 분석 및 불용어 처리
11. BoW / TF-IDF / Word2Vec / FastText 분석 리포트 생성
12. 평가용 문서 및 리포트 정리
```

## 8. 평가 지표 대응 현황

| 평가 항목 | 반영 내용 | 산출물 |
|---|---|---|
| 데이터셋 선정 타당성 | 청년정책, 창업지원, 교육훈련 3개 공식 출처 선정 | `docs/source_notes.md` |
| 편향성 처리 | 청년 관련성 high 기준으로 서비스 통합 범위 제한 | `docs/data_pipeline_summary.md` |
| 중복 제거 | `item_id` 기준 중복 확인 | `data/reports/duplicate_check_report.csv` |
| 결측치 처리 | 필드별 결측률 산출, 임의 보완 금지 | `data/reports/missing_value_report.csv` |
| 정규표현식 텍스트 정규화 | HTML/URL/특수문자/공백 정리 | `scripts/analyze_korean_text.py` |
| KoNLPy 형태소 분석 | Okt 사용 시도, 미설치 시 fallback 기록 | `data/reports/konlpy_keyword_report.csv` |
| 불용어 처리 | 행정/공통어 제거, 핵심 도메인어 보존 | `data/reports/stopword_report.csv` |
| BoW | CountVectorizer 기반 키워드 빈도 | `data/reports/bow_keyword_report.csv` |
| TF-IDF | 전체/source_category/domain별 주요 키워드 | `data/reports/tfidf_keyword_report.csv` |
| Word2Vec/FastText | gensim 가능 시 샘플 학습, 서비스 검색에는 미사용 | `data/reports/word2vec_fasttext_status_report.csv` |
| 청킹 전략 | search_profile chunk 및 향후 Recursive/Semantic 전략 문서화 | `docs/chunking_strategy.md` |
| 데이터 스키마 문서화 | 필드 설명 및 백엔드/RAG 연결 기준 작성 | `docs/data_dictionary.md`, `docs/opportunity_schema.md` |
| 파이프라인 문서화 | 수집→전처리→통합→청크→텍스트 분석 흐름 작성 | `docs/data_pipeline_summary.md` |
| 데이터 수량 문서화 | source_category별 건수 및 청크 수 기록 | `README.md`, `data/processed/preprocessing_summary.json` |

## 9. KoNLPy 형태소 분석 및 불용어 처리

`scripts/analyze_korean_text.py`는 다음 필드를 결합하여 분석한다.

- `title`
- `summary`
- `target_text`
- `benefit_text`
- `raw_text`

KoNLPy `Okt` 사용을 우선 시도하며, Windows/Java 환경 문제로 KoNLPy 실행이 어려우면 정규표현식 기반 fallback 토큰화를 수행하고 해당 사실을 리포트에 기록한다.

## 10. BoW / TF-IDF / Word2Vec / FastText 대응

`scripts/build_text_features.py`는 다음 리포트를 생성한다.

- `bow_keyword_report.csv`
- `tfidf_keyword_report.csv`
- `word2vec_fasttext_status_report.csv`

Word2Vec/FastText는 실제 RAG 검색 필수 요소가 아니며, 평가 및 분석 보조용으로만 사용한다.

## 11. RAG 청킹 전략

현재 청킹은 `item_id` 기준 search_profile chunk를 생성한다.

- 임베딩 대상: `content`
- metadata: `item_id`, `source_category`, `domain`, `title`, `source_url`, `application_url`, `info_score`, `needs_detail_check`

자세한 내용은 `docs/chunking_strategy.md`에 작성했다.

## 12. 백엔드 사용 방법

백엔드는 다음 파일을 사용한다.

```text
data/processed/opportunities.json
```

상세 페이지 연결 key는 `item_id`이다.

`application_url`이 없으면 신청 버튼을 숨기고, `source_url`이 있으면 출처 링크로 표시한다.

## 13. RAG 사용 방법

RAG 담당자는 다음 파일을 사용한다.

```text
data/processed/opportunity_chunks.jsonl
```

`content`를 임베딩하고 `metadata`를 Chroma metadata로 저장한다.

## 14. 제외한 데이터와 이유

공모전·경진대회·모집공고 데이터는 이번 최종 범위에서 제외했다.

제외 이유:

- 공식 OpenAPI 기반의 안정적인 다건 수집원이 명확하지 않음
- 현재 통합 데이터만으로 정책/창업/교육훈련 영역을 충분히 구성함
- 평가 대응을 위해 추가 수집보다 전처리 품질과 문서화를 우선함

## 15. 실행 방법

기본 통합 파일 재생성:

```bash
python scripts/build_opportunities.py
```

데이터 검증:

```bash
python scripts/validate_final_dataset.py
```

KoNLPy 형태소 분석 및 키워드 리포트 생성:

```bash
python scripts/analyze_korean_text.py
```

BoW / TF-IDF / Word2Vec / FastText 분석:

```bash
python scripts/build_text_features.py
```

전체 평가 대응 실행 순서:

```bash
python scripts/build_opportunities.py
python scripts/validate_final_dataset.py
python scripts/analyze_korean_text.py
python scripts/build_text_features.py
```

## 16. 주의사항

- 원본 raw 데이터는 절대 덮어쓰지 않는다.
- 원본에 없는 신청방법, 제출서류, 조건은 임의 생성하지 않는다.
- 모든 연결 기준은 `item_id`이다.
- KoNLPy는 Java 환경이 필요할 수 있다.
- KoNLPy 실행이 어려운 경우 fallback 토큰화를 사용하고 리포트에 기록한다.

<!-- EVAL_START -->

---

## 평가계획서 기준 데이터 전처리 반영 현황

본 데이터 패키지는 LLM 프로젝트 평가계획서의 `수집된 데이터 및 데이터 전처리 문서` 항목에 맞춰 보강하였다.

### 1. 데이터 수집 및 구축의 적절성

| 평가 기준 | 반영 내용 | 산출물 |
|---|---|---|
| NLP/RAG 목적에 맞는 데이터셋 선정 | 청년 지원 탐색에 필요한 정책, 창업지원, 교육훈련 데이터 선정 | `data/processed/opportunities.json` |
| 데이터 출처 명확화 | 온통청년, K-Startup, 고용24/HRD 출처 URL 명시 | `docs/source_notes.md` |
| 데이터 편향성 관리 | 공모전 데이터는 안정적 공식 API 부재로 제외 | `README.md`, `docs/source_notes.md` |
| 중복 제거 | `item_id` 기준 중복 검증 | `data/reports/duplicate_check_report.csv` |
| 결측치 처리 | 주요 필드별 결측률 리포트 생성, 임의 보완 금지 | `data/reports/missing_value_report.csv` |

### 2. 텍스트 전처리 및 형태소 분석

| 평가 기준 | 반영 내용 | 산출물 |
|---|---|---|
| 정규표현식 기반 정규화 | HTML, URL, 특수문자, 반복 공백 정리 | `scripts/analyze_korean_text.py` |
| KoNLPy 형태소 분석 | KoNLPy Okt 기반 명사 추출 적용 | `data/reports/konlpy_keyword_report.csv` |
| 불용어 처리 | 일반 불용어 제거, 핵심 도메인 단어 보존 | `data/reports/stopword_report.csv` |
| BoW 분석 | CountVectorizer 기반 키워드 리포트 생성 | `data/reports/bow_keyword_report.csv` |
| TF-IDF 분석 | TF-IDF 기반 주요 키워드 리포트 생성 | `data/reports/tfidf_keyword_report.csv` |
| Word2Vec/FastText 검토 | gensim 가능 시 분석, 불가 시 사유 기록 | `data/reports/word2vec_fasttext_status_report.csv` |

### 3. RAG/Graph 최적화 청킹 전략

| 평가 기준 | 반영 내용 | 산출물 |
|---|---|---|
| Vector DB 입력용 청킹 | `content`를 임베딩 대상으로 사용 | `data/processed/opportunity_chunks.jsonl` |
| 메타데이터 설계 | `item_id`, `source_category`, `domain`, `title`, `source_url` 포함 | `data/processed/opportunity_chunks.jsonl` |
| 청킹 전략 문서화 | search_profile chunk 및 Recursive/Semantic Chunking 개선안 문서화 | `docs/chunking_strategy.md` |
| Graph DB 확장 가능성 | `organization`, `region`, `domain`, `source_category`를 노드/관계 후보로 정의 | `docs/chunking_strategy.md` |

### 4. 문서화 완성도

| 평가 기준 | 반영 내용 | 산출물 |
|---|---|---|
| 데이터 스키마 문서화 | `opportunities.json`, `opportunity_chunks.jsonl` 필드 설명 | `docs/data_dictionary.md`, `docs/opportunity_schema.md` |
| 전처리 파이프라인 문서화 | 수집, 정제, 통합, 청킹, 형태소 분석 흐름 정리 | `docs/data_pipeline_summary.md` |
| 데이터 수량 기록 | 전체 건수, source_category별 건수, 청크 수 기록 | `data/processed/preprocessing_summary.json` |
| 백엔드/RAG 전달 문서 | 백엔드는 `opportunities.json`, RAG는 `opportunity_chunks.jsonl` 사용 | `docs/backend_rag_handoff.md` |

### 최종 데이터 수량

| source_category | 설명 | 건수 |
|---|---|---:|
| `policy` | 온통청년 청년정책 | 2,611 |
| `startup_notice` | K-Startup 청년 HIGH 창업지원 공고 | 3,789 |
| `training` | HRD/고용24 청년 HIGH 교육훈련 과정 | 20,403 |
| 전체 | 최종 통합 데이터 | 26,803 |

RAG용 청크 수는 총 33,950개이다.

### 데이터 출처 URL

| 출처 | URL |
|---|---|
| 온통청년 Open API | https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiGuide |
| K-Startup / 창업진흥원 Open API | https://www.data.go.kr/data/15125364/openapi.do |
| 고용24/HRD Open API | https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do |

### 제외한 데이터

공모전·경진대회·모집공고 데이터는 이번 최종 범위에서 제외하였다.

제외 사유는 다음과 같다.

- 공식 OpenAPI 기반의 안정적인 다건 수집원이 명확하지 않음
- 현재 통합 데이터만으로도 정책, 창업, 교육훈련 영역을 충분히 구성함
- 평가 대응을 위해 추가 수집보다 전처리 품질, 형태소 분석, 청킹 전략, 문서화를 우선함

---

## Ground Truth 평가 데이터셋 및 검증 스크립트

RAG 검색 결과를 평가하기 위해 `tests/evaluation_dataset.jsonl` 파일을 추가하였다.

이 파일은 실제 사용자가 입력할 만한 자연어 질문과, 정답으로 기대되는 `item_id`를 JSONL 형식으로 정리한 Ground Truth 데이터셋이다.

즉, 사용자가 질문했을 때 RAG 검색 결과가 실제 정답 데이터와 잘 연결되는지 확인하기 위한 평가용 데이터이다.

### 1. Ground Truth 데이터셋 위치

```text
tests/evaluation_dataset.jsonl
```

### 2. Ground Truth 데이터셋 구성

각 row는 다음 정보를 포함한다.

| 필드                | 설명                                           |
| ----------------- | -------------------------------------------- |
| `question`        | 사용자가 입력할 자연어 질문                              |
| `answer_item_ids` | 정답으로 기대되는 `opportunities.json`의 `item_id` 목록 |

예시는 다음과 같다.

```json
{
  "question": "청년 적금이나 자산 형성 지원 금융상품 있어?",
  "answer_item_ids": ["policy_..."]
}
```

이 구조를 통해 RAG 검색 결과가 실제 정답 데이터와 연결되는지 확인할 수 있다.

---

### 3. 검증 스크립트 위치

Ground Truth 데이터셋 검증을 위해 아래 스크립트를 추가하였다.

```text
scripts/validate_evaluation_dataset.py
```

이 스크립트는 다음 항목을 검증한다.

| 검증 항목       | 설명                                                   |
| ----------- | ---------------------------------------------------- |
| JSONL 형식 검증 | 각 줄이 정상적인 JSON 형식인지 확인                               |
| 필수 필드 검증    | `question`, `answer_item_ids` 필드 존재 여부 확인            |
| 빈 정답 검증     | `answer_item_ids`가 비어 있는지 확인                         |
| 정답 ID 검증    | `answer_item_ids`가 `opportunities.json`에 실제 존재하는지 확인 |
| 중복 질문 검증    | 동일한 질문이 중복되어 있는지 확인                                  |

---

### 4. 검증 실행 방법

패키지 루트 폴더에서 아래 명령어를 실행한다.

```bash
python scripts/validate_evaluation_dataset.py
```

---

### 5. 검증 결과

검증 결과는 다음과 같다.

```text
검증 완료: rows=50
- missing_field_rows=0
- empty_answer_rows=0
- missing_item_ids=0
- duplicate_questions=0
- summary=data\reports\evaluation_dataset_summary.csv
- detail=data\reports\evaluation_dataset_validation_errors.json
```

검증 결과의 의미는 다음과 같다.

| 항목                    | 결과 | 의미                                         |
| --------------------- | -: | ------------------------------------------ |
| `rows`                | 50 | 평가 질문 50개 존재                               |
| `missing_field_rows`  |  0 | 필수 필드 누락 없음                                |
| `empty_answer_rows`   |  0 | 정답 item_id가 비어 있는 질문 없음                    |
| `missing_item_ids`    |  0 | 모든 정답 item_id가 `opportunities.json`에 실제 존재 |
| `duplicate_questions` |  0 | 중복 질문 없음                                   |

특히 `missing_item_ids=0`이므로, Ground Truth에 등록된 정답 데이터가 최종 통합 데이터와 정상적으로 연결되어 있음을 확인했다.

---

### 6. 검증 리포트 산출물

검증 스크립트 실행 후 아래 리포트가 생성된다.

```text
data/reports/evaluation_dataset_summary.csv
data/reports/evaluation_dataset_validation_errors.json
```

| 파일                                          | 설명                    |
| ------------------------------------------- | --------------------- |
| `evaluation_dataset_summary.csv`            | Ground Truth 검증 결과 요약 |
| `evaluation_dataset_validation_errors.json` | 오류 발생 시 상세 내역 기록      |

따라서 본 패키지는 RAG 검색 품질 평가를 위한 Ground Truth 데이터셋과, 해당 데이터셋이 최종 통합 데이터와 정상 연결되는지 확인하는 검증 스크립트를 함께 포함한다.

<!-- EVAL_END -->
