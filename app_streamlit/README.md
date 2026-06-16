# 이젠, 안쉼 Streamlit 프론트엔드

현재 문서는 **프론트엔드 v1.4** 구현을 기준으로 작성되었습니다.

청년 정책·창업 공고·교육 정보를 한 화면에서 검색하고, 조건에 맞는 정책의
신청 링크와 공식 출처를 확인할 수 있는 Streamlit 애플리케이션입니다.

## 1. v1.4 주요 기능

- 로고와 서비스명을 홈 버튼으로 사용
- 새 PNG 로고를 화면 로고와 브라우저 탭 아이콘에 공통 적용
- 홈 로고 버튼의 hover 안내 문구 제거
- 상단 메뉴: `추천 결과`, `신청 가이드`, `챗봇`
- 홈 검색창에서 버튼 또는 Enter로 검색
- 추천 결과의 조건 검색창에서 `조건 추출` 버튼 또는 Enter로 검색
- 자연어에서 나이, 지역, 소득, 상태, 관심 분야 추출
- 조건 추출 결과는 기본 검색 조건으로 저장하고, 조건 입력 필터는 추가 필터로 적용
- 홈 검색 또는 재검색 후 조건 입력 필터는 빈 상태로 표시
- 조건 입력 필터에서 나이, 지역, 관심 분야를 선택해 현재 검색 결과를 더 좁힘
- 로컬 조건 파서 우선 처리, 백엔드 조건 추출 API는 필요한 경우에만 짧게 보조 호출
- 홈 검색과 조건 추출 처리 중 백구 로딩 오버레이 표시
- 검색 전에는 전체 건수 요약을 표시하지 않고 빈 검색 안내 표시
- 마감 여부 기반 결과 필터링
- 관련도 순 정렬 및 페이지당 10개 페이지네이션
- 페이지 이동 후 스크롤을 결과 목록 상단으로 복원
- 정책 카드 전체 영역을 클릭해 상세 팝업 표시
- 상세 팝업에서 정책 정보와 사용자 조건 비교
- 카드의 `신청하기`, `출처 보기` 링크는 팝업 클릭 영역에서 제외
- 신청 가이드에서 검색된 정책만 선택 가능
- 신청 가이드 검색 전 또는 검색 결과 없음 상태에서는 빈 안내 화면 표시
- FastAPI 챗봇 API 연동
- 현재 앱 버전 `v1.4` 표시

독립된 `상세 분석` 페이지는 v1.3에서 삭제되었습니다. 상세 정보는 추천 결과
화면의 정책 카드를 클릭했을 때 열리는 팝업에서 확인합니다.

## 2. 디렉터리 구조

```text
4th_project/
├─ backend/                          # FastAPI 조건 추출·RAG 챗봇 API
└─ app_streamlit/
   ├─ app.py
   ├─ README.md
   ├─ assets/
   │  ├─ logo.png
   │  └─ policy_loading.png
   ├─ data/
   │  └─ processed/
   │     └─ opportunities.json
   ├─ styles/
   │  └─ style.css
   ├─ utils/
   │  ├─ api_client.py
   │  ├─ condition_parser.py
   │  ├─ data_loader.py
   │  └─ html_renderer.py
   └─ views/
      ├─ home_page.py
      ├─ search_page.py
      ├─ guide_page.py
      └─ chatbot_page.py
```

## 3. 실행 방법

### 프론트엔드 필수 패키지

```powershell
python -m pip install streamlit pandas pillow requests
```

프로젝트 전체 백엔드까지 실행하려면 프로젝트 루트의 `requirements.txt`와
FastAPI 실행 패키지가 필요합니다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
python -m pip install -r requirements.txt
python -m pip install fastapi uvicorn pydantic
```

### Streamlit 실행

`style.css`를 상대 경로로 읽기 때문에 `app_streamlit` 폴더에서 실행합니다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project\app_streamlit
python -m streamlit run app.py --server.port 8501
```

접속 주소:

```text
http://localhost:8501
```

### 챗봇 사용 조건

