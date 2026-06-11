# Streamlit 프론트엔드 코드 문서

## 1. 문서 개요

이 문서는 청년 지원 정보 통합 탐색 서비스 **이젠, 안쉼**의 Streamlit
프론트엔드 구조와 실행 방법, 데이터 연결 방식, 주요 기능을 정리한 개발
문서이다.

현재 프론트엔드는 프로젝트 루트의 `app.py`를 기준으로 실행한다. 임시 CSV가
아닌 백엔드 전처리 결과 `data/processed/opportunities.json`을 읽어 청년
정책, 창업 공고, 교육·훈련 데이터를 화면에 표시한다.

현재 구현 범위는 다음과 같다.

1. 자연어 기반 사용자 조건 추출
2. 추출 조건을 반영한 추천 결과 화면 이동
3. 나이, 지역, 관심 분야, 마감 여부 기반 필터링
4. 실제 데이터 기반 정책 카드 출력
5. 정책 상세 분석 및 신청 가이드
6. 실제 신청 URL과 출처 URL 연결
7. 챗봇 데모 화면

---

## 2. 전체 디렉터리 구조

```text
4th_project/
├─ app.py
├─ README.md
├─ streamlit_frontend_guide.md
│
├─ data/
│  ├─ processed/
│  │  ├─ opportunities.json
│  │  ├─ opportunity_chunks.jsonl
│  │  └─ ...
│  ├─ raw/
│  └─ reports/
│
├─ styles/
│  └─ style.css
│
├─ utils/
│  ├─ data_loader.py
│  ├─ html_renderer.py
│  ├─ condition_parser.py
│  └─ recommender.py
│
└─ views/
   ├─ home_page.py
   ├─ search_page.py
   ├─ detail_page.py
   ├─ guide_page.py
   ├─ chatbot_page.py
   └─ profile_page.py
```

### 파일 배치 규칙

| 구분 | 경로 | 설명 |
|---|---|---|
| 메인 실행 파일 | `app.py` | Streamlit 앱 진입점 |
| 스타일 파일 | `styles/style.css` | 전체 UI 및 반응형 CSS |
| 페이지 파일 | `views/*_page.py` | 화면 단위 렌더링 함수 |
| 데이터 로더 | `utils/data_loader.py` | 실제 JSON 로딩 및 화면 모델 변환 |
| 조건 추출 | `utils/condition_parser.py` | 자연어 입력 조건 추출 |
| 실제 화면 데이터 | `data/processed/opportunities.json` | 정책·창업·교육 통합 데이터 |
| RAG 청크 데이터 | `data/processed/opportunity_chunks.jsonl` | 임베딩 및 벡터 검색용 |

---

## 3. 실행 방식

### 3.1 실행 환경

현재 확인된 환경은 다음과 같다.

- Windows PowerShell
- Python 3.13.12
- Streamlit 1.58.0
- pandas

필요한 패키지가 없다면 다음 명령어로 설치한다.

```powershell
python -m pip install streamlit pandas
```

### 3.2 실행 경로

PowerShell에서 다음 프로젝트 루트로 이동한다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
```

프로젝트 루트에서 다음 명령어를 실행한다.

```powershell
python -m streamlit run app.py
```

브라우저 접속 주소는 다음과 같다.

```text
http://localhost:8501
```

포트를 명시하려면 다음과 같이 실행한다.

```powershell
python -m streamlit run app.py --server.port 8501
```

실행 중인 앱은 PowerShell에서 `Ctrl+C`를 눌러 종료한다.

### 3.3 실행 위치 주의사항

`app.py`가 `styles/style.css`를 상대 경로로 읽으므로 반드시 다음 위치에서
실행하는 것을 권장한다.

```text
C:\Users\nowis\Desktop\SKN\4th_project
```

데이터 로더는 `pathlib.Path`를 사용해 실제 데이터 경로를 계산하므로 데이터
파일은 다음 위치에 있어야 한다.

```text
data/processed/opportunities.json
```

---

## 4. 메인 앱 구조: `app.py`

`app.py`는 전체 Streamlit 앱의 진입점이며 다음 작업을 담당한다.

1. Streamlit 페이지 설정
2. CSS 파일 로드
3. Streamlit 기본 메뉴와 헤더 숨김
4. 실제 정책 데이터 로드
5. 세션 상태 초기화
6. 브랜드 헤더와 탭 네비게이션 출력
7. 선택된 페이지 렌더링

### 주요 import 구조

```python
from utils.data_loader import load_policies
from utils.html_renderer import render_html
from views.home_page import render_home_page
from views.search_page import render_search_page
from views.detail_page import render_detail_page
from views.guide_page import render_guide_page
from views.chatbot_page import render_chatbot_page
```

### 기본 세션 값

```python
st.session_state.page = "홈"

