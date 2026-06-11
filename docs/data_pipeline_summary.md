# 데이터 전처리 파이프라인 요약

## 1. 전체 흐름

```text
데이터 수집
→ 원본 raw 데이터 보존
→ 출처별 전처리
→ 컬럼 표준화
→ 결측치 확인
→ 중복 제거
→ 청년 관련성 분류
→ raw_text 생성
→ 공통 스키마 통합
→ RAG 청크 생성
→ KoNLPy Okt 형태소 분석
→ 불용어 제거
→ BoW / TF-IDF 키워드 리포트 생성
→ Gensim Word2Vec / FastText 샘플 학습 리포트 생성
→ Ground Truth 평가 데이터셋 추가
→ Ground Truth answer_item_ids와 opportunities.json item_id 연결 검증
→ 최종 백엔드/RAG 산출물 생성
```

## 2. 단계별 산출물

| 단계 | 입력 | 처리 | 출력 |
|---|---|---|---|
| 수집 | API 응답 | 원본 저장 | `data/raw/` |
| 출처별 전처리 | raw 데이터 | 컬럼 표준화, 결측/중복 확인 | 출처별 processed 파일 |
| 청년 관련성 분류 | 정제 데이터 | high/medium/low 분류 | high 데이터 |
| 통합 | high 데이터 | 공통 스키마 매핑 | `opportunities.json` |
| 청킹 | 통합 데이터 | search_profile chunk 생성 | `opportunity_chunks.jsonl` |
| 데이터 검증 | 통합 데이터/청크 | 건수, 중복, 결측 확인 | `data/reports/*` |
| KoNLPy 형태소 분석 | 통합 텍스트 | Okt 기반 명사 추출, 불용어 제거 | `opportunities_with_keywords.json`, `konlpy_keyword_report.csv` |
| BoW/TF-IDF 분석 | 정규화 텍스트 | 키워드 빈도 및 중요도 분석 | `bow_keyword_report.csv`, `tfidf_keyword_report.csv` |
| Word2Vec/FastText | 명사 토큰 | Gensim 샘플 학습 및 유사어 리포트 생성 | `word2vec_fasttext_status_report.csv` |
| Ground Truth | 평가 질문/정답 item_id | JSONL 형식 검증, 정답 item_id 연결 검증 | `tests/evaluation_dataset.jsonl`, `evaluation_dataset_summary.csv` |
| 문서화 | 산출물 | 스키마, 청킹, 전처리, 평가 대응 문서화 | `docs/`, `README.md` |

## 3. 최종 데이터 수량

| 항목 | 수량 |
|---|---:|
| 최종 통합 데이터 | 26,803 |
| RAG 청크 | 33,950 |
| 온통청년 정책 | 2,611 |
| K-Startup 청년 HIGH 창업공고 | 3,789 |
| HRD 청년 HIGH 교육훈련 | 20,403 |
| Ground Truth 평가 질문 | 50 |

## 4. 핵심 실행 스크립트

| 스크립트 | 역할 |
|---|---|
| `scripts/build_opportunities.py` | 통합 데이터 재생성 |
| `scripts/validate_final_dataset.py` | 최종 데이터 건수, 중복, 결측, 청크 검증 |
| `scripts/analyze_korean_text.py` | KoNLPy Okt 형태소 분석 및 키워드 추출 |
| `scripts/build_text_features.py` | BoW, TF-IDF, Word2Vec/FastText 리포트 생성 |
| `scripts/validate_evaluation_dataset.py` | Ground Truth 정답 item_id 검증 |

## 5. Ground Truth 검증 단계

RAG 검색 품질 평가를 위해 `tests/evaluation_dataset.jsonl`을 추가했다.

검증 스크립트는 `answer_item_ids`가 `data/processed/opportunities.json`의 `item_id`에 실제 존재하는지 확인한다.

검증 결과:

```text
rows=50
missing_field_rows=0
empty_answer_rows=0
missing_item_ids=0
duplicate_questions=0
```

따라서 Ground Truth 평가 데이터셋의 정답 ID가 최종 통합 데이터와 정상적으로 연결되어 있음을 확인했다.
