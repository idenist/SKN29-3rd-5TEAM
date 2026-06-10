# 텍스트 전처리 및 형태소 분석 문서

## 1. 분석 목적

평가계획서의 텍스트 전처리 및 형태소 분석 항목에 대응하기 위해 최종 통합 데이터에 대해 한국어 텍스트 정규화, 형태소 분석, 불용어 처리, BoW/TF-IDF 분석을 수행했다.

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

## 4. KoNLPy 형태소 분석

- 우선 사용 도구: `KoNLPy Okt`
- 추출 대상: 명사 중심
- KoNLPy 실행이 어려운 환경에서는 정규표현식 기반 fallback 토큰화를 수행한다.
- 현재 생성된 리포트의 analyzer 상태는 `data/reports/stopword_report.csv`에 기록되어 있다.

현재 패키지 생성 환경의 analyzer: `regex_fallback`

## 5. 불용어 처리

일반 행정어와 너무 흔한 단어를 제거한다.

예시:

- 지원
- 사업
- 대상
- 신청
- 기간
- 관련
- 가능
- 정보
- 제공
- 과정
- 공고
- 모집
- 안내

단, 다음 핵심 도메인 단어는 보존한다.

- 청년
- 창업
- 교육
- 주거
- 취업
- AI
- 데이터
- 인공지능
- 디지털
- KDT

## 6. BoW / TF-IDF 사용 목적

BoW와 TF-IDF는 실제 RAG 검색 파이프라인의 주 검색 방식이 아니라, 데이터셋의 키워드 분포와 source_category별 특징을 평가하기 위한 분석 리포트로 사용한다.

생성 파일:

- `data/reports/bow_keyword_report.csv`
- `data/reports/tfidf_keyword_report.csv`

## 7. Word2Vec / FastText 적용 여부

Word2Vec/FastText는 실제 서비스 검색 필수 요소가 아니다.

가능한 환경에서는 gensim 기반 샘플 학습을 수행하고, 불가능한 경우에는 `data/reports/word2vec_fasttext_status_report.csv`에 미적용 사유를 기록한다.

본 프로젝트의 실제 RAG 검색은 `opportunity_chunks.jsonl`의 `content`를 임베딩하여 수행한다.
