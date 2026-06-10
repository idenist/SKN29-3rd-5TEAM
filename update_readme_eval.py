from pathlib import Path
import re

p = Path("README.md")
s = p.read_text(encoding="utf-8")

block = r"""
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
"""

start = "<!-- EVAL_START -->"
end = "<!-- EVAL_END -->"
new = f"{start}\n{block}\n{end}"

if start in s and end in s:
    s = re.sub(f"{start}.*?{end}", new, s, flags=re.S)
else:
    s = s.rstrip() + "\n\n" + new + "\n"

p.write_text(s, encoding="utf-8")
print("README 평가표 반영 완료")