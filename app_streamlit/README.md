# 이젠, 안쉼 Streamlit 앱

청년 정책, 창업 공고, 교육·훈련 데이터를 통합 탐색하는 Streamlit 기반 프론트엔드입니다.

현재 앱은 임시 CSV가 아닌 백엔드 전처리 결과인
`data/processed/opportunities.json`을 사용합니다.

## 1. 실행 환경

현재 확인된 개발 환경은 다음과 같습니다.

- Windows PowerShell
- Python 3.13.12
- Streamlit 1.58.0
- pandas

필요한 패키지가 없다면 다음 명령어로 설치합니다.

```powershell
python -m pip install streamlit pandas
```

## 2. 실행 방법

PowerShell에서 프로젝트 루트로 이동합니다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
```

다음 명령어로 앱을 실행합니다.

```powershell
python -m streamlit run app.py
```

실행 후 브라우저에서 다음 주소로 접속합니다.

```text
http://localhost:8501
```

포트를 직접 지정하려면 다음과 같이 실행합니다.

```powershell
python -m streamlit run app.py --server.port 8501
```

앱 종료는 실행 중인 PowerShell에서 `Ctrl+C`를 누릅니다.

## 3. 주요 폴더 구조

```text
4th_project/
├─ app.py
├─ README.md
├─ data/
│  ├─ processed/
│  │  ├─ opportunities.json
│  │  └─ opportunity_chunks.jsonl
│  ├─ raw/
│  └─ reports/
├─ data_temp/
│  └─ policies.csv
├─ styles/
│  └─ style.css
├─ utils/
│  ├─ condition_parser.py
│  ├─ data_loader.py
│  ├─ html_renderer.py
│  └─ recommender.py
└─ views/
   ├─ home_page.py
   ├─ search_page.py
   ├─ detail_page.py
   ├─ guide_page.py
   └─ chatbot_page.py
```

## 4. 사용 데이터

### 화면 데이터

앱은 다음 파일을 읽습니다.

```text
data/processed/opportunities.json
```

현재 데이터는 총 26,803건이며 다음 항목을 포함합니다.

- 청년 정책: `policy`
- 창업 공고: `startup_notice`
- 교육·훈련: `training`

데이터 로딩 경로와 화면용 필드 변환은
`utils/data_loader.py`에서 관리합니다.

### RAG 데이터

다음 파일은 RAG 임베딩 및 벡터 DB 구축용입니다.

```text
data/processed/opportunity_chunks.jsonl
```

현재 Streamlit 목록 화면은 이 파일을 직접 읽지 않습니다.

### 임시 데이터

기존 임시 데이터는 다음 위치에 백업되어 있습니다.

```text
data_temp/policies.csv
```

현재 앱 코드에서는 `data_temp`를 참조하지 않습니다. 실제 데이터 연결에
문제가 생겼을 때 비교·검증하는 용도로만 유지합니다.

## 5. 실제 데이터 변환 규칙

`opportunities.json`의 원본 필드를 기존 화면이 사용하는 공통 모델로
변환합니다.

| 화면 필드 | 실제 데이터 기준 |
|---|---|
| 고유 ID | `item_id` |
| 제목 | `title` |
| 설명 | `summary` |
| 분야 | `source_category`, `domain` 조합 |
| 신청 기간 | `application_*` 또는 `program_*` |
| 대상 연령 | `age_min`, `age_max` |
| 지원 내용 | `benefit_text` |
| 신청 방법 | `application_method` |
| 대상 조건 | `target_text` |
| 지역 | `region` 또는 `location` |
| 신청 링크 | `application_url` |
| 출처 링크 | `source_url` |
| 정렬 기준 | `info_score` 및 검색어 일치도 |

`info_score`는 사용자 적합도 점수가 아니라 데이터 완성도 점수입니다.
현재 화면에서는 기본 정렬 보조값으로만 사용합니다.

원본에 없는 제출 서류나 세부 조건은 임의로 생성하지 않고
`공식 공고 확인`으로 표시합니다.

## 6. 구현된 화면 흐름

1. 홈에서 자연어 조건을 입력합니다.
2. `조건 추출하기`를 누르면 나이, 지역, 소득, 현재 상태, 관심 분야를
   `st.session_state`에 저장합니다.
3. 별도의 조건 입력 탭을 거치지 않고 추천 결과로 이동합니다.
4. 추천 결과 왼쪽 필터에서 추출된 조건을 확인하고 수정할 수 있습니다.
5. 관심 분야, 나이, 지역, 검색어, 마감 여부를 반영해 결과를 필터링합니다.
6. 전체 일치 건수를 표시하고 관련도 상위 30건만 카드로 렌더링합니다.
7. 실제 `application_url`과 `source_url`이 있을 때 신청 및 출처 버튼을
   제공합니다.

## 7. 주요 UX 변경 사항

- `조건 입력` 독립 탭 제거
- 자연어 추출 후 추천 결과로 바로 이동
- 추천 결과 왼쪽에 조건 입력 필터 배치
- 현재 적용 조건 요약 표시
- `카드 보기` 컨트롤 제거
- `마감 정책 제외` 토글 기본 활성화
- 토글 해제 시 마감 정책 포함
- 신청 가이드 1단계에 공식 사이트 링크 추가
- 상세 및 신청 가이드 정책 선택 기준을 제목이 아닌 `item_id`로 변경

## 8. 데이터 갱신 방법

백엔드 전처리를 다시 수행한 경우 다음 파일을 같은 경로에 교체합니다.

```text
data/processed/opportunities.json
data/processed/opportunity_chunks.jsonl
```

앱에서 필요한 필드 이름이 유지되면 별도 코드 변경 없이 다시 실행할 수
있습니다. 필드 구조가 변경된 경우 `utils/data_loader.py`의 정규화 로직도
함께 수정해야 합니다.

Streamlit 캐시 때문에 교체한 데이터가 즉시 반영되지 않으면 앱을 종료한 뒤
다시 실행합니다.

```powershell
cd C:\Users\nowis\Desktop\SKN\4th_project
python -m streamlit run app.py
```

## 9. 확인 사항

- 실제 데이터 26,803건 로딩 확인
- 추천 결과 최대 30건 렌더링 확인
- 마감 정책 토글 동작 확인
- 상세 분석 정책 26,803건 선택 가능 여부 확인
- 신청 가이드 공식 링크 연결 확인
- 앱 코드 내 `data_temp` 및 `policies.csv` 참조 제거 확인

## 10. 현재 제한 사항

- 자연어 조건 추출은 정규식과 키워드 기반의 간단한 파서입니다.
- 소득과 직업 상태는 실제 데이터의 구조화 필드가 부족해 정밀 판정에
  사용하지 않습니다.
- 추천 결과는 아직 벡터 검색이나 LLM 기반 RAG 결과가 아니라 키워드,
  분야, 지역, 나이, 데이터 완성도를 조합한 결과입니다.
- 상세 자격 및 제출 서류는 반드시 공식 공고에서 최종 확인해야 합니다.
