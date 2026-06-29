# Plana AI Screenshot Extractor

이 프로젝트는 OCR 기능을 통해 블루아카이브의 학생 및 스킬 정보를 파싱하여 plana.ai 서버와 동기화하는 도구이자 매크로로 스크린샷을 더욱 쉽게 찍을 수 있도록 돕습니다.


## 사용방법
<img width="1197" height="743" alt="Image" src="https://github.com/user-attachments/assets/3ce1a6d6-a432-4a32-89ec-c1118da6492a" />
1. plana.ai에서 회원가입한 id랑 비밀번호로 로그인을 합니다



<img width="1189" height="721" alt="Image" src="https://github.com/user-attachments/assets/44d9e6ec-e6ca-4411-aeb0-36885f8d18a9" />
2. 단일 파일 선택 / 폴더 선택 중 하나를 골라 파일이나 디렉토리를 지정합니다.




<img width="1187" height="717" alt="Image" src="https://github.com/user-attachments/assets/c439464c-d6a9-42ff-94e4-93e333919a63" />
3. 지정 후 일괄 추출 시작 버튼을 누릅니다




<img width="1102" height="739" alt="Image" src="https://github.com/user-attachments/assets/6456b13a-4009-48c5-a5b8-b6a8cfbd27a3" />
4. 여기서 추출 결과를 확인 합니다. 추출 결과에 따라 검수 필요 상태가 뜰 수 있으니 참고 바랍니다. (검수 필요 상태의 기준은 스캔 후 필드가 비어 있거나 하는 경우에 발생하며, 설령 스캔을 해도 오류값으로 채워지는 경우 준비됨 상태로 채워지니 유의 부탁 드립니다)




<img width="1091" height="730" alt="Image" src="https://github.com/user-attachments/assets/92b3dda5-3a76-4197-bcc1-2c3f28fdf124" />
4-1. 만약 상세검수를 할 경우에는 먼저 확인할 학생의 데이터를 클릭후 선택 항목 상세 검수 버튼을 클릭합니다




<img width="1491" height="932" alt="Image" src="https://github.com/user-attachments/assets/b93e7ca9-c4b5-4c30-9897-6368acb9e6be" />
4-2. 오류등을 수정할때 사진을 참고해 옆에 있는 데이터 필드를 수정해주세요. 다 수정 하셨다면 초록 버튼을 업로드를 취소 하실 예정이면 빨간 버튼을 눌러주시면 되겠습니다.




<img width="1087" height="726" alt="Image" src="https://github.com/user-attachments/assets/a29db03b-af22-439e-b1f9-a96c86d1ec26" />
5. Yes를 누르시면 본인의 계정에 업로드한 데이터가 등록 됩니다




## 매크로 사용방법
<img width="1202" height="739" alt="Image" src="https://github.com/user-attachments/assets/d88ccbd5-1cc3-4c34-8f3c-b7e9c0033482" />
1. 우선 매크로 대기 버튼을 로비에서 눌러주세요.
 



<img width="2560" height="1440" alt="Image" src="https://github.com/user-attachments/assets/29ebcf06-4651-46b9-95f3-a3efbfceefa5" />
2. 블루아카이브를 실행하고 학생의 상세정보 창을 위와 같이 띄워주세요.




### 주의사항
### 해당 매크로는 Steam 블루아카이브 클라이언트를 기준으로 만들었습니다. 그 외의 에뮬레이터 같은 프로그램에서의 정상작동은 저도 장담할수 없습니다. 그러니 Steam 버전으로 해주세요.
### 또한 이 메크로의 작동 방식은 처음 시작한 학생을 기준으로 한바퀴를 다 돌아서 올때까지 무한반복하는 시스템입니다. 그러니 일부 학생만 업로드 하시길 원한다면, 스크린샷을 여러번 해서 폴더 선택 업로드 혹은 인게임에서 원하는 학생을 셀렉트 후
### 필터링 설정에서 아래와 같이 셀렉트만 필터링 되게 해주시면 됩니다.
### <img width="2406" height="1176" alt="Image" src="https://github.com/user-attachments/assets/70f1d971-8901-4fe8-901c-64868f5112e5" />
### 혹시이긴 하지만 이제 만약의 경우를 대비해서 비상 정지 단축키를 설정해두었습니다. [F9] 를 누르시면 매크로를 중지시킬수 있습니다.




3. 2번 사진의 상태에서 [F8] 키를 눌러 매크로를 시작해주세요.
## 매크로 도는 중에는 절대로 다른 짓을 하시면 안됩니다. 매크로가 꼬여요.




<img width="1102" height="739" alt="Image" src="https://github.com/user-attachments/assets/008907ee-eaae-4aca-b7e2-12e849e9c207" />
4. 위의 사용방법을 반복하시거나 일괄로 서버에 업로드 하시면 됩니다





## .exe로 실행하기 (사용자용)

Release_Executable를 압축해제 하여 Plana_AI_Extractor.exe를 실행하면 됩니다.


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

### 실행 파일(exe) 빌드 방법

개발된 소스 코드를 다른 사용자가 별도의 환경 설정 없이 실행할 수 있도록 `.exe` 파일로 빌드하려면 PyInstaller를 사용합니다.

```bash
pyinstaller Plana_AI_Extractor.spec
```

빌드가 완료되면 `dist/` 폴더 안에 실행 가능한 `.exe` 파일과 관련 리소스가 생성됩니다.
