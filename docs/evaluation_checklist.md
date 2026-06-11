# 평가 지표 대응 체크리스트

## 1. 데이터 수집 및 구축의 적절성

- [x] NLP/RAG 목적에 맞는 데이터셋 선정
- [x] 온통청년, K-Startup, HRD 공식 출처 사용
- [x] 원본 raw 데이터 보존
- [x] 청년 관련성 high 기준으로 서비스 통합 범위 제한

## 2. 데이터 편향성, 중복성, 결측치 처리

- [x] 청년 관련성 high 기준 적용
- [x] `item_id` 기준 중복 확인
- [x] 필드별 결측률 리포트 생성
- [x] 원본에 없는 값 임의 생성 금지

산출물:

```text
data/reports/duplicate_check_report.csv
data/reports/missing_value_report.csv
data/reports/source_coverage_report.csv
```

## 3. 텍스트 전처리 및 형태소 분석

- [x] 정규표현식 기반 텍스트 정규화
- [x] KoNLPy Okt 기반 형태소 분석 완료
- [x] 불용어 처리
- [x] BoW 리포트 생성
- [x] TF-IDF 리포트 생성
- [x] Word2Vec/FastText 샘플 학습 완료

최종 형태소 분석 상태:

```text
analyzer: konlpy.Okt
rows: 26,803
```

산출물:

```text
data/processed/opportunities_with_keywords.json
data/reports/konlpy_keyword_report.csv
data/reports/stopword_report.csv
data/reports/bow_keyword_report.csv
data/reports/tfidf_keyword_report.csv
```

## 4. Word2Vec / FastText 밀집 표현 검증

Gensim 기반 Word2Vec/FastText 샘플 학습을 수행했다.

최종 상태:

```text
Word2Vec: trained_sample
FastText: trained_sample
```

산출물:

```text
data/reports/word2vec_fasttext_status_report.csv
```

해당 모델은 평가/분석용 샘플 학습이며 실제 서비스 검색에는 사용하지 않는다. 실제 서비스 검색은 RAG 임베딩을 사용한다.

## 5. RAG / Graph 최적화 청킹 전략

- [x] `item_id` 기반 search_profile chunk 생성
- [x] `content`와 `metadata` 분리
- [x] Vector DB 입력 구조 문서화
- [x] Graph DB 확장 가능성 문서화

산출물:

```text
data/processed/opportunity_chunks.jsonl
docs/chunking_strategy.md
```

## 6. Ground Truth 평가 데이터셋

- [x] RAG 검색 평가용 Ground Truth 데이터셋 추가
- [x] 정답 `answer_item_ids`와 `opportunities.json`의 `item_id` 연결 검증
- [x] 검증 스크립트 및 검증 리포트 생성

검증 결과:

```text
rows=50
missing_field_rows=0
empty_answer_rows=0
missing_item_ids=0
duplicate_questions=0
```

산출물:

```text
tests/evaluation_dataset.jsonl
scripts/validate_evaluation_dataset.py
data/reports/evaluation_dataset_summary.csv
data/reports/evaluation_dataset_validation_errors.json
```

## 7. 문서화 완성도

- [x] 데이터 설명서 작성
- [x] 데이터 스키마 문서 작성
- [x] 전처리 파이프라인 문서 작성
- [x] 청킹 전략 문서 작성
- [x] 백엔드/RAG 전달 문서 작성
- [x] 평가 지표 대응표 작성

산출물:

```text
README.md
docs/data_dictionary.md
docs/opportunity_schema.md
docs/data_pipeline_summary.md
docs/text_preprocessing.md
docs/chunking_strategy.md
docs/backend_rag_handoff.md
```