st.session_state.profile = {
    "age": 27,
    "region": "서울",
    "income": 3000,
    "job_status": "중소기업 재직자",
    "housing_status": "월세",
    "interest": ["취업", "금융", "주거"]
}
```

### 페이지 라우팅

| 페이지 | 렌더링 함수 |
|---|---|
| 홈 | `render_home_page()` |
| 추천 결과 | `render_search_page(policies)` |
| 상세 분석 | `render_detail_page(policies)` |
| 신청 가이드 | `render_guide_page(policies)` |
| 챗봇 | `render_chatbot_page(policies)` |

기존의 독립적인 `조건 입력` 탭은 제거했다. 홈에서 조건을 추출하면 추천 결과
페이지로 바로 이동하고, 결과 화면 왼쪽에서 조건을 수정한다.

---

## 5. 실제 데이터 구조

### 5.1 화면 데이터

현재 화면에서 사용하는 데이터는 다음 파일이다.

```text
data/processed/opportunities.json
```

총 26,803건이며 다음 세 가지 데이터 유형으로 구성된다.

| `source_category` | 설명 | 확인 건수 |
|---|---|---:|
| `policy` | 청년 정책 | 2,611 |
| `startup_notice` | 창업 지원 공고 | 3,789 |
| `training` | 교육·직업훈련 | 20,403 |

데이터 연결 기준 키는 정책명이 아닌 `item_id`이다. 정책명은 중복될 수
있으므로 상세 분석과 신청 가이드에서도 `item_id`를 사용한다.

### 5.2 주요 원본 필드

| 원본 필드 | 설명 |
|---|---|
| `item_id` | 통합 데이터 고유 ID |
| `title` | 정책 또는 공고명 |
| `source_category` | 정책·창업·훈련 구분 |
| `domain` | 정책 분야 |
| `summary` | 요약 설명 |
| `application_start_date` | 신청 시작일 |
| `application_end_date` | 신청 종료일 |
| `program_start_date` | 교육·사업 시작일 |
| `program_end_date` | 교육·사업 종료일 |
| `age_min`, `age_max` | 대상 연령 |
| `benefit_text` | 지원 내용 |
| `application_method` | 신청 방법 |
| `target_text` | 대상 및 자격 조건 |
| `region`, `location` | 지역 |
| `application_url` | 신청 URL |
| `source_url` | 원문 출처 URL |
| `organization` | 운영 기관 |
| `is_open` | 접수 여부 |
| `needs_detail_check` | 상세 확인 필요 여부 |
| `info_score` | 데이터 완성도 점수 |

### 5.3 RAG 데이터

다음 파일은 RAG 임베딩 및 벡터 DB 구축용이다.

```text
data/processed/opportunity_chunks.jsonl
```

현재 Streamlit 목록 화면은 이 파일을 직접 읽지 않는다. 추후 챗봇 또는 벡터
검색 백엔드에서 사용한다.

---

## 6. 유틸 모듈

### 6.1 `data_loader.py`

`opportunities.json`을 읽고 기존 UI가 사용할 수 있는 공통 화면 모델로
변환한다.

```python
DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "opportunities.json"
)
```

`load_policies()`는 JSON을 로드하고 각 데이터를 `_normalize()`로 변환한 뒤
`info_score` 기준으로 정렬한다. 결과는 `st.cache_data`로 캐시한다.

#### 화면 모델 변환 규칙

| 화면 필드 | 원본 데이터 |
|---|---|
| `id` | `item_id` |
| `title` | `title` |
| `description` | `summary` |
| `category` | `source_category`, `domain` 조합 |
| `period` | 신청 기간 또는 프로그램 기간 |
| `age` | `age_min`, `age_max` |
| `support` | `benefit_text` |
| `method` | `application_method` |
| `income` | `target_text` |
| `region` | `region` 또는 `location` |
| `application_url` | `application_url` |
| `source_url` | `source_url` |
| `organization` | `organization` |
| `score` | `info_score` |

원본에 없는 제출 서류나 세부 조건은 임의 생성하지 않고 `공식 공고 확인`으로
표시한다.

`info_score`는 사용자 적합도 점수가 아니라 데이터 완성도 점수다. 현재는
검색 결과의 기본 정렬 보조값으로만 사용한다.

### 6.2 `html_renderer.py`

여러 줄 HTML의 들여쓰기를 정리한 뒤 Streamlit에 렌더링한다.

```python
def render_html(markup):
    normalized = "\n".join(
        line.strip()
        for line in textwrap.dedent(markup).splitlines()
        if line.strip()
    )
    st.markdown(normalized, unsafe_allow_html=True)
