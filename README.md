# Plana AI Screenshot Extractor

이 프로젝트는 지정된 매크로 화면에서 필요한 이미지를 추출하고 OCR 기능을 통해 텍스트를 파싱하여 백엔드 서버와 동기화하는 도구입니다.

## 소스 코드로 실행하기 (개발자용)

### 1. 요구 사항 설치
본 프로젝트는 Python 환경을 필요로 합니다. 아래 명령어로 필요한 라이브러리를 설치할 수 있습니다:
```bash
pip install -r requirements.txt
```

### 2. 프로그램 실행
```bash
python gui_app.py
```

## 실행 파일(exe) 빌드 방법

개발된 소스 코드를 다른 사용자가 별도의 환경 설정 없이 실행할 수 있도록 `.exe` 파일로 빌드하려면 PyInstaller를 사용합니다.

```bash
pyinstaller Plana_AI_Extractor.spec
```

빌드가 완료되면 `dist/` 폴더 안에 실행 가능한 `.exe` 파일과 관련 리소스가 생성됩니다.
