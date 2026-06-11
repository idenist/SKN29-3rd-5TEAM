# Streamlit 프론트엔드 코드 문서

## 1. 문서 개요

이 문서는 청년 정책 추천 서비스의 Streamlit 프론트엔드 코드 구조와 주요 기능을 정리한 개발 문서이다. 현재 프론트엔드는 `app_streamlit` 디렉터리를 기준으로 동작하며, 정책 데이터는 `data/policies.csv`를 읽어 화면에 표시한다.

현재 구현은 CSV 기반 정책 조회, 자연어 조건 추출, 추천 결과 카드 표시, 정책 상세 분석, 신청 가이드, 챗봇 데모 화면으로 구성되어 있다. 향후 FastAPI 및 RAG 백엔드와 연동할 때는 현재의 화면 구조를 유지하면서 데이터 입력부만 API 호출 방식으로 교체할 수 있다.

---

## 2. 전체 디렉터리 구조

```text
project-root/
├─ app_streamlit/
│  ├─ app.py
│  ├─ styles/
│  │  └─ style.css
│  ├─ views/
│  │  ├─ home_page.py
│  │  ├─ profile_page.py
│  │  ├─ search_page.py
│  │  ├─ chatbot_page.py
│  │  ├─ detail_page.py
│  │  └─ guide_page.py
│  └─ utils/
│     ├─ data_loader.py
│     ├─ html_renderer.py
│     ├─ recommender.py
│     └─ condition_parser.py
│
└─ data/
   └─ policies.csv
```

### 파일 배치 규칙

| 구분 | 경로 | 설명 |
|---|---|---|
| 메인 실행 파일 | `app_streamlit/app.py` | Streamlit 앱의 진입점 |
| 스타일 파일 | `app_streamlit/styles/style.css` | 전체 UI CSS 정의 |
| 페이지 파일 | `app_streamlit/views/*_page.py` | 화면 단위 렌더링 함수 모음 |
| 유틸 파일 | `app_streamlit/utils/*.py` | 데이터 로딩, HTML 렌더링, 추천/조건 추출 로직 |
| 정책 데이터 | `data/policies.csv` | 프론트엔드에서 표시하는 정책 샘플 데이터 |

---

## 3. 실행 방식

현재 `data_loader.py`는 다음 상대 경로를 기준으로 CSV를 읽는다.

```python
pd.read_csv("../data/policies.csv", encoding="utf-8-sig")
```

따라서 Streamlit 앱은 `app_streamlit` 디렉터리 내부에서 실행하는 것을 기준으로 한다.

```bash
cd app_streamlit
streamlit run app.py
```

루트 디렉터리에서 실행할 경우 `../data/policies.csv` 경로가 맞지 않을 수 있으므로, 실행 위치를 맞추거나 `data_loader.py`에서 경로를 절대/동적 경로로 변경해야 한다.

---

## 4. 메인 앱 구조: `app.py`

`app.py`는 전체 Streamlit 앱의 진입점이다. 주요 역할은 다음과 같다.

1. Streamlit 페이지 기본 설정
2. CSS 파일 로드
3. Streamlit 기본 UI 숨김 처리
4. 정책 데이터 로드
5. 세션 상태 초기화
6. 상단 브랜드 헤더 출력
7. 페이지 탭 네비게이션 구성
8. 현재 선택된 페이지 렌더링

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

### 기본 페이지 설정

```python
st.set_page_config(
    page_title="이젠, 안쉼",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed"
)
```

### 세션 기본값

앱 최초 실행 시 다음 세션 값이 생성된다.

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

이 값은 홈 화면에서 자연어 조건을 추출하거나 추천 결과 화면에서 필터를 수정할 때 갱신된다.

### 페이지 라우팅

현재 페이지는 `st.session_state.page` 값에 따라 결정된다.

| 페이지명 | 렌더링 함수 |
|---|---|
| 홈 | `render_home_page()` |
| 추천 결과 | `render_search_page(policies)` |
| 상세 분석 | `render_detail_page(policies)` |
| 신청 가이드 | `render_guide_page(policies)` |
| 챗봇 | `render_chatbot_page(policies)` |

---

## 5. 데이터 구조: `policies.csv`