프로젝트 루트에서 FastAPI 백엔드를 실행합니다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
python -m uvicorn backend.main:app --reload --port 8000
```

프론트엔드는 다음 API를 사용합니다.

```text
POST http://localhost:8000/api/conditions/extract
POST http://localhost:8000/api/chat
```

조건 추출 API의 기본 서버 주소는 `BACKEND_URL` 환경 변수로 바꿀 수 있습니다.

```powershell
$env:BACKEND_URL="http://localhost:8000"
```

조건 추출 보조 API의 응답 대기 시간은 `CONDITION_EXTRACT_TIMEOUT`으로 조정할 수
있습니다. 기본값은 `2.5`초입니다.

```powershell
$env:CONDITION_EXTRACT_TIMEOUT="2.5"
```

현재 챗봇 API 주소는 `chatbot_page.py`에
`http://localhost:8000/api/chat`으로 지정되어 있습니다. 백엔드가 실행되지
않으면 조건 검색은 로컬 규칙 기반 파서로 대체되고, 챗봇에는 연결 오류가
표시됩니다.

## 4. 앱 구조

### `app.py`

앱의 진입점입니다.

- `APP_VERSION = "v1.4"`
- Streamlit 페이지 설정과 CSS 로드
- 로고 이미지의 Data URI 생성
- 로고와 브라우저 탭 아이콘은 `docs/images/home_logo.png` 사용
- 정책 데이터 로드
- 공통 세션 상태 초기화
- 로고 홈 버튼과 상단 메뉴 렌더링
- 선택한 페이지 렌더링

현재 페이지 구성:

| 화면 | 렌더링 함수 |
|---|---|
| 홈 | `render_home_page(policies)` |
| 추천 결과 | `render_search_page(policies)` |
| 신청 가이드 | `render_guide_page(policies)` |
| 챗봇 | `render_chatbot_page(policies)` |

이전 세션 값이 `상세 분석`인 경우 자동으로 `추천 결과` 화면으로 이동합니다.

### 기본 세션 상태

```python
st.session_state.page = "홈"
st.session_state.has_searched = False
st.session_state.profile = {
    "age": 27,
    "region": "서울",
    "income": 3000,
    "job_status": "중소기업 재직자",
    "housing_status": "월세",
    "interest": [],
}
```

기본 프로필은 내부 검색 상태 초기화에 사용합니다. 추천 결과 탭을 바로 열거나
홈에서 검색해 이동한 경우에도 수동 조건 입력 필터의 나이, 지역, 관심 분야는
선택되지 않은 상태로 표시됩니다. 홈에서 추출한 조건은
`st.session_state.profile`과 `st.session_state.search_base_profile`에 저장되어
검색 결과 계산에는 적용됩니다. 이후 조건 입력 필터를 적용하면
`search_base_profile` 위에 사용자가 입력한 필터 조건을 추가해 결과를 더 좁힙니다.

## 5. 데이터

### 데이터 경로

```text
app_streamlit/data/processed/opportunities.json
```

`utils/data_loader.py`는 `app_streamlit` 폴더를 기준으로 이 파일을 찾습니다.

현재 확인된 데이터:

| 항목 | 값 |
|---|---:|
| 통합 지원 정보 | 26,803건 |
| 정책 제공 기관 | 3,166개 |
| 화면 분류 | 6개 |

화면 분류는 `취업`, `교육`, `창업`, `주거`, `금융`, `복지`입니다.

### 화면 모델

`load_policies()`는 원본 JSON을 다음 공통 필드로 변환하고 `info_score`
내림차순으로 정렬합니다.

| 화면 필드 | 주요 원본 필드 |
|---|---|
| `id` | `item_id` |
| `title` | `title` |
| `description` | `summary` |
| `category` | `source_category`, `domain` |
| `period` | 신청 기간 또는 프로그램 기간 |
| `age` | `age_min`, `age_max` |
| `support` | `benefit_text` |
| `method` | `application_method` |
| `income` | `target_text` |
| `region` | `region`, `location` |
| `application_url` | `application_url` |
| `source_url` | `source_url` |
| `organization` | `organization` |
| `score` | `info_score` |

