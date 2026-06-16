# 청년 지원 통합 탐색 에이전트

## 1. 프로젝트 개요

- **서비스 명**: 이젠, 안쉼 (청년들이 정보 탐색의 피로에서 벗어나 안심할 수 있는 서비스)
- **기획 배경**: 청년 정책(온통청년), 창업 지원(K-Startup), 교육·훈련(고용24) 정보가 여러 기관에 파편화되어 있어 발생하는 청년들의 높은 탐색 비용과 정보 비대칭 문제를 해결하고자 함
- **핵심 가치**: 규칙 기반의 하드코딩 필터링을 넘어, **자연어 기반 조건 추출(NLP)**, **Hybrid RAG**, **LangGraph 기반 멀티 에이전트 워크플로우**를 결합하여 대용량 공공 데이터셋 안에서 사용자 맞춤형 청년 지원 정보를 큐레이션함

본 저장소는 청년 지원 정보를 통합 탐색하기 위한 **Streamlit 프론트엔드, FastAPI 백엔드, LangGraph 기반 RAG 파이프라인, Chroma Vector DB, Neo4j 보조 검색, 평가 및 sLLM 실험 산출물**을 포함한다.

초기에는 온통청년 정책 데이터 중심으로 출발했으나, 서비스 범위를 넓히기 위해 K-Startup 창업지원 공고와 고용24/HRD 교육훈련 과정까지 통합하였다. 최종 백엔드 데이터는 `data/processed/opportunities.json`이며, RAG 임베딩 데이터는 `data/processed/opportunity_chunks.jsonl`이다.

### 1.1 프로젝트 한눈에 보기

| 항목 | 내용 |
|---|---|
| 서비스 대상 | 청년 정책, 창업지원 공고, 교육·훈련 과정을 찾는 청년 사용자 |
| 핵심 문제 | 기관별로 흩어진 지원 정보를 사용자가 직접 비교해야 하는 탐색 비용 |
| 핵심 기능 | 자연어 조건 추출, 맞춤형 추천, 신청 가능성 판단, 출처 기반 답변, 마감 공고 필터링 |
| 데이터 규모 | 통합 데이터 26,803건, RAG 청크 33,950개 |
| 주요 기술 | Streamlit, FastAPI, LangGraph, ChromaDB, Neo4j, OpenAI, Tavily, LoRA/QLoRA |
| 평가 방식 | Rule-based 평가, BLEU/ROUGE 보조 지표, LLM-as-a-Judge 평가 |

---

## 2. 팀원 소개 및 역할 분담

<table>
  <tr align="center">
    <th width="10%">구분</th>
    <th width="18%">송민지</th>
    <th width="18%">윤승혁</th>
    <th width="18%">정승</th>
    <th width="18%">한경찬</th>
    <th width="18%">한예나</th>
  </tr>
  
  <tr align="center">
    <td><strong>사진</strong></td>
    <td><img src="docs/images/minji.png" width="110" height="110" alt="송민지"></td>
    <td><img src="docs/images/seunghyuk.png" width="110" height="110" alt="윤승혁"></td>
    <td><img src="docs/images/seung.png" width="110" height="110" alt="정승"></td>
    <td><img src="docs/images/kyungchan.png" width="110" height="110" alt="한경찬"></td>
    <td><img src="docs/images/yena.png" width="110" height="110" alt="한예나"></td>
  </tr>
  
  <tr align="center">
    <td><strong>역할</strong></td>
    <td><strong>프론트엔드</strong></td>
    <td><strong>RAG/LangGraph</strong></td>
    <td><strong>데이터 엔지니어링</strong></td>
    <td><strong>백엔드</strong></td>
    <td><strong>PM/기획, 평가</strong></td>
  </tr>
  
  <tr valign="top">
    <td align="center"><strong>한 일</strong></td>
    <td>Streamlit UI/UX 설계</td>
    <td>LangGraph 기반 에이전트 워크플로우 설계</td>
    <td>Open API 데이터 수집 및 정제</td>
    <td>FastAPI 기반 RESTful API 설계</td>
    <td>프로젝트 리딩 및 기획 총괄</td>
  </tr>
</table>

---

## 3. 핵심 기능 (Key Features)

1. **자연어 기반 유저 프로필 추출 (NLP)**
   - "서울 사는 27살 취준생이고 주거에 관심 있어"와 같은 사용자 질의에서 연령, 지역, 소득, 고용 상태, 관심사를 파싱하여 유저 프로필 세션에 자동 매칭한다.

2. **실시간 대용량 통합 데이터 필터링**
   - 2.6만 건 이상의 이종 데이터(정책, 창업, 교육)를 단일 스키마로 통합하여 자연어 추출 조건, 추가 입력 필터, 마감 여부를 실시간으로 다중 필터링한다. 브라우저 성능을 위해 추천 결과는 10개 단위 페이지네이션으로 표시한다.