현재 `policies.csv`에는 12개의 정책 데이터가 들어 있다. 주요 컬럼은 다음과 같다.

| 컬럼명 | 설명 | 예시 |
|---|---|---|
| `rank` | 정책 노출 순위 | `1` |
| `title` | 정책명 | `청년일자리도약장려금` |
| `category` | 정책 분야 | `취업`, `금융`, `주거` |
| `icon` | 카드에 표시할 아이콘 | `💼` |
| `description` | 정책 요약 설명 | `중소기업에 취업한 청년...` |
| `period` | 신청 기간 | `2026.01.01 ~ 2026.12.31` |
| `age` | 대상 연령 | `만 15세 ~ 34세` |
| `support` | 지원 내용 | `최대 1200만원 지원` |
| `method` | 신청 방법 | `고용24에서 신청` |
| `income` | 소득 조건 | `제한 없음` |
| `docs` | 제출 서류 | `근로계약서, 고용보험 확인자료` |
| `status` | 신청 상태 | `신청 가능` |
| `status_class` | CSS 배지 클래스 | `badge-green` |
| `detail` | 상세 라벨 | `취업` |
| `region` | 대상 지역 | `전국`, `서울` |
| `job_status` | 대상 직업 상태 | `중소기업 재직자`, `무관` |
| `housing_status` | 대상 주거 상태 | `월세`, `무관` |
| `score` | 추천 정렬용 점수 | `98` |
| `official_url` | 공식 신청/안내 URL | `https://www.work24.go.kr` |

현재 화면에서는 주로 `title`, `category`, `icon`, `description`, `period`, `age`, `support`, `method`, `income`, `docs`, `status`, `status_class`, `detail`, `official_url`이 사용된다.

---

## 6. 유틸 모듈

### 6.1 `data_loader.py`

정책 CSV 파일을 읽어 리스트 딕셔너리 형태로 변환한다.

```python
def load_policies():
    df = pd.read_csv("../data/policies.csv", encoding="utf-8-sig")
    return df.to_dict(orient="records")
```

반환 예시는 다음과 같다.

```python
[
    {
        "rank": 1,
        "title": "청년일자리도약장려금",
        "category": "취업",
        ...
    },
    ...
]
```

### 6.2 `html_renderer.py`

여러 줄 HTML 문자열을 Streamlit에 안전하게 렌더링하기 위한 함수가 정의되어 있다.

```python
def render_html(markup):
    normalized = "\n".join(
        line.strip()
        for line in textwrap.dedent(markup).splitlines()
        if line.strip()
    )
    st.markdown(normalized, unsafe_allow_html=True)
```

주요 목적은 들여쓰기 때문에 Markdown이 코드 블록으로 인식되는 문제를 줄이는 것이다.

### 6.3 `condition_parser.py`

사용자의 자연어 입력에서 나이, 지역, 연소득, 직업 상태, 관심 분야를 간단한 정규식과 키워드 기반으로 추출한다.

추출 대상 필드는 다음과 같다.

```python
{
    "age": None,
    "region": None,
    "income": None,
    "job_status": None,
    "interest": []
}
```

현재 인식 가능한 표현은 다음과 같다.

| 항목 | 인식 방식 | 예시 |
|---|---|---|
| 나이 | `숫자 + 살` | `27살` |
| 소득 | `연소득 + 숫자` | `연소득 3000` |
| 지역 | 지역명 포함 여부 | `서울`, `부산`, `경기` |
| 직업 상태 | 키워드 포함 여부 | `중소기업`, `취준`, `취업준비`, `창업` |
| 관심 분야 | 분야 키워드 포함 여부 | `취업`, `금융`, `주거`, `교육`, `창업` |

### 6.4 `recommender.py`

정책 상태 배지, 추천 정렬, 조건 비교 함수가 정의되어 있다.

#### `get_status_badge(status)`

정책 상태 문자열에 따라 CSS 클래스를 반환한다.

| 상태 | 반환 클래스 |
|---|---|
| 신청 가능 | `badge-green` |
| 조건 확인 필요 | `badge-orange` |
| 마감 임박 | `badge-red` |
| 그 외 | `badge-blue` |

#### `recommend_policies(policies, user_profile)`