```

Markdown이 들여쓰기된 HTML을 코드 블록으로 처리하는 문제를 줄이는 역할을
한다.

### 6.3 `condition_parser.py`

사용자의 자연어 입력에서 다음 조건을 추출한다.

```python
{
    "age": None,
    "region": None,
    "income": None,
    "job_status": None,
    "interest": []
}
```

| 항목 | 인식 예시 |
|---|---|
| 나이 | `27살` |
| 소득 | `연소득 3000` |
| 지역 | `서울`, `부산`, `경기` |
| 현재 상태 | `중소기업`, `취준`, `취업준비`, `창업` |
| 관심 분야 | `취업`, `금융`, `주거`, `교육`, `창업` |

현재는 정규식과 키워드 기반의 간단한 파서다.

### 6.4 `recommender.py`

정책 상태 배지, 추천 정렬, 조건 비교 함수가 들어 있다. 현재 추천 결과의
핵심 필터는 `search_page.py`에서 직접 처리하고 있어 이 모듈은 향후 추천
엔진 확장용 보조 모듈에 가깝다.

---

## 7. 페이지별 기능 정리

### 7.1 홈 화면: `home_page.py`

홈 화면은 서비스 소개, 자연어 입력, 예시 질문, 서비스 흐름을 제공한다.

#### 동작 흐름

```text
사용자 자연어 입력
→ parse_user_query()
→ 기존 profile과 추출 결과 병합
→ st.session_state.profile 저장
→ 추천 결과 필터 기본값 설정
→ st.session_state.page = "추천 결과"
→ st.rerun()
```

`조건 추출하기`를 누르면 별도의 조건 입력 페이지를 거치지 않고 추천 결과로
바로 이동한다.

### 7.2 추천 결과 화면: `search_page.py`

추천 결과 화면은 현재 프론트엔드의 핵심 페이지다.

#### 왼쪽 패널

1. 자연어 재검색
2. 조건 다시 추출
3. 나이 입력
4. 지역 선택
5. 연소득 입력
6. 현재 상태 선택
7. 주거 상태 선택
8. 관심 분야 선택
9. 조건 적용

#### 오른쪽 결과 영역

1. 원본 자연어 질의 표시
2. 현재 적용 조건 요약
3. 공공데이터 안내
4. 전체 일치 건수 표시
5. 마감 정책 제외 토글
6. 관련도 상위 30건 카드 렌더링

#### 필터 기준

- 관심 분야와 정책 카테고리
- 사용자 나이와 정책 연령
- 사용자 지역과 정책 지역
- 마감 여부
- 자연어 검색어와 제목·요약·태그·대상 조건의 일치도
- `info_score`

전체 일치 건수는 표시하지만 브라우저 성능을 위해 카드 출력은 최대 30건으로
제한한다.

#### 마감 상태 처리

다음 조건에 따라 상태를 판단한다.

1. `is_open`이 `N` 또는 `False`이면 신청 마감
2. 종료일이 오늘보다 이전이면 신청 마감
3. 종료일까지 14일 이하면 마감 임박
4. 상세 확인이 필요하면 조건 확인 필요
5. 그 외는 신청 가능

`마감 정책 제외` 토글은 기본으로 활성화되어 있다. 토글을 끄면 마감 정책도
검색 결과에 포함된다.

#### 실제 링크 처리

- `application_url`이 있으면 `신청하기` 링크 표시
- `source_url`이 있으면 `출처 보기` 링크 표시
- URL이 없으면 비활성 상태 안내 표시
- 외부 링크는 새 탭에서 열린다

### 7.3 정책 상세 분석: `detail_page.py`

정책 선택 드롭다운은 `item_id`를 내부 값으로 사용하고 정책명을 화면에
표시한다.

선택한 정책과 `st.session_state.profile`의 사용자 조건을 비교해 다음 항목을
표로 출력한다.

- 나이
- 지역
- 소득
- 현재 상태
- 주거 상태

현재 실제 데이터에서 정밀 판정이 어려운 항목은 `공식 공고 확인`으로
표시한다.

### 7.4 신청 가이드: `guide_page.py`

선택한 정책의 신청 기간, 상태, 신청 절차를 단계별로 표시한다.

```text
1. 공식 사이트 접속
2. 회원가입 또는 본인 인증
3. 신청서 작성
4. 필요 서류 제출
5. 심사 결과 확인
```

1단계 오른쪽의 `공식 사이트 접속` 버튼은 다음 순서로 URL을 선택한다.

```python
policy["application_url"]
or policy["source_url"]
or OFFICIAL_SITES.get(policy["title"])
```

정책 선택 기준은 제목이 아니라 `item_id`다.

### 7.5 챗봇 화면: `chatbot_page.py`

현재 챗봇은 실제 LLM 또는 RAG 백엔드가 연결되지 않은 정적 데모 UI다.

질문 입력창과 버튼은 존재하지만 응답 생성 로직은 아직 없다. 향후
`opportunity_chunks.jsonl` 기반 벡터 검색 또는 FastAPI 챗봇 API와 연결해야
한다.

### 7.6 미사용 조건 입력 화면: `profile_page.py`

기존 독립 조건 입력 페이지 코드가 남아 있지만 현재 `app.py` 네비게이션에는
연결되어 있지 않다. 조건 입력 기능은 추천 결과 화면의 왼쪽 필터로
통합되었다.

---

## 8. CSS 구조: `style.css`

`style.css`는 Streamlit 기본 UI를 보완하고 서비스 전반의 카드형 디자인을
정의한다.

| 영역 | 주요 클래스 |
|---|---|
| 앱 배경 | `.stApp`, `.block-container` |
| 브랜드 헤더 | `.top-header`, `.brand`, `.brand-title` |
| 홈 Hero | `.hero-section`, `.hero-title`, `.hero-subtitle` |
| 서비스 흐름 | `.flow-section`, `.flow-grid`, `.flow-item` |
| 추천 결과 | `.search-result-box`, `.info-box`, `.result-filter-heading` |
| 정책 카드 | `.policy-card`, `.policy-layout`, `.policy-meta` |
| 링크 버튼 | `.action-btn`, `.sub-btn`, `.policy-link` |
| 상태 배지 | `.badge-green`, `.badge-orange`, `.badge-red` |
| 신청 가이드 | `.guide-step`, `.step-num`, `.guide-site-link` |
| 챗봇 | `.chat-layout`, `.chat-bubble-user`, `.chat-bubble-ai` |

`@media (max-width: 900px)` 구간에서는 정책 카드, 서비스 흐름, 채팅 화면을
단일 컬럼으로 변경한다.

---

## 9. 현재 구현된 사용자 흐름

```text
[홈]
자연어로 사용자 조건 입력