데이터는 `st.cache_data`로 캐시됩니다. 원본에 없는 정보는 임의로 만들지 않고
`공식 공고 확인`으로 표시합니다. 대상 연령 정보가 없거나 `0~0`으로 들어온
데이터는 `연령 정보 없음`으로 표시합니다.

## 6. 화면별 동작

### 홈

`views/home_page.py`

- 서비스 소개와 데이터 통계 표시
- 자연어 검색창 제공
- `AI에게 물어보기` 버튼 또는 Enter로 제출
- 예시 질문 버튼 제공
- 조건 추출 후 추천 결과 화면으로 이동

검색 흐름:

```text
자연어 입력
→ 로컬 parse_user_query() 실행
→ 로컬에서 조건이 잡히면 즉시 결과 조건으로 사용
→ 로컬에서 조건을 못 잡은 경우에만 POST /api/conditions/extract 보조 요청
→ API 실패 또는 타임아웃 시 로컬 결과만 사용
→ 추출값으로 결과 계산용 profile/search_base_profile 저장
→ 수동 필터의 나이·지역·관심 분야는 빈 상태로 초기화
→ has_searched = True
→ 추천 결과 이동
```

### 추천 결과

`views/search_page.py`

#### 조건 검색

- 검색어 입력 후 `조건 추출` 버튼 또는 Enter로 제출
- 조건 추출 결과는 기본 검색 조건으로 결과에 바로 적용
- 나이, 지역, 관심 분야 입력 후 `조건 적용`을 누르면 기본 검색 조건 위에 추가 필터 적용
- 추천 결과 탭 최초 진입 시 필터 기본 선택값 없음
- 홈 검색 직후에도 나이·지역·관심 분야 필터는 모두 미선택
- 추천 결과 화면에서 `조건 추출`을 다시 누르면 기본 검색 조건은 새 검색어 기준으로 바뀌고 필터 UI는 초기화
- 조건 입력 필터에는 적용할 조건을 하나 이상 입력하면 됨

#### 결과 계산

결과는 다음 조건을 사용합니다.

- 관심 분야와 정책 카테고리
- 사용자 나이와 정책 대상 연령
- 사용자 지역과 정책 지역
- 마감 정책 제외 여부
- 검색어 토큰과 정책 `search_text` 일치도
- 데이터 `info_score`

관련도 점수는 `info_score`에 검색어 일치 점수를 더해 계산합니다. 이는 최종
자격 판정 점수가 아니며, 실제 신청 가능 여부는 공식 공고를 확인해야 합니다.

#### 결과 목록

- 전체 일치 건수 표시
- 검색 전에는 전체 건수 요약 대신 빈 검색 안내 표시
- 기본값으로 마감 정책 제외
- 페이지당 10개 정책 표시
- 이전/다음 버튼으로 전체 결과 탐색
- 페이지 전환 시 별도 로딩 오버레이 없이 바로 결과 갱신
- 페이지 이동 후 스크롤을 결과 목록 상단으로 부드럽게 복원
- 정책 지원 내용은 카드에서 두 줄로 생략

#### 정책 카드와 상세 팝업

- 카드의 정보 영역을 클릭하면 `st.dialog` 상세 팝업 표시
- 신청 기간, 대상 연령, 지역, 기관, 지원 내용, 자격 조건, 신청 방법 표시
- 사용자 조건과 정책 조건 비교표 표시
- 팝업에서 신청 가이드로 이동 가능
- 팝업은 열릴 때 상단부터 표시되고 내부 스크롤 가능

카드의 `신청하기`와 `출처 보기`는 팝업 버튼과 분리된 외부 링크입니다.

링크 우선순위:

```text
신청하기: application_url → official_url → source_url
출처 보기: source_url → official_url → application_url
```

유효한 HTTP 또는 HTTPS 주소가 없으면 `신청 링크 없음` 또는 `출처 없음`으로
표시합니다.

### 신청 가이드

`views/guide_page.py`

- 추천 결과에서 검색된 정책만 선택 목록에 표시
- 팝업에서 이동한 경우 해당 정책을 기본 선택
- 홈 검색 전이거나 검색 결과가 없으면 빈 상태 안내 표시
- 신청 기간과 현재 상태 표시
- 신청 절차 5단계 표시
- 공식 사이트 링크 제공