현재는 정책의 `score` 값을 기준으로 내림차순 정렬한다.

#### `check_conditions(policy, user_profile)`

사용자 조건과 정책 조건을 비교하여 나이, 지역, 소득, 현재 상태에 대한 판정 리스트를 반환한다.

현재 이 모듈은 정의는 되어 있으나 추천 결과 페이지에 완전히 연결되어 있지는 않다. 향후 조건 기반 추천을 강화할 때 연결할 수 있다.

---

## 7. 페이지별 기능 정리

## 7.1 홈 화면: `home_page.py`

홈 화면은 서비스 소개, 자연어 입력, 조건 추출 버튼, 예시 질문, 서비스 흐름을 보여준다.

### 주요 기능

1. 서비스 소개 Hero 영역 표시
2. 자연어 입력 텍스트 영역 제공
3. `조건 추출하기` 버튼 클릭 시 조건 파싱
4. 추출된 조건을 `st.session_state.profile`에 반영
5. 추천 결과 페이지로 자동 이동

### 동작 흐름

```text
사용자 자연어 입력
→ parse_user_query(user_query)
→ 추출 결과를 session_state.profile에 반영
→ result_query, filter_* 세션 값 설정
→ st.session_state.page = "추천 결과"
→ st.rerun()
```

### 기본 입력 예시

```text
27살, 서울 거주, 연소득 3000만원, 중소기업 재직자야. 받을 수 있는 청년 정책 알려줘.
```

---

## 7.2 사용자 조건 입력 화면: `profile_page.py`

사용자 조건을 직접 입력하는 폼 화면이다. 현재 `app.py`의 네비게이션에는 연결되어 있지 않지만, 독립 페이지로 사용할 수 있는 구조를 갖고 있다.

### 입력 항목

| 항목 | UI 컴포넌트 |
|---|---|
| 나이 | `st.number_input` |
| 지역 | `st.selectbox` |
| 연소득 | `st.number_input` |
| 현재 상태 | `st.selectbox` |
| 주거 상태 | `st.selectbox` |
| 관심 분야 | `st.multiselect` |

폼 제출 시 `st.session_state.profile`을 갱신하고 추천 결과 페이지로 이동한다.

---

## 7.3 추천 결과 화면: `search_page.py`

추천 결과 화면은 현재 프론트엔드의 핵심 페이지이다. 왼쪽에는 조건 수정 패널이 있고, 오른쪽에는 조건에 맞는 정책 카드가 표시된다.

### 주요 기능

1. 자연어 재검색
2. 조건 재추출
3. 수동 필터 입력
4. 관심 분야 기반 정책 필터링
5. 마감 정책 제외 토글
6. 정책 카드 목록 출력
7. 현재 적용 조건 요약 표시

### 필터 기준

현재 실제 필터링은 주로 관심 분야와 마감 여부 기준으로 수행된다.

```python
filtered_policies = [
    policy for policy in policies
    if not selected_interests or policy["category"] in selected_interests
]
```

마감 정책 제외가 켜져 있으면 `_is_closed_policy()`로 마감 여부를 판단해 제외한다.

```python
if exclude_closed:
    filtered_policies = [
        policy for policy in filtered_policies
        if not _is_closed_policy(policy)
    ]
```

### 마감 정책 판단 방식

`_is_closed_policy(policy)`는 다음 기준으로 마감 여부를 판단한다.

1. `status` 값이 `마감`, `신청 마감`, `접수 마감`이면 마감 처리
2. `period`에서 날짜를 추출한 뒤 마지막 날짜가 오늘보다 이전이면 마감 처리

### 정책 카드 표시 정보

각 정책 카드는 다음 정보를 보여준다.

| 표시 영역 | 내용 |
|---|---|
| 좌측 | 순위, 아이콘, 카테고리 |
| 상단 | 정책명, 상태 배지, 상세 라벨 |
| 본문 | 설명, 신청기간, 대상연령, 지원내용 |
| 하단 | 신청방법, 소득조건, 제출서류 |
| 우측 | 신청하기, 출처 보기 버튼 형태 UI |