3. **데이터 완성도 점수 (`info_score`) 도입**
   - 공공 데이터 특유의 정보 공백을 극복하기 위해 필드 완성도를 기반으로 스코어링 시스템을 구현하였다. 단, `info_score`는 데이터 완성도 점수이며 사용자 적합도 점수와는 구분한다.

4. **LangGraph 및 에이전트 기반 오케스트레이션**
   - 단순 검색 쿼리를 넘어 조건 추출, 라우팅, 검색, 검색 충분성 판단, 외부 검색 fallback, 자격 판단, 답변 생성을 상태 그래프 흐름으로 제어한다.

5. **Hybrid RAG 기반 정책 검색**
   - ChromaDB 기반 Vector 검색과 Neo4j 기반 Graph 보조 검색을 병합하여 의미 기반 검색과 관계 기반 검색을 함께 수행한다.

6. **공식 외부 검색 fallback**
   - 내부 Vector DB 검색 결과가 부족하거나 최신성이 필요한 경우 Tavily 기반 공식 도메인 제한 검색을 수행하여 온통청년, K-Startup, 고용24/HRD 등 공식 출처 확인 후보를 보강한다.

7. **멀티 소스 통합 인터페이스**
   - 청년정책(온통청년), 창업지원(K-Startup), 교육훈련(고용24/HRD) 3개 출처를 단일 화면에서 탐색할 수 있다.

8. **대화형 챗봇 UI**
   - 자연어로 조건을 입력하면 맞춤형 지원 항목을 추천받을 수 있는 챗봇 인터페이스를 제공한다.

9. **sLLM LoRA/QLoRA 실험**
   - 메인 서비스는 OpenAI 기반 RAG를 유지하되, 평가 기준 대응 및 향후 확장 가능성 검토를 위해 Qwen2.5-1.5B-Instruct 기반 LoRA/QLoRA 실험을 별도 수행하였다.

---

## 4. 기술 스택