검색 결과가 없을 때 전체 정책을 임의로 표시하지 않습니다.

### 챗봇

`views/chatbot_page.py`

- `st.chat_message` 기반 대화 기록 표시
- `st.chat_input`으로 질문 입력
- 질문에서 나이, 지역, 관심 분야 등을 먼저 추출하고 현재 사용자 프로필로 보완
- 비어 있는 프로필 값은 임의 기본값으로 채우지 않고 `null`로 전달
- FastAPI `/api/chat`에 `top_k=5`로 요청
- 응답의 `answer` 값을 대화 기록에 저장
- 백엔드 연결 및 응답 오류 안내

요청 예시:

```json
{
  "message": "25살에 맞는 청년 정책 추천해줘",
  "user_profile": {
    "age": 25,
    "region": null,
    "income": null,
    "employment_status": null,
    "interest_domain": "전체"
  },
  "top_k": 5
}
```

## 7. 자연어 조건 추출

`utils/api_client.py`, `utils/condition_parser.py`

먼저 로컬 정규식과 키워드로 기본 조건을 추출합니다. 로컬 파서가 나이, 지역,
주거 상태, 관심 분야 등 하나 이상의 조건을 찾으면 백엔드 API를 기다리지 않고
즉시 결과를 계산합니다.

로컬 파서가 조건을 찾지 못한 경우에만 `POST /api/conditions/extract`로
보조 추출을 요청합니다. 백엔드 호출은 짧은 타임아웃을 사용하고, 같은 문장은
프론트엔드에서 캐시해 반복 검색 시 재호출을 줄입니다. API 호출에 실패하면
로컬 추출 결과를 그대로 사용합니다.

로컬 파서가 인식하는 값:

| 조건 | 예시 |
|---|---|
| 나이 | `27살` |
| 연소득 | `연소득 3000` |
| 지역 | `서울`, `부산`, `대구`, `인천`, `광주`, `대전`, `경기` |
| 상태 | `중소기업`, `취준`, `취업준비`, `창업` |
| 관심 분야 | `취업`, `금융`, `주거`, `교육`, `창업` |

`월세`, `전세`, `주택`, `주거비`가 포함되면 관심 분야에 `주거`를 추가합니다.

## 8. CSS와 UI

`styles/style.css`

- 고정 색상과 글꼴을 사용해 운영체제 테마 영향 최소화
- 큰 로고 이미지와 굵은 서비스명을 하나의 홈 버튼으로 구성
- 홈 로고 버튼에 별도 hover 툴팁을 표시하지 않음
- 활성 메뉴 파란색 표시
- 홈 Hero, 검색창, 예시 질문, 통계 카드 구성
- 홈 `AI에게 물어보기` 버튼의 파란색 디자인 유지
- 홈 검색과 조건 추출 중 `assets/policy_loading.png` 기반 로딩 오버레이 표시
- 조건 입력 팁은 `먼저 검색 → 필요 시 나이·지역·관심 분야 추가 적용` 흐름 안내
- 정책 카드 전체 클릭 영역과 외부 링크 영역 분리
- 버튼 hover/active 피드백과 부드러운 스크롤 적용
- `prefers-reduced-motion` 환경에서는 모션 최소화
- 900px, 620px 기준 반응형 레이아웃 적용

## 9. 현재 제한 사항

1. 추천은 규칙 기반이며 최종 자격 판정 모델이 아닙니다.
2. 소득·직업·주거 조건은 원본 데이터 구조 한계로 정밀 필터링하지 않습니다.
3. 자연어 파서는 제한된 표현만 인식합니다.
4. AI 조건 추출은 FastAPI와 OpenAI 설정이 없으면 로컬 파서로 대체됩니다.
5. 상세 팝업 비교표의 일부 판정은 `확인 필요` 또는 `공식 공고 확인`입니다.
6. 챗봇은 FastAPI와 관련 검색 백엔드가 실행되어야 동작합니다.
7. 신청 서류가 원본에 없으면 신청 가이드에서 `공식 공고 확인`으로 표시합니다.

## 10. 검증