현재 `신청하기`와 `출처 보기`는 실제 클릭 가능한 버튼이 아니라 HTML `div`로 표시된 시각 요소이다. 실제 링크 기능을 넣으려면 `official_url`을 사용하는 `<a>` 태그나 `st.link_button()`으로 교체해야 한다.

---

## 7.4 정책 상세 분석 화면: `detail_page.py`

정책을 하나 선택한 뒤 사용자의 조건과 정책 조건을 표 형태로 비교하는 화면이다.

### 주요 기능

1. 정책 선택 드롭다운
2. 선택 정책의 기본 정보 카드 표시
3. 조건 비교 데이터프레임 출력
4. 추천 이유 표시

### 현재 한계

현재 상세 분석의 사용자 정보는 다음 값으로 하드코딩되어 있다.

```text
나이: 27세
지역: 서울특별시
소득: 3,000만원
취업 상태: 중소기업 재직자
주거 상태: 월세
```

따라서 홈 화면이나 추천 결과 화면에서 수정한 `st.session_state.profile` 값이 반영되지 않는다. 향후에는 다음과 같이 세션 기반으로 바꾸는 것이 좋다.

```python
profile = st.session_state.profile
```

---

## 7.5 신청 가이드 화면: `guide_page.py`

선택한 정책의 신청 절차와 필요 서류를 단계별로 안내하는 화면이다.

### 주요 기능

1. 정책 선택 드롭다운
2. 신청 기간 및 상태 표시
3. 신청 절차 5단계 출력
4. 공식 사이트 링크 표시
5. 신청 전 유의사항 경고 표시

### 신청 절차

```text
1. 공식 사이트 접속
2. 회원가입 또는 본인 인증
3. 신청서 작성
4. 필요 서류 제출
5. 심사 결과 확인
```

공식 URL은 다음 순서로 결정된다.

```python
official_url = policy.get("official_url") or OFFICIAL_SITES.get(policy["title"])
```

즉, CSV에 `official_url`이 있으면 해당 값을 우선 사용하고, 없으면 `OFFICIAL_SITES` 딕셔너리에 등록된 기본 URL을 사용한다.

---

## 7.6 챗봇 화면: `chatbot_page.py`

챗봇 화면은 현재 실제 LLM/RAG 연동이 아닌 정적 데모 UI로 구성되어 있다.

### 현재 구성

1. 사용자 질문 예시 말풍선
2. AI 답변 예시 말풍선
3. 자주 묻는 질문 카드
4. 질문 입력창
5. 질문하기 버튼

### 현재 예시 질문

```text
청년도약계좌랑 청년일자리도약장려금은 같이 받을 수 있어?
```

### 현재 한계

`st.text_input()`과 `st.button()`은 존재하지만 입력값을 처리하는 로직은 아직 없다. 향후 FastAPI의 `/api/chat` 또는 RAG 서비스와 연결해야 한다.

---

## 8. CSS 구조: `style.css`

`style.css`는 Streamlit 기본 UI를 보완하고, 카드형 정책 추천 서비스에 맞는 디자인을 제공한다.

### 주요 스타일 영역

| 영역 | 주요 클래스 |
|---|---|
| 전체 앱 배경 | `.stApp`, `.block-container` |
| 상단 헤더 | `.top-header`, `.brand`, `.brand-title`, `.brand-sub` |
| 홈 Hero | `.hero-section`, `.hero-title`, `.hero-subtitle`, `.hero-desc` |
| 예시 칩 | `.example-area`, `.example-chip` |
| 서비스 흐름 | `.flow-section`, `.flow-grid`, `.flow-item` |
| 검색 결과 | `.search-result-box`, `.info-box`, `.result-title` |
| 정책 카드 | `.policy-card`, `.policy-layout`, `.policy-title`, `.policy-meta` |
| 배지 | `.badge-green`, `.badge-blue`, `.badge-orange`, `.badge-red` |
| 신청 가이드 | `.guide-step`, `.step-num`, `.guide-site-link` |
| 챗봇 | `.chat-layout`, `.chat-bubble-user`, `.chat-bubble-ai` |

### 반응형 처리

`@media (max-width: 900px)` 구간에서 모바일 화면에 맞게 다음 요소들이 조정된다.

