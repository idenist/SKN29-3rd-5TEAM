@echo off
chcp 65001 > nul
echo [1/7] 프로젝트 폴더 이동
cd /d C:\Users\Playdata\Downloads\youth-support-data-final-evaluation-package\youth-support-data-final-evaluation-package

echo [2/7] Java 확인
java -version
IF %0% NEQ 0 (
  echo Java가 없어 Temurin JDK 17 설치를 시도합니다.
  winget install EclipseAdoptium.Temurin.17.JDK --silent --accept-package-agreements --accept-source-agreements
  echo Java 설치 후 PATH 반영을 위해 CMD를 새로 열어야 할 수 있습니다.
)

echo [3/7] conda base 활성화
call C:\Users\Playdata\miniconda3\Scripts\activate.bat
call conda activate base

echo [4/7] pip 업그레이드
python -m pip install --upgrade pip

echo [5/7] JPype1 / KoNLPy 설치
python -m pip install JPype1 konlpy

echo [6/7] KoNLPy Okt 테스트
python -c "from konlpy.tag import Okt; okt=Okt(); print(okt.nouns('청년 창업 지원사업과 국민내일배움카드 교육과정을 추천합니다'))"
IF %0% NEQ 0 (
  echo KoNLPy 테스트 실패. Java 설치 직후라면 CMD를 완전히 닫고 다시 열어서 이 BAT 파일을 다시 실행하세요.
  pause
  exit /b 1
)

echo [7/7] KoNLPy 기반 분석 재실행
python scripts\analyze_korean_text.py
python scripts\build_text_features.py

echo 완료. analyzer=konlpy_okt 라고 나오면 성공입니다.
pause