문법 검사:

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project\app_streamlit
python -m py_compile app.py views\home_page.py views\search_page.py views\guide_page.py views\chatbot_page.py
```

주요 확인 항목:

- 로고 클릭 시 홈 이동
- 상단 메뉴 이동
- 홈 버튼 및 Enter 검색
- 조건 검색창 버튼 및 Enter 검색
- 홈 검색 후 수동 조건 필터 미선택 상태
- 조건 추출 후 수동 조건 필터 초기화
- 조건 입력 필터가 기본 검색 조건 위에 추가 필터로 적용되는지 확인
- 조건 입력 필터를 비운 채 적용할 때 안내 메시지 표시
- 마감 정책 제외 토글
- 10개 단위 페이지 이동
- 정책 카드 상세 팝업
- 신청 및 출처 외부 링크
- 상세 팝업의 신청/출처 링크 버튼 오류 없이 표시
- 제목 옆 자동 앵커 링크 아이콘 숨김
- 연령 정보가 없는 정책은 `연령 정보 없음`으로 표시
- 팝업에서 신청 가이드 이동
- 검색 전 신청 가이드 빈 상태
- 검색 후 신청 가이드 정책 목록 연동
- 챗봇 백엔드 연결 오류 처리

## 11. 버전 정보

### v1.4

- 앱 표시 버전 `v1.4`로 변경
- 조건 추출 결과를 기본 검색 조건으로 저장하고, 조건 입력 필터는 추가 필터로 적용
- 홈 검색과 추천 결과 재검색 후 조건 입력 필터를 빈 상태로 초기화
- 조건 입력 필터를 비운 채 적용하면 사용자 안내 메시지 표시
- 검색 전에는 전체 정책 건수 요약을 표시하지 않고 빈 검색 안내 표시
- 로컬 조건 파서를 우선 사용해 조건 추출 버튼 반응 속도 개선
- 백엔드 조건 추출 API 호출 타임아웃 단축 및 동일 문장 캐시 적용
- 홈 검색과 조건 추출 처리 중 백구 로딩 오버레이 표시
- 로고 파일 경로를 `docs/images/home_logo.png`로 통일해 다른 PC에서도 경로 오류 없이 실행
- 조건 입력 팁 문구를 실제 사용자 흐름에 맞게 수정
- 페이지 이동 후 스크롤을 결과 목록 상단으로 복원
- Streamlit 제목 옆 자동 앵커 링크 아이콘 숨김
- 상세 팝업의 `st.link_button` 오류를 피하기 위해 신청/출처 링크를 HTML 링크 버튼으로 통일
- 연령 하한·상한이 없거나 `0~0`인 데이터는 데이터 정규화와 화면 렌더링 단계에서 모두 `연령 정보 없음`으로 표시
- 앱 버전 변경 시 데이터 로드 전에 `st.cache_data`를 초기화해 정규화 변경사항이 즉시 반영되도록 처리
- 챗봇 요청 프로필에서 `None` 값을 안전하게 처리하고, 질문에서 추출한 조건을 우선 반영

### v1.3

- 독립 상세 분석 페이지 삭제
- 정책 카드 상세 팝업 방식으로 통합
- 로고를 홈 버튼으로 변경하고 홈 메뉴 제거
- 검색 결과 10개 단위 페이지네이션
- 페이지 전환 동작 개선
- 홈 검색 후 조건 입력 필터를 빈 상태로 표시
- 신청하기·출처 보기 링크와 카드 팝업 클릭 영역 분리
- 홈 검색창 Enter 제출 지원
- 조건 검색창 Enter 제출 지원
- 프로젝트 PNG 로고로 화면 로고와 브라우저 탭 아이콘 교체
- 홈 로고 버튼의 hover 안내 문구 제거
- 페이지 이동 시 표시되던 로딩 오버레이와 목록 흐림 효과 제거
- 버튼 전환과 페이지 이동 반응 개선
- 로고와 서비스명 크기·굵기 개선
- 신청 가이드에서 검색된 정책만 표시
- 신청 가이드 검색 전 기본 상태를 빈 결과로 변경
- 버전 표시 `v1.3`