1. Hero 이미지 숨김
2. 서비스 흐름을 세로 배치로 변경
3. 정책 카드 레이아웃을 단일 컬럼으로 변경
4. 채팅 레이아웃을 단일 컬럼으로 변경

---

## 9. 현재 구현된 사용자 흐름

```text
[홈]
사용자가 자연어로 조건 입력
예: "27살, 서울 거주, 연소득 3000만원, 중소기업 재직자야"

↓

[조건 추출]
condition_parser.py에서 나이, 지역, 소득, 직업 상태, 관심 분야 추출

↓

[세션 저장]
st.session_state.profile 갱신

↓

[추천 결과]
관심 분야와 마감 여부 기준으로 정책 필터링
정책 카드 목록 표시

↓

[상세 분석]
정책별 조건 비교 표 확인

↓

[신청 가이드]
신청 절차, 필요 서류, 공식 사이트 링크 확인

↓

[챗봇]
정책 관련 질문 화면 확인
```

---

## 10. 현재 코드의 장점

1. `app.py`, `views`, `utils`, `styles`가 분리되어 있어 구조가 이해하기 쉽다.
2. `st.session_state`를 사용해 페이지 간 사용자 조건을 공유한다.
3. CSV 기반이므로 백엔드 없이도 프론트엔드 단독 시연이 가능하다.
4. 정책 카드 UI, 신청 가이드, 상세 분석 등 발표 시연에 필요한 화면이 이미 구성되어 있다.
5. `official_url` 컬럼을 활용하면 실제 신청 링크 연결로 확장하기 쉽다.
6. `chatbot_page.py`가 별도로 분리되어 있어 추후 RAG 챗봇 API만 연결하면 된다.

---

## 11. 현재 한계 및 개선 필요 사항

## 11.1 추천 로직이 아직 단순함

현재 추천 결과 페이지는 주로 관심 분야와 마감 여부만 기준으로 필터링한다. 나이, 지역, 소득, 직업 상태, 주거 상태를 종합적으로 반영한 추천 점수 계산은 아직 약하다.

### 개선 방향

- `recommender.py`의 `recommend_policies()` 연결
- `check_conditions()` 결과를 정책 카드에 표시
- 조건 충족 개수에 따라 추천 점수 재계산
- `가능성 높음`, `추가 확인 필요`, `가능성 낮음` 등 판정 라벨 추가

## 11.2 상세 분석 화면이 하드코딩되어 있음

`detail_page.py`의 사용자 조건은 현재 고정값이다. 홈 또는 추천 결과에서 변경한 조건이 반영되도록 수정해야 한다.

### 개선 방향

```python
profile = st.session_state.profile
```

이 값을 사용해 `내 정보` 컬럼을 동적으로 구성한다.

## 11.3 신청하기 버튼이 실제 버튼이 아님

추천 결과 카드의 `신청하기 ↗`, `출처 보기`는 현재 HTML `div`로 표시된다. 클릭 이벤트나 링크 이동 기능은 없다.

### 개선 방향

- `st.link_button("신청하기 ↗", p["official_url"])` 사용
- 또는 HTML `<a>` 태그로 변경
- URL이 없는 정책은 `출처 확인 필요` 표시

## 11.4 챗봇이 정적 데모 상태임

현재 챗봇 페이지는 실제 질문 처리 로직이 없다.

### 개선 방향

- `requests.post()`로 FastAPI `/api/chat` 호출
- 응답 JSON에서 `answer`, `recommendations`, `sources`를 받아 표시
- `st.session_state.messages`로 대화 히스토리 관리

## 11.5 자연어 조건 추출 범위가 좁음

현재 조건 추출은 정규식과 키워드 기반이다. 다음 표현은 놓칠 가능성이 있다.

| 표현 | 현재 처리 가능성 |
|---|---|
| `만 27세` | 낮음 |
| `연봉 3000` | 낮음 |
| `소득은 3000만원` | 낮음 |
| `서울시 거주` | 가능 |
| `경기도 거주` | 일부 가능 |
| `무직` | 낮음 |
| `대학생` | 낮음 |
| `프리랜서` | 낮음 |

### 개선 방향

- 정규식 패턴 확장
- 직업 상태 키워드 추가
- 지역명 전체 목록 확장
- LLM 기반 조건 추출 API로 대체

