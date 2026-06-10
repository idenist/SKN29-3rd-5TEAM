# K-Startup 창업공고 청년 HIGH 전처리 문서

## 1. 개요

본 문서는 K-Startup 창업공고 데이터를 청년 지원 통합 탐색 에이전트에 통합하기 위한 전처리 기준을 설명한다.

K-Startup 전체 창업공고를 모두 사용하는 것이 아니라, 청년과 직접적인 관련성이 명확한 `HIGH` 데이터만 온통청년 정책 데이터와 통합한다.

## 2. 입력 데이터

- 파일명: `data/raw/kstartup_api/kstartup_announcements_raw.csv`
- 원본 건수: 29,017건
- 원본 컬럼 수: 30개

## 3. 주요 판단 컬럼

청년 관련성 판단에는 아래 원본 컬럼을 사용한다.

- `biz_pbanc_nm`: 사업공고명
- `intg_pbanc_biz_nm`: 통합공고사업명
- `pbanc_ctnt`: 공고 내용
- `aply_trgt`: 신청 대상
- `aply_trgt_ctnt`: 신청 대상 상세
- `biz_trgt_age`: 사업 대상 연령
- `prfn_matr`: 우대사항
- `supt_biz_clsfc`: 지원사업 분류
- `biz_enyy`: 사업 업력
- `aply_excl_trgt_ctnt`: 신청 제외 대상

## 4. HIGH 분류 기준

아래 조건 중 하나라도 명확히 해당하면 `HIGH`로 분류한다.

### 4.1 청년 키워드 명시

- 청년
- 청년창업
- 청년기업
- 청년창업센터
- 청년 스타트업
- 청년 예비창업자
- 청년창업자
- 청년층

### 4.2 청년 연령 기준 명확

- 만 19세
- 만 34세 이하
- 만 39세 이하
- 19세~39세
- 20세~39세

단, `만 40세 이상`이 함께 포함된 경우에는 청년 전용으로 보지 않고 `MEDIUM`으로 분류한다.  
다만 청년 키워드 또는 청년 우대 조건이 명확하면 `HIGH`가 우선한다.

### 4.3 청년 우대 조건

- 청년 우대
- 청년 가점
- 청년기업 우대
- 청년창업자 우대
- 청년층 우대
- 청년 참여 우대

청년 우대 공고는 청년 전용이 아니더라도 청년에게 유리한 공고이므로 `HIGH`로 분류한다.

## 5. MEDIUM / LOW 처리

### MEDIUM

청년도 신청 가능성이 있지만 청년 전용 또는 청년 우대가 명확하지 않은 데이터이다.

예시:

- 예비창업자
- 초기창업자
- 창업 3년 이내
- 창업 7년 이내
- 스타트업
- 창업기업
- 청년 연령대가 포함되지만 40세 이상도 함께 포함된 경우

현재 단계에서는 온통청년 정책 데이터와 통합하지 않는다.

### LOW

청년 관련성이 낮거나 일반 기업 대상 성격이 강한 데이터이다.

현재 단계에서는 온통청년 정책 데이터와 통합하지 않는다.

## 6. 전처리 결과

| 분류 | 건수 | 비율 |
|---|---:|---:|
| HIGH | 3,789 | 13.06% |
| MEDIUM | 25,208 | 86.87% |
| LOW | 20 | 0.07% |

## 7. 통합 대상

온통청년 정책 데이터와 통합하는 대상은 아래 파일이다.

```text
data/processed/startup_youth_high_only.json
```

RAG 통합 대상은 아래 파일이다.

```text
data/processed/startup_youth_high_chunks.jsonl
```

## 8. 실행 방법

```bash
python scripts/preprocess_kstartup_youth.py --input data/raw/kstartup_api/kstartup_announcements_raw.csv --output-dir data/processed
```

## 9. 주의사항

- 원본 CSV는 절대 수정하지 않는다.
- 최종 통합 대상은 HIGH만이다.
- MEDIUM / LOW는 참고용으로만 보관한다.
- 없는 값은 임의로 채우지 않는다.
- 청년 우대는 HIGH로 분류한다.
- 통합 데이터에서는 `item_id`를 고유 식별자로 사용한다.
