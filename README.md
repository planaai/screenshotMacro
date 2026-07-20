# Plana AI Screenshot Extractor

이 프로젝트는 OCR 기능을 통해 **블루 아카이브**의 학생 및 스킬 정보를 파싱하여 [plana.ai](https://plana.ai) 서버와 동기화하는 도구입니다. 스크린샷 캡처부터 정보 추출, 서버 업로드까지의 과정을 자동화 및 매크로 기능으로 더욱 쉽고 빠르게 진행할 수 있도록 돕습니다.

---

## 시작하기 전에 (공통 사용법)

<img width="600" alt="로그인 화면" src="https://github.com/user-attachments/assets/3ce1a6d6-a432-4a32-89ec-c1118da6492a" />

1. 프로그램 실행 후, `plana.ai`에 가입된 **아이디와 비밀번호로 로그인**합니다.

<img width="600" alt="모드 선택" src="https://github.com/user-attachments/assets/0bfe0d99-f03b-4790-a1b9-44dd023d0904" />

2. **스캐너 모드**와 **매크로 모드** 중 원하는 기능을 선택해 주세요.

---

## 1. 스캐너 모드 사용 방법 (수동 캡처)

원하는 학생을 직접 확인하며 하나씩 스캔하고 업로드할 때 유용합니다.

1. 프로그램에서 **[스캐너 캡쳐 시작 대기]** 버튼을 누른 후, Steam 버전 블루 아카이브 클라이언트를 켜주세요.
   <br><img width="600" alt="스캐너 대기" src="https://github.com/user-attachments/assets/ef3a345b-f0e6-4e4c-803e-fce07f8ce0dc" />

2. 인게임에서 **스캔할 학생의 상세 정보 창**을 띄워주세요.
   > **참고:** 블루 아카이브 창만 캡처하는 것이 아니라 전체 화면을 캡처하므로, 중간에 시스템 팝업 등이 나타나지 않도록 주의해 주세요.
   <br><img width="600" alt="학생 상세창" src="https://github.com/user-attachments/assets/7b392835-c576-4c69-92bc-2b189174ff63" />

3. 캡처가 완료되면 프로그램에 나타난 **추출 결과를 검수**해 주세요.
   <br><img width="600" alt="결과 검수" src="https://github.com/user-attachments/assets/3885e1d1-fd82-4806-85a4-20400d2e5839" />

4. 검수가 끝났다면 **바로 업로드**를 진행합니다. 캡처가 잘못되었다면 취소 후, 다시 대기 상태 버튼을 눌러 2번 과정부터 재시도하시면 됩니다.

---

## 2. 매크로 모드 사용 방법 (자동 캡처)

학생 목록을 자동으로 넘기며 연속으로 스크린샷을 촬영하고 추출합니다.

> **매크로 사용 전 주의사항**
> * **Steam 블루 아카이브 클라이언트**를 기준으로 제작되었습니다. 타 앱플레이어(에뮬레이터)에서의 정상 작동은 보장하지 않습니다.
> * 시작한 학생을 기준으로 **한 바퀴를 다 돌 때까지 무한 반복**하는 시스템입니다.
> * 매크로가 도는 중에는 **마우스나 키보드 조작을 절대 삼가주세요.** 매크로가 꼬일 수 있습니다.

### 특정 학생만 업로드하고 싶을 때
전체 학생이 아닌 일부 학생만 업로드하길 원한다면, 인게임 정렬 필터링 설정에서 아래 사진과 같이 **[셀렉트]** 항목만 필터링되도록 설정한 후 매크로를 실행해 주세요.
<img width="600" alt="필터링 설정" src="https://github.com/user-attachments/assets/70f1d971-8901-4fe8-901c-64868f5112e5" />

### 매크로 실행 순서
1. 프로그램 로비에서 **[매크로 대기]** 버튼을 눌러주세요.
   <br><img width="600" alt="매크로 대기" src="https://github.com/user-attachments/assets/280ffb1e-462a-49a7-8361-8657b7503e32" />

2. 블루 아카이브를 실행하고, 시작점인 **학생의 상세 정보 창**을 띄워주세요.
   <br><img width="600" alt="학생 상세창" src="https://github.com/user-attachments/assets/29ebcf06-4651-46b9-95f3-a3efbfceefa5" />

3. 그 상태에서 키보드 **`[F8]`** 키를 눌러 매크로를 시작합니다.
   > **비상 정지 단축키:** 매크로 작동 중 긴급하게 멈춰야 할 경우 **`[F9]`** 키를 누르시면 즉시 중지됩니다.

4. 매크로가 종료되면 위 스캐너 모드와 동일하게 결과를 검수하고 서버에 **일괄 업로드**하시면 됩니다.
   <br><img width="600" alt="업로드" src="https://github.com/user-attachments/assets/008907ee-eaae-4aca-b7e2-12e849e9c207" />

---

## 3. 일괄 인식 기능 (기존 스크린샷 활용)

이미 찍어둔 스크린샷 파일들을 모아 한 번에 정보를 추출하는 모드입니다.

1. 미리 스크린샷 파일들을 하나의 폴더에 모아둡니다.
2. 해당 폴더를 우클릭한 후 **경로로 복사**를 눌러주세요.
   <br><img width="500" alt="경로 복사" src="https://github.com/user-attachments/assets/1341d744-a41e-4380-94f7-d9eeb4ec52de" />
3. 프로그램의 폴더 선택 칸에 복사한 경로를 붙여넣거나, 폴더 선택 버튼을 눌러 직접 폴더를 지정해 주세요.
   <br><img width="600" alt="폴더 지정" src="https://github.com/user-attachments/assets/25a17a24-129a-48c6-aedf-6b398009da4a" />
4. **[일괄 추출 시작]** 버튼을 눌러주세요.
   <br><img width="600" alt="일괄 추출" src="https://github.com/user-attachments/assets/b74bea9b-13dd-4f09-b6cb-e4f04499764c" />
5. 완료 후 상세 항목을 검수하고 **서버에 일괄 업로드** 하거나, 오류 제보를 위해 **오류 제출용 데이터 압축 저장**을 선택하실 수 있습니다.
   <br><img width="600" alt="결과 화면" src="https://github.com/user-attachments/assets/03e20b32-9605-4dce-bca8-4105ce892bfc" />

---

## 설치 및 실행 방법

### 일반 사용자용 (.exe 실행)
Python 환경 설정 없이 바로 실행하고 싶으신 분들을 위한 방법입니다.
* 제공된 `Release_Executable` 압축 파일을 해제합니다.
* 폴더 내에 있는 **`Plana_AI_Extractor.exe`** 파일을 실행하면 즉시 사용할 수 있습니다.

### 개발자용 (소스 코드로 실행)
직접 코드를 수정하거나 Python 환경에서 실행하고 싶으신 분들을 위한 방법입니다.

**1. 패키지 요구 사항 설치**
프로젝트 루트 경로에서 아래 명령어를 통해 필요한 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
```

**2. 프로그램 실행**
```bash
python gui_app.py
```

**3. 실행 파일(exe) 빌드 방법**
코드 수정 후 새로운 `.exe` 파일로 빌드하려면 PyInstaller를 사용합니다.
```bash
pyinstaller Plana_AI_Extractor_beta.spec
```
빌드가 완료되면 `dist/` 폴더 안에 실행 가능한 `.exe` 파일과 관련 리소스가 생성됩니다.