---

## 12. FastAPI/RAG 연동 시 권장 구조

향후 백엔드와 연결할 경우 프론트엔드는 다음 API를 호출하는 구조로 확장할 수 있다.

| 화면 | 호출 API | 용도 |
|---|---|---|
| 홈 | `POST /api/conditions/extract` | 자연어 조건 추출 |
| 추천 결과 | `POST /api/recommend` 또는 `POST /api/chat` | 조건 기반 정책 추천 |
| 상세 분석 | `GET /api/policies/{policy_id}` | 정책 상세 정보 조회 |
| 신청 가이드 | `GET /api/policies/{policy_id}` | 신청 방법, 서류, 링크 조회 |
| 챗봇 | `POST /api/chat` | RAG 기반 질의응답 |

### 추천 결과 API 응답 예시

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
      "policy_id": "youth_employment_001",
      "title": "청년일자리도약장려금",
      "category": "취업",
      "eligibility": "가능성 높음",
      "reason": "나이, 고용 상태, 지역 조건이 일치합니다.",
      "required_documents": ["근로계약서", "고용보험 확인자료"],
      "source_url": "https://www.work24.go.kr"
    }
  ],
  "warnings": [
    "일부 소득 조건은 공식 공고 확인이 필요합니다."
  ]
}
```

---

## 13. 우선 수정하면 좋은 작업 목록

### 1순위: 상세 분석 페이지 동적화

`detail_page.py`에서 하드코딩된 사용자 조건을 `st.session_state.profile` 기반으로 변경한다.

### 2순위: 신청 링크 실제 연결

`search_page.py`의 `신청하기`와 `출처 보기`를 실제 링크 버튼으로 변경한다.

### 3순위: 추천 로직 연결

`recommender.py`의 조건 비교 로직을 `search_page.py`에 연결해 정책별 조건 충족 여부를 표시한다.

### 4순위: 챗봇 API 연동

`chatbot_page.py`에서 질문 입력값을 받아 FastAPI `/api/chat`으로 전송하고 답변을 화면에 표시한다.

### 5순위: 조건 추출 패턴 확장

`condition_parser.py`에 나이, 소득, 지역, 직업 상태 표현을 추가한다.

---

## 14. 발표/시연 관점 요약

현재 프론트엔드는 다음 내용을 시연할 수 있다.

1. 자연어 입력으로 사용자 조건 추출
2. 추출된 조건을 기반으로 추천 결과 페이지 이동
3. 관심 분야와 마감 여부 기준 정책 카드 필터링
4. 정책별 신청 기간, 대상 연령, 지원 내용, 제출 서류 확인
5. 정책 상세 분석 화면 확인
6. 신청 가이드에서 공식 사이트 링크 확인
7. 챗봇 UI 데모 확인

다만 실제 RAG 기반 답변과 정책 조건 기반 정밀 추천은 아직 백엔드/RAG 연동이 필요하다. 따라서 현재 프론트엔드는 최종 서비스의 UI 프로토타입이자 CSV 기반 fallback 화면으로 볼 수 있다.

---

## 15. 결론

현재 Streamlit 프론트엔드는 프로젝트의 서비스 흐름을 보여주기에 충분한 기본 구조를 갖추고 있다. 특히 홈, 추천 결과, 상세 분석, 신청 가이드, 챗봇 화면이 분리되어 있어 발표용 시연 흐름을 구성하기 좋다.

향후 작업의 핵심은 화면을 새로 만드는 것이 아니라, 현재 화면에 실제 추천 로직과 RAG/FastAPI 응답을 연결하는 것이다. 즉, 프론트엔드는 현재 구조를 유지하고 다음 항목을 보강하는 방향이 적절하다.

1. 조건 기반 추천 점수 계산
2. 정책별 자격 판단 결과 표시
3. 신청 링크 실제 연결
4. 상세 분석의 세션 조건 반영
5. 챗봇의 FastAPI/RAG API 연동

이 작업들이 완료되면 현재 프론트엔드는 단순 화면 목업을 넘어, 청년 정책 RAG 서비스의 실제 사용자 인터페이스로 사용할 수 있다.
