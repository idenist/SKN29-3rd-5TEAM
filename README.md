# 청년 지원 통합 탐색 에이전트 데이터 파이프라인

## 1. 프로젝트 개요

- **서비스 명**: 이젠, 안쉼 (청년들이 정보 탐색의 피로에서 벗어나 안심할 수 있는 서비스)
- **기획 배경**: 청년 정책(온통청년), 창업 지원(K-Startup), 교육·훈련(고용24) 정보가 여러 기관에 파편화되어 있어 발생하는 청년들의 높은 탐색 비용과 정보 비대칭 문제를 해결하고자 함
- **핵심 가치**: 규칙 기반의 하드코딩 필터링을 넘어, **자연어 기반 조건 추출(NLP)** 및 **멀티 에이전트 워크플로우(LangGraph)**를 결합하여 대용량 공공 데이터셋(2.6만 건) 안에서 유저 맞춤형 정책을 최적의 경로로 큐레이션합니다.

본 패키지는 청년 지원 정보를 RAG 기반으로 탐색하기 위한 최종 데이터 산출물이다.

기존 v2 통합 데이터에 평가계획서의 데이터 전처리 요구 항목을 반영하여 데이터 설명서, 전처리 파이프라인 문서, KoNLPy Okt 형태소 분석 스크립트, 불용어 처리 리포트, BoW/TF-IDF 리포트, Word2Vec/FastText 샘플 학습 리포트, Ground Truth 평가 데이터셋, 청킹 전략 문서를 추가했다.

최종 백엔드 데이터는 `data/processed/opportunities.json`이며, RAG 임베딩 데이터는 `data/processed/opportunity_chunks.jsonl`이다.

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
    <td><strong>PM/기획,평가</strong></td>
  </tr>
  
  <tr valign="top">
    <td align="center"><strong>한 일</strong></td>
    <td>
      Streamlit UI/UX 설계
    </td>
    <td>
      LangGraph 기반 에이전트 워크플로우 설계
    </td>
    <td>
      Open API 데이터 수집 및 정제
    </td>
    <td>
      FastAPI 기반 RESTful API 설계
    </td>
    <td>
      프로젝트 리딩 및 기획 총괄
    </td>
  </tr>
</table>

---
## 3. 버전별 패치노트 (Version History)

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

---

## 4. 현재 통합된 데이터 출처

| source_category | 데이터 | 출처 | 통합 기준 | 건수 |
|---|---|---|---|---:|
| `policy` | 청년정책 | 온통청년 Open API | 전체 정책 데이터 | 2,611 |
| `startup_notice` | 창업지원 공고 | K-Startup / 창업진흥원 Open API | `youth_relevance = high` | 3,789 |
| `training` | 교육·취업 훈련 과정 | 고용24/HRD 국민내일배움카드 훈련과정 API | `youth_relevance = high` | 20,403 |

## 5. 핵심 기능 (Key Features)
1. **자연어 기반 유저 프로필 추출 (NLP)**
   - "서울 사는 27살 취준생이고 주거에 관심 있어"와 같은 사용자 질의에서 연령, 지역, 소득, 상태, 관심사를 파싱하여 유저 프로필 세션에 자동 매칭합니다.
2. **실시간 대용량 통합 데이터 필터링**
   - 2.6만 건 이상의 이종 데이터(정책, 창업, 교육)를 단일 스키마로 통합하여 자연어 추출 조건, 추가 입력 필터, 마감 여부를 실시간으로 다중 필터링합니다. 브라우저 성능을 위해 추천 결과는 10개 단위 페이지네이션으로 표시합니다.
3. **데이터 완성도 점수 (`info_score`) 도입**
   - 공공 데이터 특유의 정보 공백을 극복하기 위해 필드 완성도를 기반으로 스코어링 시스템을 구현, 유저에게 정밀하고 신뢰도 높은 공고를 최우선으로 노출합니다.