| 분류 | 기술 |
|---|---|
| Frontend | ![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white) |
| Backend | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) |
| LLM/RAG | ![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat&logo=langchain&logoColor=white) ![LangGraph](https://img.shields.io/badge/LangGraph-000000?style=flat) ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white) ![Tavily](https://img.shields.io/badge/Tavily-0066FF?style=flat) |
| Vector DB | ![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=flat) |
| Graph DB | ![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=flat&logo=neo4j&logoColor=white) |
| Fine-tuning | ![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black) ![QLoRA](https://img.shields.io/badge/QLoRA/PEFT-FF6F00?style=flat) |
| Diagram | ![Eraser](https://img.shields.io/badge/Eraser-000000?style=flat) ![Mermaid](https://img.shields.io/badge/Mermaid-FF3670?style=flat&logo=mermaid&logoColor=white) |
| 협업 | ![Notion](https://img.shields.io/badge/Notion-000000?style=flat&logo=notion&logoColor=white) ![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white) |
| Language | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) |

---

## 5. 시스템 아키텍처

## 5.1 전체 디렉터리 구조

```text
📂 SKN29-3rd-5TEAM
├── 📂 app_streamlit               # Streamlit 프론트엔드 애플리케이션
│   ├── 📄 app.py                  # 프론트엔드 메인 진입점
│   ├── 📂 styles/                 # UI 커스텀 스타일링 (style.css)
│   ├── 📂 utils/                  # 데이터 로더, HTML 렌더러, 조건 파서 모듈
│   └── 📂 views/                  # 화면 단위 렌더링 (홈, 추천결과, 상세, 가이드, 챗봇)
├── 📂 backend                     # FastAPI 백엔드 애플리케이션
│   ├── 📄 main.py                 # 백엔드 API 서버 진입점
│   ├── 📂 api/                    # API 라우터 및 엔드포인트 제어 레이어
│   ├── 📂 db/                     # 데이터베이스 및 Vector DB 연결 설정
│   ├── 📂 graph/                  # LangGraph 기반 에이전트 워크플로우 및 노드 정의
│   ├── 📂 schemas/                # Pydantic 기반 데이터 검증 및 DTO 스키마
│   └── 📂 services/               # 핵심 추천 비즈니스 로직 레이어
├── 📂 data                        # 데이터 저장 및 분석 관리
│   ├── 📂 raw/                    # 공공데이터 수집 원본 (Open API Raw Data)
│   ├── 📂 processed/              # 전처리 완료 및 정규화 데이터 (opportunities.json 등)
│   ├── 📂 vector_db/              # Chroma Vector DB 저장 경로
│   └── 📂 reports/                # 중복/결측치/형태소 분석 품질 리포트
├── 📂 docs                        # 데이터 사전, 청킹 전략 등 개발 명세 및 문서
├── 📂 scripts                     # 데이터 전처리, 텍스트 분석 및 자동화 스크립트
├── 📂 sllm                        # sLLM 파인튜닝, LoRA/QLoRA 실험
├── 📂 evaluation                  # RAG, LLM 평가
├── 📂 tests                       # 단위 및 통합 테스트 코드
├── 📄 .env.example                # API 키 및 DB 접속 정보 환경변수 예시 파일
├── 📄 requirements.txt            # 의존성 패키지 목록
├── 📄 run_konlpy_setup.bat        # Java 환경 검증 및 KoNLPy 패키지 자동 설치 스크립트
└── 📄 update_readme_eval.py       # 데이터 전처리 평가 리포트 README 반영 스크립트
```

<img src="docs/images/architecture.png" width="1000" alt="Architecture">

## 5.2 Framework

전체 시스템은 **Frontend → FastAPI Backend → LangGraph Workflow → Data/ML Layer** 4개 레이어로 구성된다.

### Frontend (Streamlit)
사용자는 Streamlit UI를 통해 챗봇, 정책 검색, 상세 조회 화면에 접근한다. 챗봇(`chatbot_page.py`)은 `POST /api/chat`으로 FastAPI와 통신하며, 정책 목록·상세 화면은 `data_loader.py`가 `opportunities.json`을 직접 읽어 렌더링한다.

### FastAPI Backend
`main.py`가 미들웨어·예외 핸들러·lifespan을 관리하고, `chat.py`가 요청을 받아 LangGraph 워크플로우(`run_rag_chat()`)를 호출한다. `policy_repository.py`는 `item_id` 기준 O(1) 상세 조회를 담당한다.

### LangGraph 노드 흐름

사용자 입력부터 최종 답변 생성까지 각 노드의 역할과 상태 전달 흐름을 나타낸다.

<img src="docs/images/langgraph_node_flow.png" width="1000" alt="LangGraph node flow">

```text
Input Validator → Condition Extractor → Router
  → Retriever (Chroma Vector Search)
  → graph_retrieve_node (Neo4j Cypher)
  → hybrid_merge_node (Vector + Graph 결과 병합, 중복 제거)
  → Result Sufficiency Checker
  → Official External Search Fallback (필요 시)
  → Eligibility Checker
  → Answer Generator
```

### Data / ML Layer

| 구성 요소 | 내용 |
|---|---|
| ChromaDB | `youth_opportunity_chunks` 컬렉션, 33,950 chunks |
| Neo4j AuraDB | Item + Domain 노드, 500건 샘플 적재 완료 |
| opportunities.json | 통합 데이터 26,803건 |
| opportunity_chunks.jsonl | RAG 임베딩용 33,950 chunks |
| OpenAI API | Embedding + Chat, 지수백오프 재시도 (max=2) |
| Tavily | 공식 도메인 제한 외부 검색 fallback |
| LoRA/QLoRA | Qwen2.5-1.5B-Instruct 기반 sLLM 파인튜닝 실험 |
| LLM-as-a-Judge | Context Relevance 4.6 / Groundedness 4.2 / Answer Relevance 4.1 |

---

## 6. Neo4j Graph DB

정책 간 관계 기반 검색을 위해 Neo4j AuraDB(클라우드)를 도입했다.

### 노드 및 관계 구조

| 구성 요소 | 내용 |
|---|---|
| 노드 | `Item` (item_id, title, source_category, domain, info_score) |
| 노드 | `Domain` (name) |
| 관계 | `Item -[:BELONGS_TO]-> Domain` |

### 데이터 적재 현황

- `opportunity_chunks.jsonl` 기준 500건 샘플 적재 완료
- 적재 스크립트: `scripts/build_graph_db.py`

### Hybrid RAG 파이프라인

Vector 검색 결과와 Graph 검색 결과를 병합하여 최종 후보를 구성한다.

```text
Retriever (Chroma) → graph_retrieve_node (Neo4j Cypher)
  → hybrid_merge_node (vector=5, graph_new=2, total=7, 중복 제거)
```

Neo4j 연결 실패 시 기존 Vector 파이프라인으로 자동 전환(graceful degradation)된다.

<img src="docs/images/graph_DB.png" width="1000" alt="graph_DB">
<img src="docs/images/hybrid_rag.png" width="1000" alt="hybrid_rag">

---

## 7. 데이터 출처

| source_category | 데이터 | 출처 | 통합 기준 | 건수 |
|---|---|---|---|---:|
| `policy` | 청년정책 | 온통청년 Open API | 전체 정책 데이터 | 2,611 |
| `startup_notice` | 창업지원 공고 | K-Startup / 창업진흥원 Open API | `youth_relevance = high` | 3,789 |
| `training` | 교육·취업 훈련 과정 | 고용24/HRD 국민내일배움카드 훈련과정 API | `youth_relevance = high` | 20,403 |

### 출처 URL

1. 온통청년 Open API
   - https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiGuide
   - https://www.data.go.kr/data/15143273/openapi.do

2. K-Startup / 창업진흥원 Open API
   - https://www.data.go.kr/data/15125364/openapi.do
   - https://nidview.k-startup.go.kr/view/public/kisedKstartupService/announcementInformation

3. 고용24/HRD Open API
   - https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do

---

## 8. 최종 데이터 수량

| 항목 | 수량 |
|---|---:|
| 최종 통합 데이터 `opportunities.json` | 26,803건 |
| 최종 RAG 청크 `opportunity_chunks.jsonl` | 33,950개 |
| 온통청년 정책 | 2,611건 |
| K-Startup 청년 HIGH 창업공고 | 3,789건 |
| HRD 청년 HIGH 교육훈련 | 20,403건 |
| 신청 URL 보유 데이터 | 2,538건 |
| 출처 URL 보유 데이터 | 25,851건 |
| Ground Truth 평가 질문 | 50개 |

---

## 9. 최종 산출물

| 파일 | 용도 |
|---|---|
| `data/processed/opportunities.json` | 백엔드 검색 결과 및 상세 페이지용 통합 데이터 |
| `data/processed/opportunity_chunks.jsonl` | Chroma 등 Vector DB 임베딩용 JSONL |
| `data/processed/opportunities_with_keywords.json` | KoNLPy Okt 형태소/키워드 분석 결과가 추가된 평가용 데이터 |
| `data/reports/konlpy_keyword_report.csv` | KoNLPy Okt 기반 키워드 빈도 리포트 |
| `data/reports/bow_keyword_report.csv` | BoW 키워드 빈도 리포트 |
| `data/reports/tfidf_keyword_report.csv` | TF-IDF 기반 주요 키워드 리포트 |
| `data/reports/word2vec_fasttext_status_report.csv` | Word2Vec/FastText 샘플 학습 상태 및 유사어 결과 |
| `data/reports/missing_value_report.csv` | 필드별 결측 리포트 |
| `data/reports/duplicate_check_report.csv` | `item_id` 중복 확인 리포트 |
| `data/reports/chunk_length_report.csv` | 청크 길이 통계 |
| `tests/evaluation_dataset.jsonl` | RAG 검색 품질 평가용 Ground Truth 데이터셋 |
| `scripts/validate_evaluation_dataset.py` | Ground Truth 정답 `item_id` 검증 스크립트 |
| `docs/01-1. 데이터_출처.md` | 온통청년, K-Startup, 고용24/HRD 데이터 출처 정리 |
| `docs/01-2. 데이터 스키마 설계서.md` | 통합 데이터 스키마와 `item_id` 연결 기준 |
| `docs/01-3. 데이터 전처리 가이드.md` | 출처별 전처리 기준과 청년 관련성 분류 기준 |
| `docs/01-4. 데이터 파이프라인 가이드.md` | 데이터 수집→정제→통합→청크→평가 데이터셋 흐름 |
| `docs/02-1. RAG_LLM_보고서_통합.md` | RAG/LLM 파이프라인 통합 보고서 |
| `docs/02-4. RAG_평가_보고서.md` | Rule-based RAG 평가 결과 보고서 |
| `docs/02-5. LLM_Judge_평가_보고서.md` | LLM-as-a-Judge 평가 결과 보고서 |
| `docs/03-1. 백엔드_API_명세.md` | FastAPI 응답 계약 및 엔드포인트 명세 |
| `docs/03-2. 백엔드-RAG_연결.md` | 백엔드-RAG 연결 기준 문서 |
| `docs/04. sLLM_LoRA_실험_보고서.md` | LoRA/QLoRA 실험 코드, 설정, 샘플 결과 |

---

## 10. 데이터 수집 및 전처리 흐름

```text
1. 온통청년 / K-Startup / HRD 데이터 수집
2. 원본 raw 데이터 보존
3. 출처별 전처리
4. 컬럼 표준화
5. 결측치 및 중복 확인
6. 청년 관련성 high/medium/low 분류
7. high 데이터 중심으로 서비스 통합
8. 공통 스키마 opportunities.json 생성
9. RAG용 opportunity_chunks.jsonl 생성
10. KoNLPy Okt 형태소 분석 및 불용어 처리
11. BoW / TF-IDF 키워드 리포트 생성
12. Gensim Word2Vec / FastText 샘플 학습 리포트 생성
13. Ground Truth 평가 데이터셋 추가
14. Ground Truth answer_item_ids와 opportunities.json item_id 연결 검증
15. 평가용 문서 및 리포트 정리
```

<img src="docs/images/pipeline_flow.png" width="1000" alt="Pipeline_flow">

---

## 11. 텍스트 분석 및 전처리

`scripts/analyze_korean_text.py`와 `scripts/build_text_features.py`로 전체 26,803건에 대해 아래 분석을 수행했다.

| 분석 항목 | 도구 | 산출물 |
|---|---|---|
| 형태소 분석 / 불용어 처리 | KoNLPy Okt | `konlpy_keyword_report.csv` |
| BoW / TF-IDF | CountVectorizer / TfidfVectorizer | `bow_keyword_report.csv`, `tfidf_keyword_report.csv` |
| Word2Vec / FastText | Gensim (샘플 학습) | `word2vec_fasttext_status_report.csv` |

Word2Vec/FastText는 평가용 샘플 학습이며 실제 서비스 검색에는 사용하지 않는다. 실제 RAG 검색은 OpenAI Embedding 기반 Vector DB(ChromaDB)로 수행한다.

---

## 12. 평가 지표 대응 현황

| 평가 항목 | 반영 내용 | 산출물 |
|---|---|---|
| 데이터셋 선정 타당성 | 청년정책, 창업지원, 교육훈련 3개 공식 출처 선정 | `docs/01-1. 데이터_출처.md` |
| 편향성 처리 | 청년 관련성 high 기준으로 서비스 통합 범위 제한 | `docs/01-4. 데이터 파이프라인 가이드.md` |
| 중복 제거 | `item_id` 기준 중복 확인 | `data/reports/duplicate_check_report.csv` |
| 결측치 처리 | 필드별 결측률 산출, 임의 보완 금지 | `data/reports/missing_value_report.csv` |
| 정규표현식 텍스트 정규화 | HTML/URL/특수문자/공백 정리 | `scripts/analyze_korean_text.py` |
| KoNLPy 형태소 분석 | KoNLPy Okt 기반 명사 추출을 최종 통합 데이터 26,803건에 적용 | `data/reports/konlpy_keyword_report.csv`, `data/processed/opportunities_with_keywords.json` |
| 불용어 처리 | 행정/공통어 제거, 핵심 도메인어 보존 | `data/reports/stopword_report.csv` |
| BoW | CountVectorizer 기반 키워드 빈도 | `data/reports/bow_keyword_report.csv` |
| TF-IDF | 전체/source_category/domain별 주요 키워드 | `data/reports/tfidf_keyword_report.csv` |
| Word2Vec/FastText | Gensim 기반 샘플 학습 수행, 두 모델 모두 `trained_sample` 상태 확인 | `data/reports/word2vec_fasttext_status_report.csv` |
| Ground Truth | RAG 정답 데이터셋 50개 구축 및 `answer_item_ids` 연결 검증 | `tests/evaluation_dataset.jsonl`, `data/reports/evaluation_dataset_summary.csv` |
| 청킹 전략 | search_profile chunk 및 향후 Recursive/Semantic 전략 문서화 | `docs/01-4. 데이터 파이프라인 가이드.md` |
| 데이터 스키마 문서화 | 필드 설명 및 백엔드/RAG 연결 기준 작성 | `docs/01-2. 데이터 스키마 설계서.md`, `docs/03-2. 백엔드-RAG_연결.md` |
| 파이프라인 문서화 | 수집→전처리→통합→청크→텍스트 분석→Ground Truth 검증 흐름 작성 | `docs/01-4. 데이터 파이프라인 가이드.md` |
| 데이터 수량 문서화 | source_category별 건수 및 청크 수 기록 | `README.md`, `data/processed/preprocessing_summary.json` |
| RAG/LLM 평가 | Rule-based 평가, BLEU/ROUGE 보조 지표, LLM-as-a-Judge 평가 수행 | `docs/02-4. RAG_평가_보고서.md`, `docs/02-5. LLM_Judge_평가_보고서.md` |
| sLLM 파인튜닝 대응 | LoRA/QLoRA 학습 코드, 설정 파일, 샘플 프롬프트 결과 정리 | `sllm/`, `docs/04. sLLM_LoRA_실험_보고서.md` |

---

## 13. 평가 결과 요약

### 13.1 Rule-based RAG 평가

| 항목 | 결과 |
|---|---:|
| 총 테스트 케이스 수 | 10 |
| 통과 케이스 수 | 10 |
| 통과율 | 100.0% |
| 평균 규칙 기반 점수 | 1.000 |
| 평균 BLEU | 0.0212 |
| 평균 ROUGE-1 F1 | 0.1451 |
| 평균 ROUGE-2 F1 | 0.0581 |
| 평균 ROUGE-L F1 | 0.1242 |

규칙 기반 평가는 route, next_action, recommendations 개수, 마감 공고 제외, 입력 검증, tool_trace 존재 여부처럼 시스템 동작 조건을 확인한다. BLEU/ROUGE는 추천형 RAG 특성상 참고용 보조 지표로 해석한다.

### 13.2 LLM-as-a-Judge 평가

| 지표 | 평균 점수 |
|---|---:|
| Context Relevance | 4.6 / 5 |
| Groundedness | 4.2 / 5 |
| Answer Relevance | 4.1 / 5 |
| 전체 평균 | 약 4.3 / 5 |

검색된 컨텍스트가 질문과 대체로 관련 있고, 답변이 검색 결과에 근거하여 생성되었음을 확인했다. 다만 신청 가능 여부, 제출 서류, 지역 제한 등 세부 신청 정보는 원천 데이터 구조화 수준에 따라 추가 확인이 필요한 경우가 남아 있다.

---

## 14. RAG 청킹 전략

현재 청킹은 `item_id` 기준 search_profile chunk를 생성한다.

- 임베딩 대상: `content`
- metadata: `item_id`, `source_category`, `domain`, `title`, `source_url`, `application_url`, `info_score`, `needs_detail_check`

자세한 내용은 `docs/01-4. 데이터 파이프라인 가이드.md`와 `docs/02-1. RAG_LLM_보고서_통합.md`에 작성했다.

<img src="docs/images/chunk_diagram.png" width="1000" alt="chunk_diagram">

---

## 15. 제외한 데이터와 이유

공모전·경진대회·모집공고 데이터는 이번 최종 범위에서 제외했다.

제외 이유:

- 공식 OpenAPI 기반의 안정적인 다건 수집원이 명확하지 않음
- 현재 통합 데이터만으로 정책/창업/교육훈련 영역을 충분히 구성함
- 평가 대응을 위해 추가 수집보다 전처리 품질과 문서화를 우선함

---

## 16. 설치 및 실행

### 요구 환경

- Python 3.10 이상
- Java JDK 11 이상 (KoNLPy 사용 시 필요)
- OpenAI API Key
- Neo4j AuraDB 접속 정보 (Graph DB 사용 시)
- Tavily API Key (외부 공식 검색 fallback 사용 시)

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 아래 항목을 입력한다.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini

NEO4J_URI=your_neo4j_uri
NEO4J_USER=your_neo4j_user
NEO4J_PASSWORD=your_neo4j_password

TAVILY_API_KEY=your_tavily_api_key
EXTERNAL_WEB_SEARCH_ENABLED=true
ENABLE_DDG_HTML_SEARCH=false
TAVILY_SEARCH_DEPTH=basic
TAVILY_INCLUDE_RAW_CONTENT=false
CURRENT_POLICY_YEAR=2026
```

### 3. 데이터 초기화

```bash
python scripts/build_opportunities.py
python scripts/validate_final_dataset.py
```

### 4. Vector DB 구축

통합 RAG 검색용 Chroma Vector DB를 구축한다.

```bash
python scripts/build_opportunity_vector_db.py \
  --input data/processed/opportunity_chunks.jsonl \
  --persist-dir data/vector_db \
  --collection-name youth_opportunity_chunks \
  --reset
```

OpenAI Embedding API RateLimit이 발생하면 batch size를 낮춰 재실행한다.

```bash
python scripts/build_opportunity_vector_db.py \
  --input data/processed/opportunity_chunks.jsonl \
  --persist-dir data/vector_db \
  --collection-name youth_opportunity_chunks \
  --batch-size 30
```

### 5. Graph DB 적재

Neo4j 보조 검색을 사용할 경우 다음 스크립트를 실행한다.

```bash
python scripts/build_graph_db.py
```

Neo4j 연결 정보가 없거나 연결에 실패해도 기본 Vector RAG 파이프라인은 동작하도록 설계되어 있다.

### 6. 서버 실행

백엔드:

```bash
uvicorn backend.main:app --reload
```

프론트엔드:

```bash
cd app_streamlit
streamlit run app.py
```

### 7. API 동작 확인

헬스체크:

```bash
curl http://127.0.0.1:8000/health
```

RAG 챗봇 API 테스트:

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"서울에 사는 25세 청년이 받을 수 있는 월세 지원 정책 알려줘.","top_k":5}'
```

### 8. 데이터 전처리 및 평가용 스크립트

데이터 검증:

```bash
python scripts/validate_final_dataset.py
```

KoNLPy Okt 형태소 분석 및 키워드 리포트 생성:

```bash
python scripts/analyze_korean_text.py
```

BoW / TF-IDF / Word2Vec / FastText 분석:

```bash
python scripts/build_text_features.py
```

Ground Truth 평가 데이터셋 검증:

```bash
python scripts/validate_evaluation_dataset.py
```

전체 평가 대응 실행 순서:

```bash
python scripts/build_opportunities.py
python scripts/validate_final_dataset.py
python scripts/analyze_korean_text.py
python scripts/build_text_features.py
python scripts/validate_evaluation_dataset.py
```

---

## 17. 데모 시나리오

발표 또는 시연 시 다음 질의를 사용할 수 있다.

| 시나리오 | 예시 질문 | 확인 포인트 |
|---|---|---|
| 주거 정책 추천 | 서울에 사는 25세 청년이 받을 수 있는 월세 지원 정책 알려줘 | 조건 추출, 주거 route, 정책 추천, 출처 URL |
| 교육훈련 추천 | 국민내일배움카드로 들을 수 있는 AI 데이터 분석 훈련 과정 추천해줘 | training source_category, 교육훈련 카드 표시 |
| 창업공고 최신성 | 2026년에 신청 가능한 청년 창업지원 공고 추천해줘 | startup_notice 검색, 마감 공고 제외 |
| 롱테일 fallback | 중소기업 다니는 청년 교통비 지원해주는 사업 있어? | 내부 검색 보강, 공식 외부 검색 fallback |
| 입력 검증 | 월세 | 짧은 질문 경고, 추가 조건 안내 또는 외부 검색 보강 |

---

## 18. 백엔드 사용 방법

백엔드는 다음 파일을 사용한다.

```text
data/processed/opportunities.json
```

상세 페이지 연결 key는 `item_id`이다.

`application_url`이 없으면 신청 버튼을 숨기고, `source_url`이 있으면 출처 링크로 표시한다.

---

## 19. RAG 사용 방법

RAG 담당자는 다음 파일을 사용한다.

```text
data/processed/opportunity_chunks.jsonl
```

`content`를 임베딩하고 `metadata`를 Chroma metadata로 저장한다. 검색 결과의 `item_id`를 `opportunities.json`의 상세 데이터와 연결한다.

---

## 20. Ground Truth 평가 데이터셋

RAG 검색 결과를 평가하기 위해 `tests/evaluation_dataset.jsonl` 파일을 추가했다.

실제 사용자가 입력할 만한 자연어 질문과, 정답으로 기대되는 `item_id`를 JSONL 형식으로 정리한 Ground Truth 데이터셋이다. 자세한 내용은 `docs/02-4. RAG_평가_보고서.md`와 `docs/02-5. LLM_Judge_평가_보고서.md` 참고.

---

## 21. 주의사항

- 원본 raw 데이터는 절대 덮어쓰지 않는다.
- 원본에 없는 신청방법, 제출서류, 조건은 임의 생성하지 않는다.
- 모든 연결 기준은 `item_id`이다.
- `info_score`는 데이터 완성도 점수이며 추천 적합도 점수가 아니다.
- KoNLPy는 Java 환경이 필요할 수 있다.
- 최종 제출 산출물은 KoNLPy Okt 기반 분석 결과로 재생성했다.
- Java/KoNLPy가 없는 환경에서는 스크립트가 중단되지 않도록 정규표현식 기반 예외 처리 경로를 포함한다.
- Word2Vec/FastText는 평가/분석용 샘플 학습이며 실제 서비스 검색에는 사용하지 않는다.
- 외부 검색 fallback 결과는 공식 출처 확인 후보이며, 신청 가능 여부와 세부 조건은 원문 확인이 필요하다.

---

## 22. 버전 히스토리 (Version History)

### 📌 v1.5 — 페이지 전환 최적화 및 리소스 캐시 개선

* **앱 버전 표시 갱신**: Streamlit 상단 버전을 `v1.5`로 변경
* **챗봇 화면 명칭 갱신**: 챗봇 화면 제목을 `정책 챗봇`에서 `안쉼 챗봇`으로 변경
* **첫 진입 로딩 화면**: 앱을 처음 열어 정책 데이터를 불러오는 동안 `policy_loading.png` 기반 로딩 화면만 표시하고, 로드 완료 후 페이지가 보이도록 렌더링 순서 최적화
* **페이지 전환 최적화**: 챗봇, 검색 전 추천 결과, 검색 전 신청 가이드처럼 정책 목록이 필요 없는 화면에서는 대용량 정책 JSON 로드를 건너뛰도록 개선
* **검색 결과 재사용**: 조건, 키워드, 마감 정책 제외 설정이 그대로인 경우 추천 결과 필터링/정렬 결과를 세션에서 재사용해 페이지 복귀와 탭 전환 반응 속도 개선
* **정적 리소스 캐시**: 로고 base64 변환, 페이지 아이콘 로드, CSS 파일 읽기를 캐시해 Streamlit rerun 시 반복 파일 I/O를 줄임

### 📌 v1.4 — 조건 검색/필터 UX 정리 및 반응 속도 개선
* **조건 추출과 필터 분리**: 자연어 조건 추출 결과를 기본 검색 조건으로 저장하고, 조건 입력 필터는 그 결과를 더 좁히는 추가 필터로 동작하도록 개선
* **필터 초기화 흐름 정리**: 홈 검색 또는 추천 결과 재검색 후 나이·지역·관심 분야 필터는 빈 상태로 표시하여 사용자가 추가 조건만 직접 선택할 수 있도록 변경
* **검색 전 상태 개선**: 아직 검색하지 않은 상태에서는 전체 정책 건수 요약을 표시하지 않고 빈 검색 안내를 표시
* **조건 추출 속도 개선**: 로컬 조건 파서를 우선 사용하고, 백엔드 조건 추출 API는 필요한 경우에만 짧게 보조 호출하도록 최적화. 동일 문장 조건 추출은 캐시하여 반복 호출을 줄임
* **로딩 오버레이 추가**: 홈 검색과 조건 추출 처리 중 백구 로딩 이미지를 표시하여 검색 진행 상태를 명확히 안내
* **로고 자산 경로 안정화**: 로고 파일 경로를 `docs/images/home_logo.png`로 통일해 다른 PC에서도 실행 시 파일 경로 오류가 나지 않도록 수정
* **사용자 안내 문구 정리**: 조건 입력 팁을 실제 흐름에 맞게 `먼저 검색 → 필요 시 필터 추가 적용` 기준으로 수정
* **상세 팝업 안정화**: Streamlit `st.link_button` 대신 HTML 링크 버튼을 사용해 신청/출처 링크 오류를 방지
* **챗봇 프로필 안정화**: 비어 있는 프로필 값을 `int(None)`으로 변환하지 않도록 수정하고, 질문에서 추출한 조건을 우선 반영
* **데이터 표시 보정**: 연령 정보가 없거나 `0~0`으로 들어온 정책은 `연령 정보 없음`으로 표시
* **UI 정리**: 제목 옆 자동 앵커 링크 아이콘을 숨기고, 페이지 이동 후 스크롤을 결과 목록 상단으로 복원
* **캐시 갱신 처리**: 앱 버전 변경 시 데이터 로드 전에 Streamlit 데이터 캐시를 초기화해 정규화 변경사항이 즉시 반영되도록 개선
* **앱 버전 표시 갱신**: Streamlit 상단 버전을 `v1.4`로 변경

### 📌 v1.3 — 상세 팝업 통합 및 추천 결과 UX 개선
* **상세 팝업 통합**: 독립된 상세 분석 페이지를 삭제하고, 카드 클릭 시 그 자리에서 즉시 열리는 팝업창(`st.dialog`)으로 통합
* **로고 홈 버튼**: 상단 메뉴의 '홈' 탭을 없애고 로고+서비스명을 클릭하면 홈으로 이동하도록 UI 단순화
* **10개 단위 페이지네이션**: 대용량 결과를 10개씩 나누어 표시하고 페이지 이동 시 스크롤을 결과 목록 상단으로 복원
* **신청 가이드 연동**: 추천 결과에서 검색된 정책만 신청 가이드 선택 목록에 표시
* **링크 클릭 영역 분리**: 카드 전체 클릭(팝업 오픈)과 카드 내부의 외부 링크(`신청하기`, `출처 보기`) 작동 영역 분리

### 📌 v1.2 — AI API 연동 및 UX 고도화
* **상세 팝업 통합**: 독립된 상세 분석 페이지를 삭제하고, 카드 클릭 시 그 자리에서 즉시 열리는 팝업창(`st.dialog`)으로 통합
* **로고 홈 버튼**: 상단 메뉴의 '홈' 탭을 없애고 로고+서비스명을 클릭하면 홈으로 이동하도록 UI 단순화
* **클릭 영역 분리**: 카드 전체 클릭(팝업 오픈)과 카드 내부의 외부 링크(`신청하기`, `출처 보기`) 작동 영역 분리
* **사용자 흐름 연동**: 검색창 `Enter` 키 제출 지원, 상세 팝업에서 가이드 이동 시 해당 정책 자동 우선 선택
* **백엔드 AI 연결**: AI 조건 추출 API 및 실제 RAG 챗봇 API(`POST /api/chat`) 연동으로 정적 데모 탈피

### 📌 v1.1 — 목록 조회 최적화 및 UI 정밀 조정
* **10개 단위 페이지네이션**: 대용량 데이터 처리를 위해 결과를 10개씩 분할 노출하고 페이지 이동 시 상단 스크롤 적용
* **UI 줄맞춤 및 정렬**: 화면 전체 요소의 레이아웃 줄맞춤 작업을 대거 진행하여 시각적 안정감 확보
* **디자인 톤 다운**: 시각적으로 튀던 추천 결과창의 `조건 적용` 버튼 색상을 차분하게 변경
* **자연스러운 전환**: 화면 간 이동 및 기능 작동 시 부드럽고 자연스럽게 흐르도록 모션 보완
* **콘텐츠 재배치**: 정책 '간단 설명'을 '지원 내용' 섹션으로 통합하고, 목록 카드에서는 최대 두 줄로 말줄임 처리
