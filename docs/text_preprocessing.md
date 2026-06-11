# 텍스트 전처리 및 형태소 분석 문서

## 1. 분석 목적

평가계획서의 텍스트 전처리 및 형태소 분석 항목에 대응하기 위해 최종 통합 데이터에 대해 한국어 텍스트 정규화, KoNLPy Okt 기반 형태소 분석, 불용어 처리, BoW/TF-IDF 분석, Word2Vec/FastText 샘플 학습을 수행했다.

## 2. 분석 대상 필드

- `title`
- `summary`
- `benefit_text`
- `target_text`
- `raw_text`

## 3. 정규표현식 기반 정규화

`scripts/analyze_korean_text.py`와 `scripts/build_text_features.py`에서 다음 처리를 수행한다.

- HTML 태그 제거
- URL 제거 또는 별도 필드에 보존
- 특수문자 정리
- 줄바꿈/탭 제거
- 반복 공백 제거
- 한글/영문/숫자 중심 토큰 보존

정규표현식 처리는 형태소 분석 전 텍스트를 정리하기 위한 사전 정규화 단계이다.

## 4. KoNLPy Okt 형태소 분석

본 프로젝트는 KoNLPy Okt 기반 명사 추출을 기본 형태소 분석 방식으로 사용했다.

최종 실행 결과는 다음과 같다.

```text
analyzer: konlpy.Okt
rows: 26,803
output: data/processed/opportunities_with_keywords.json
keyword report: data/reports/konlpy_keyword_report.csv
```

Java/KoNLPy가 설치되지 않은 환경에서도 스크립트가 중단되지 않도록 `scripts/analyze_korean_text.py`에는 정규표현식 기반 예외 처리 경로를 포함했다. 이 경로는 환경 이식성을 위한 안전장치이며, 최종 제출 산출물은 KoNLPy Okt 실행 결과로 재생성하였다.

## 5. 불용어 처리

정책/공고/훈련 데이터에서 반복적으로 등장하지만 의미 구분에 기여도가 낮은 일반어를 불용어로 제거했다.

예시:

```text
지원, 사업, 대상, 신청, 기간, 관련, 가능, 정보, 제공, 과정, 공고, 모집, 안내
```

다만 다음과 같은 핵심 도메인 단어는 보존했다.

```text
청년, 창업, 교육, 취업, 주거, AI, 데이터, 인공지능, KDT, 디지털
```

산출물:

```text
data/reports/stopword_report.csv
```

## 6. BoW / TF-IDF 분석

`build_text_features.py`에서 CountVectorizer 기반 BoW 리포트와 TfidfVectorizer 기반 TF-IDF 리포트를 생성했다.

산출물:

```text
data/reports/bow_keyword_report.csv
data/reports/tfidf_keyword_report.csv
```

BoW는 자주 등장하는 단어를 확인하기 위한 빈도 기반 분석이며, TF-IDF는 source_category/domain별로 상대적으로 중요한 단어를 확인하기 위한 분석이다.

## 7. Word2Vec / FastText 샘플 학습

Gensim 기반 Word2Vec/FastText 샘플 학습을 수행했다.

산출물:

```text
data/reports/word2vec_fasttext_status_report.csv
```

최종 확인 상태:

```text
Word2Vec: trained_sample
FastText: trained_sample
```

해당 모델은 평가/분석용 샘플 학습이며 실제 서비스 검색에는 사용하지 않는다. 실제 RAG 검색은 `opportunity_chunks.jsonl`의 `content`를 Chroma 등 Vector DB에 임베딩하여 수행한다.

## 8. 최종 산출물 요약

| 산출물 | 설명 |
|---|---|
| `data/processed/opportunities_with_keywords.json` | KoNLPy Okt 기반 키워드가 추가된 평가용 데이터 |
| `data/reports/konlpy_keyword_report.csv` | 형태소 분석 기반 키워드 빈도 리포트 |
| `data/reports/stopword_report.csv` | 불용어 처리 기준 리포트 |
| `data/reports/bow_keyword_report.csv` | BoW 키워드 빈도 리포트 |
| `data/reports/tfidf_keyword_report.csv` | TF-IDF 키워드 리포트 |
| `data/reports/word2vec_fasttext_status_report.csv` | Word2Vec/FastText 샘플 학습 결과 리포트 |