4. **LangGraph 및 에이전트 기반 오케스트레이션 (Back-end 지향)**
   - 단순 검색 쿼리를 넘어 복잡한 추천 로직 및 예외 처리를 에이전트의 상태 그래프(`graph/`) 흐름으로 제어하여 향후 유연한 챗봇 서비스 확장이 가능합니다.

---

## 6. 데이터 출처 URL

1. 온통청년 Open API  
   - https://www.youthcenter.go.kr/cmnFooter/openapiIntro/oaiGuide
   - https://www.data.go.kr/data/15143273/openapi.do

2. K-Startup / 창업진흥원 Open API  
   - https://www.data.go.kr/data/15125364/openapi.do
   - https://nidview.k-startup.go.kr/view/public/kisedKstartupService/announcementInformation

3. 고용24/HRD Open API  
   - https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do

## 7. 최종 데이터 수량

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

## 8. 최종 산출물

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
| `docs/data_dictionary.md` | 데이터 설명서 |
| `docs/chunking_strategy.md` | RAG/Graph 입력용 청킹 전략 문서 |
| `docs/text_preprocessing.md` | 텍스트 전처리 및 형태소 분석 문서 |
| `docs/data_pipeline_summary.md` | 데이터 수집→정제→통합 파이프라인 문서 |
| `docs/evaluation_checklist.md` | 평가 지표 대응표 |

## 9. 전체 디렉터리 구조