↓

[조건 추출]
나이, 지역, 소득, 현재 상태, 관심 분야 추출

↓

[세션 저장]
st.session_state.profile과 filter_* 값 갱신

↓

[추천 결과]
왼쪽에서 조건 확인 및 수정
나이, 지역, 관심 분야, 검색어, 마감 여부 필터 적용
상위 30건 카드 표시

↓

[상세 분석]
item_id 기준 정책 선택
사용자 조건과 실제 정책 정보 비교

↓

[신청 가이드]
신청 절차와 실제 공식 링크 확인

↓

[챗봇]
정책 질의응답 데모 UI 확인
```

---

## 10. 현재 코드의 장점

1. `app.py`, `views`, `utils`, `styles`가 역할별로 분리되어 있다.
2. `st.session_state`로 페이지 간 사용자 조건을 공유한다.
3. 실제 통합 데이터 26,803건을 프론트엔드 공통 모델로 변환한다.
4. `item_id`를 사용해 중복 정책명 문제를 방지한다.
5. 대량 데이터를 모두 렌더링하지 않고 상위 30건만 출력한다.
6. 실제 신청 URL과 출처 URL을 사용한다.
7. 원본에 없는 정보를 임의 생성하지 않고 공식 공고 확인을 유도한다.
8. Streamlit 캐시로 대용량 JSON 재로딩 비용을 줄인다.

---

## 11. 현재 한계 및 개선 필요 사항

### 11.1 추천 로직이 규칙 기반이다

현재 추천은 검색어 일치, 관심 분야, 나이, 지역, 마감 여부,
`info_score`를 조합한다. 아직 벡터 검색이나 개인별 적합도 모델은 아니다.

#### 개선 방향

- 백엔드 추천 API 연결
- 벡터 검색 점수 반영
- 정책별 조건 충족 판정
- 추천 근거와 경고 항목 구조화

### 11.2 소득·직업·주거 정밀 판정이 어렵다

실제 통합 데이터에 모든 조건이 구조화되어 있지 않아 현재 소득, 직업 상태,
주거 상태를 정밀 필터로 사용하지 않는다.

#### 개선 방향

- 구조화된 자격 조건 필드 추가
- `target_text`에서 조건 추출
- RAG 또는 LLM 기반 자격 조건 해석

### 11.3 상세 분석 판정이 안내 수준이다

현재 상세 분석은 사용자 정보와 정책 정보를 나란히 보여주지만 모든 항목의
충족 여부를 자동 판정하지 않는다.

#### 개선 방향

- 정책별 조건 비교 엔진 구현
- 충족, 불충족, 확인 필요 상태 구분
- 판정 근거와 원문 출처 표시

### 11.4 챗봇이 정적 데모다

챗봇 입력값을 처리하는 백엔드 연결이 없다.

#### 개선 방향

- FastAPI `/api/chat` 연결
- Vector DB 검색 결과와 출처 표시
- `st.session_state.messages` 기반 대화 이력 관리

### 11.5 자연어 조건 추출 범위가 좁다

현재 파서는 `27살`, `연소득 3000`, `서울`, `취준` 같은 제한된 표현을
인식한다.

#### 개선 방향

- `만 27세`, `연봉 3000`, `무직`, `대학생`, `프리랜서` 지원
- 전국 시·도 및 시·군·구 표현 확장
- LLM 구조화 출력 기반 추출 API 연결

---

## 12. FastAPI/RAG 연동 시 권장 구조

| 화면 | 권장 API | 용도 |
|---|---|---|
| 홈 | `POST /api/conditions/extract` | 자연어 조건 추출 |
| 추천 결과 | `POST /api/recommend` | 조건 기반 추천 |
| 상세 분석 | `GET /api/opportunities/{item_id}` | 상세 조회 |
| 신청 가이드 | `GET /api/opportunities/{item_id}` | 신청 정보 조회 |
| 챗봇 | `POST /api/chat` | RAG 기반 질의응답 |

### 추천 API 응답 예시

```json
{
  "user_conditions": {
    "age": 27,
    "region": "서울",
    "income": 3000,
    "job_status": "중소기업 재직자",
    "housing_status": "월세",
    "interest": ["취업", "금융", "주거"]
  },
  "recommendations": [
    {
      "item_id": "policy_001",
      "title": "정책명",
      "category": "취업",
      "eligibility": "확인 필요",
      "reason": "나이와 지역 조건이 일치합니다.",
      "application_url": "https://example.com/apply",
      "source_url": "https://example.com/source"
    }
  ],
  "warnings": [
    "최종 자격은 공식 공고에서 확인해야 합니다."
  ]
}
```

---

## 13. 데이터 갱신 및 운영 방법

백엔드 전처리를 다시 수행한 경우 다음 파일을 동일한 경로에 교체한다.

```text
data/processed/opportunities.json
data/processed/opportunity_chunks.jsonl
```

원본 필드명이 유지되면 프론트엔드 코드 변경 없이 다시 실행할 수 있다.
스키마가 변경되면 `utils/data_loader.py`의 `_normalize()`와 관련 변환 함수를
수정해야 한다.

데이터 교체 후 캐시된 값이 남아 있으면 앱을 종료하고 다시 실행한다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
python -m streamlit run app.py
```