```text
📂 3RDPRJ
├── 📂 app_streamlit               # Streamlit 프론트엔드 어플리케이션
│   ├── 📄 app.py                 # 프론트엔드 메인 진입점
│   ├── 📂 styles/                # UI 커스텀 스타일링 (style.css)
│   ├── 📂 utils/                 # 데이터 로더, HTML 렌더러, 조건 파서 모듈
│   └── 📂 views/                 # 화면 단위 렌더링 (홈, 추천결과, 신청 가이드, 챗봇)
├── 📂 backend                     # FastAPI 백엔드 어플리케이션
│   ├── 📄 main.py                # 백엔드 API 서버 진입점
│   ├── 📂 api/                   # API 라우터 및 엔드포인트 제어 레이어
│   ├── 📂 db/                    # 데이터베이스 및 Vector DB 연결 설정
│   ├── 📂 graph/                 # LangGraph 기반 에이전트 워크플로우 및 노드 정의
│   ├── 📂 schemas/               # Pydantic 기반 데이터 검증 및 DTO 스키마
│   └── 📂 services/              # 핵심 추천 비즈니스 로직 레이어
├── 📂 data                        # 데이터 저장 및 분석 관리
│   ├── 📂 raw/                   # 공공데이터 수집 원본 (Open API Raw Data)
│   ├── 📂 processed/             # 전처리 완료 및 정규화 데이터 (opportunities.json 등)
│   └── 📂 reports/               # 중복/결측치/형태소 분석 품질 리포트
├── 📂 docs                        # 데이터 사전, 청킹 전략 등 개발 명세 및 문서
├── 📂 scripts                     # 데이터 전처리, 텍스트 분석 및 자동화 스크립트
├── 📂 tests                       # 단위 및 통합 테스트 코드
├── 📄 .env                        # API 키 및 DB 접속 정보 환경변수 파일
├── 📄 requirements.txt            # 의존성 패키지 목록 (Streamlit, FastAPI, Pandas 등)
├── 📄 run_konlpy_setup.bat        # Java 환경 검증 및 KoNLPy 패키지 자동 설치 스크립트
└── 📄 update_readme_eval.py       # 데이터 전처리 평가 리포트 README 반영 스크립트

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

## 11. 평가 지표 대응 현황

| 평가 항목 | 반영 내용 | 산출물 |
|---|---|---|
| 데이터셋 선정 타당성 | 청년정책, 창업지원, 교육훈련 3개 공식 출처 선정 | `docs/source_notes.md` |
| 편향성 처리 | 청년 관련성 high 기준으로 서비스 통합 범위 제한 | `docs/data_pipeline_summary.md` |
| 중복 제거 | `item_id` 기준 중복 확인 | `data/reports/duplicate_check_report.csv` |
| 결측치 처리 | 필드별 결측률 산출, 임의 보완 금지 | `data/reports/missing_value_report.csv` |
| 정규표현식 텍스트 정규화 | HTML/URL/특수문자/공백 정리 | `scripts/analyze_korean_text.py` |
| KoNLPy 형태소 분석 | KoNLPy Okt 기반 명사 추출을 최종 통합 데이터 26,803건에 적용 | `data/reports/konlpy_keyword_report.csv`, `data/processed/opportunities_with_keywords.json` |
| 불용어 처리 | 행정/공통어 제거, 핵심 도메인어 보존 | `data/reports/stopword_report.csv` |
| BoW | CountVectorizer 기반 키워드 빈도 | `data/reports/bow_keyword_report.csv` |
| TF-IDF | 전체/source_category/domain별 주요 키워드 | `data/reports/tfidf_keyword_report.csv` |
| Word2Vec/FastText | Gensim 기반 샘플 학습 수행, 두 모델 모두 `trained_sample` 상태 확인 | `data/reports/word2vec_fasttext_status_report.csv` |
| Ground Truth | RAG 정답 데이터셋 50개 구축 및 `answer_item_ids` 연결 검증 | `tests/evaluation_dataset.jsonl`, `data/reports/evaluation_dataset_summary.csv` |
| 청킹 전략 | search_profile chunk 및 향후 Recursive/Semantic 전략 문서화 | `docs/chunking_strategy.md` |
| 데이터 스키마 문서화 | 필드 설명 및 백엔드/RAG 연결 기준 작성 | `docs/data_dictionary.md`, `docs/opportunity_schema.md` |
| 파이프라인 문서화 | 수집→전처리→통합→청크→텍스트 분석→Ground Truth 검증 흐름 작성 | `docs/data_pipeline_summary.md` |
| 데이터 수량 문서화 | source_category별 건수 및 청크 수 기록 | `README.md`, `data/processed/preprocessing_summary.json` |

## 12. KoNLPy 형태소 분석 및 불용어 처리

`scripts/analyze_korean_text.py`는 다음 필드를 결합하여 분석한다.

- `title`
- `summary`
- `target_text`
- `benefit_text`
- `raw_text`

최종 제출 산출물은 Java JDK와 KoNLPy 실행 환경을 설정한 뒤, KoNLPy `Okt` 기반 명사 추출 방식으로 재생성했다.

최종 실행 상태는 다음과 같다.

```text
analyzer: konlpy.Okt
rows: 26,803
output: data/processed/opportunities_with_keywords.json
```

`analyze_korean_text.py` 안에는 Java/KoNLPy가 없는 환경에서도 스크립트가 중단되지 않도록 정규표현식 기반 예외 처리 경로를 포함했다. 이 예외 처리는 환경 이식성을 위한 안전장치이며, 최종 제출 산출물은 KoNLPy Okt 실행 결과를 기준으로 한다.

## 13. BoW / TF-IDF / Word2Vec / FastText 대응

`scripts/build_text_features.py`는 다음 리포트를 생성한다.

- `bow_keyword_report.csv`
- `tfidf_keyword_report.csv`
- `word2vec_fasttext_status_report.csv`

Gensim 기반 Word2Vec/FastText 샘플 학습을 수행하고, 주요 seed 단어별 유사어 리포트를 생성했다.

최종 확인 상태는 다음과 같다.

```text
Word2Vec: trained_sample
FastText: trained_sample
```

해당 모델은 평가/분석용 샘플 학습이며, 실제 서비스 검색에는 사용하지 않는다. 실제 RAG 검색은 `opportunity_chunks.jsonl`의 `content`를 Chroma 등 Vector DB에 임베딩하여 수행한다.

## 14. RAG 청킹 전략

현재 청킹은 `item_id` 기준 search_profile chunk를 생성한다.

- 임베딩 대상: `content`
- metadata: `item_id`, `source_category`, `domain`, `title`, `source_url`, `application_url`, `info_score`, `needs_detail_check`

자세한 내용은 `docs/chunking_strategy.md`에 작성했다.

## 15. 백엔드 사용 방법

백엔드는 다음 파일을 사용한다.

```text
data/processed/opportunities.json
```

상세 페이지 연결 key는 `item_id`이다.

`application_url`이 없으면 신청 버튼을 숨기고, `source_url`이 있으면 출처 링크로 표시한다.

## 16. RAG 사용 방법

RAG 담당자는 다음 파일을 사용한다.

```text
data/processed/opportunity_chunks.jsonl
```

`content`를 임베딩하고 `metadata`를 Chroma metadata로 저장한다. 검색 결과의 `item_id`를 `opportunities.json`의 상세 데이터와 연결한다.

## 17. 제외한 데이터와 이유

공모전·경진대회·모집공고 데이터는 이번 최종 범위에서 제외했다.

제외 이유:

- 공식 OpenAPI 기반의 안정적인 다건 수집원이 명확하지 않음
- 현재 통합 데이터만으로 정책/창업/교육훈련 영역을 충분히 구성함
- 평가 대응을 위해 추가 수집보다 전처리 품질과 문서화를 우선함

## 18. 실행 방법

기본 통합 파일 재생성:

```bash
python scripts/build_opportunities.py
```

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

## 19. Ground Truth 평가 데이터셋 및 검증 스크립트

RAG 검색 결과를 평가하기 위해 `tests/evaluation_dataset.jsonl` 파일을 추가했다.

이 파일은 실제 사용자가 입력할 만한 자연어 질문과, 정답으로 기대되는 `item_id`를 JSONL 형식으로 정리한 Ground Truth 데이터셋이다.

각 row는 다음 정보를 포함한다.

| 필드 | 설명 |
|---|---|
| `question` | 사용자가 입력할 자연어 질문 |
| `answer_item_ids` | 정답으로 기대되는 `opportunities.json`의 `item_id` 목록 |

Ground Truth 데이터셋은 아래 경로에 위치한다.

```text
tests/evaluation_dataset.jsonl
```

검증 스크립트는 아래 경로에 위치한다.

```text
scripts/validate_evaluation_dataset.py
```

검증 명령어는 다음과 같다.

```bash
python scripts/validate_evaluation_dataset.py
```

검증 결과는 다음과 같다.

```text
검증 완료: rows=50
- missing_field_rows=0
- empty_answer_rows=0
- missing_item_ids=0
- duplicate_questions=0
```

검증 결과의 의미는 다음과 같다.

| 항목 | 결과 | 의미 |
|---|---:|---|
| `rows` | 50 | 평가 질문 50개 존재 |
| `missing_field_rows` | 0 | 필수 필드 누락 없음 |
| `empty_answer_rows` | 0 | 정답 item_id가 비어 있는 질문 없음 |
| `missing_item_ids` | 0 | 모든 정답 item_id가 `opportunities.json`에 실제 존재 |
| `duplicate_questions` | 0 | 중복 질문 없음 |

검증 리포트는 아래 파일로 저장된다.

```text
data/reports/evaluation_dataset_summary.csv
data/reports/evaluation_dataset_validation_errors.json
```

따라서 본 패키지는 RAG 검색 품질 평가를 위한 Ground Truth 데이터셋과, 해당 데이터셋이 최종 통합 데이터와 정상 연결되는지 확인하는 검증 스크립트를 함께 포함한다.

## 20. 주의사항

- 원본 raw 데이터는 절대 덮어쓰지 않는다.
- 원본에 없는 신청방법, 제출서류, 조건은 임의 생성하지 않는다.
- 모든 연결 기준은 `item_id`이다.
- KoNLPy는 Java 환경이 필요할 수 있다.
- 최종 제출 산출물은 KoNLPy Okt 기반 분석 결과로 재생성했다.
- Java/KoNLPy가 없는 환경에서는 스크립트가 중단되지 않도록 정규표현식 기반 예외 처리 경로를 포함한다.
- Word2Vec/FastText는 평가/분석용 샘플 학습이며 실제 서비스 검색에는 사용하지 않는다.