### 데이터 파일 역할

| 파일 | 운영 용도 |
|---|---|
| `opportunities.json` | 화면 목록, 상세, 신청 가이드 |
| `opportunity_chunks.jsonl` | RAG 임베딩 및 검색 |
| `data/raw/*` | 원본 수집 데이터 |
| `data/reports/*` | 데이터 품질 및 분석 보고서 |

---

## 14. 검증 결과 및 시연 범위

현재 확인된 항목은 다음과 같다.

1. 실제 데이터 26,803건 로딩
2. 정책 2,611건, 창업 공고 3,789건, 교육·훈련 20,403건 통합
3. 추천 결과 최대 30건 렌더링
4. 마감 정책 제외 토글 동작
5. 상세 분석에서 전체 `item_id` 선택 가능
6. 신청 가이드 공식 링크 연결
7. 신청 URL과 출처 URL 카드 연결
8. 앱 코드의 임시 CSV 참조 제거
9. 홈 조건 추출 후 추천 결과 자동 이동
10. 추천 결과 왼쪽 필터 수정 및 적용

현재 발표 또는 시연에서는 자연어 조건 추출, 추천 결과 필터링, 실제 데이터
카드, 상세 분석, 신청 가이드와 공식 사이트 연결을 보여줄 수 있다.

---

## 15. 결론

현재 Streamlit 프론트엔드는 임시 CSV 목업 단계에서 실제 통합 데이터 기반
화면으로 전환되었다. 홈, 추천 결과, 상세 분석, 신청 가이드, 챗봇 화면이
분리되어 있고, 실제 데이터 26,803건을 공통 UI 모델로 변환해 사용할 수
있다.

다음 단계의 핵심은 화면을 새로 만드는 것이 아니라 현재 UI에 백엔드 추천
API와 RAG 챗봇을 연결하는 것이다.

우선순위는 다음과 같다.

1. FastAPI 추천 API 연결
2. 조건별 자격 판정 로직 구현
3. Vector DB 기반 검색 결과 반영
4. 챗봇 RAG 응답과 출처 표시
5. 자연어 조건 추출 범위 확장

이 작업이 완료되면 현재 프론트엔드는 실제 청년 지원 정보 탐색 서비스의
사용자 인터페이스로 운영할 수 있다.
