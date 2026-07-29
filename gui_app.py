import sys
import os

if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    try:
        os.add_dll_directory(sys._MEIPASS)
        ort_capi = os.path.join(sys._MEIPASS, 'onnxruntime', 'capi')
        if os.path.exists(ort_capi):
            os.environ['PATH'] = ort_capi + os.pathsep + os.environ.get('PATH', '')
            os.add_dll_directory(ort_capi)
    except AttributeError:
        pass

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import threading
import extractor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QStackedWidget, QFileDialog, 
                             QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
                             QFormLayout, QMessageBox, QDialog, QAbstractItemView, QProgressBar)
from PyQt5.QtGui import QFontDatabase, QFont, QPixmap, QPainter, QColor, QIcon, QResizeEvent
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QThread
import json
import math
import macro
import scanner
import requests
import subprocess
import time

APP_VERSION = "v1.0.0"
GITHUB_REPO = "planaai/screenshotMacro"

class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest_version = data.get("tag_name", "")
                if latest_version and latest_version != APP_VERSION:
                    assets = data.get("assets", [])
                    download_url = ""
                    for asset in assets:
                        if asset.get("name", "").endswith(".zip"):
                            download_url = asset.get("browser_download_url", "")
                            break
                    if not download_url:
                        for asset in assets:
                            if asset.get("name", "").endswith(".exe"):
                                download_url = asset.get("browser_download_url", "")
                                break
                    if not download_url and assets:
                        download_url = assets[0].get("browser_download_url", "")
                    
                    if download_url:
                        self.update_available.emit(latest_version, download_url, data.get("body", ""))
        except Exception as e:
            self.error_occurred.emit(str(e))

class DownloadUpdateThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        
    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=10)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with open(self.save_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                    self.progress.emit(100)
                else:
                    downloaded = 0
                    for data in response.iter_content(chunk_size=4096):
                        downloaded += len(data)
                        f.write(data)
                        self.progress.emit(int(100 * downloaded / total_size))
            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))

def get_asset_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Font Loading
FONT_PATH = get_asset_path(r"assets\font.otf")
BG_PATH = get_asset_path(r"assets\bg.jpg")

COLOR_PINK = "#f9a8d4"
COLOR_PINK_HOVER = "#f472b6"
COLOR_GREEN = "#86efac"
COLOR_GREEN_HOVER = "#4ade80"
COLOR_RED = "#fca5a5"
COLOR_RED_HOVER = "#f87171"
GLASS_BG = "rgba(255, 255, 255, 180)" # 70% opacity white for true liquid glass!

COMMON_STYLE = f"""
QLineEdit {{
    background-color: {GLASS_BG};
    border: 2px solid {COLOR_PINK};
    border-radius: 10px;
    padding: 10px;
    font-size: 16px;
}}
QPushButton {{
    background-color: {COLOR_PINK};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px;
    font-size: 16px;
}}
QPushButton:hover {{
    background-color: {COLOR_PINK_HOVER};
}}
QPushButton:disabled {{
    background-color: #d1d5db;
}}
QTextEdit {{
    background-color: {GLASS_BG};
    border: 2px solid {COLOR_PINK};
    border-radius: 10px;
    padding: 10px;
    font-family: Consolas;
    font-size: 13px;
}}
QMessageBox QLabel {{
    font-size: 13px;
}}
QMessageBox QPushButton {{
    background-color: {COLOR_PINK};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 5px 15px;
    font-size: 13px;
}}
QMessageBox QPushButton:hover {{
    background-color: {COLOR_PINK_HOVER};
}}
"""

_OriginalQMessageBox = QMessageBox

class CustomMessageBox:
    Yes = getattr(_OriginalQMessageBox, 'Yes', 16384)
    No = getattr(_OriginalQMessageBox, 'No', 65536)
    
    @staticmethod
    def _show(parent, title, text, icon_type):
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(350)
        
        # We use a QDialog with a custom stylesheet to guarantee it looks right
        dialog.setStyleSheet(f"QDialog {{ background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 10px; }} QLabel {{ color: #333333; font-size: 15px; font-weight: bold; padding: 10px; }} QPushButton {{ background-color: {COLOR_PINK}; color: white; border: none; border-radius: 5px; padding: 8px 20px; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: {COLOR_PINK_HOVER}; }}")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_text = QLabel(text)
        lbl_text.setAlignment(Qt.AlignCenter)
        lbl_text.setWordWrap(True)
        layout.addWidget(lbl_text)
        
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(15)
        
        if icon_type == "question":
            btn_yes = QPushButton("예 (Yes)")
            btn_no = QPushButton("아니오 (No)")
            btn_yes.setCursor(Qt.PointingHandCursor)
            btn_no.setCursor(Qt.PointingHandCursor)
            btn_yes.clicked.connect(lambda: dialog.done(CustomMessageBox.Yes))
            btn_no.clicked.connect(lambda: dialog.done(CustomMessageBox.No))
            btn_layout.addWidget(btn_yes)
            btn_layout.addWidget(btn_no)
        else:
            btn_ok = QPushButton("확인 (OK)")
            btn_ok.setCursor(Qt.PointingHandCursor)
            btn_ok.clicked.connect(lambda: dialog.done(CustomMessageBox.Yes))
            btn_layout.addWidget(btn_ok)
            
        layout.addLayout(btn_layout)
        
        # Remove context help button from title bar
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        return dialog.exec_()

    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        return CustomMessageBox._show(parent, title, text, "info")

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        return CustomMessageBox._show(parent, title, text, "warning")

    @staticmethod
    def critical(parent, title, text, *args, **kwargs):
        return CustomMessageBox._show(parent, title, text, "critical")

    @staticmethod
    def question(parent, title, text, *args, **kwargs):
        return CustomMessageBox._show(parent, title, text, "question")

QMessageBox = CustomMessageBox

class GlassWidget(QWidget):
    """A widget that draws the Steam screenshot as background."""
    def paintEvent(self, event):
        painter = QPainter(self)
        if os.path.exists(BG_PATH):
            pixmap = QPixmap(BG_PATH)
            # scale pixmap to fill the widget
            pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            # Center the pixmap
            x = (self.width() - pixmap.width()) // 2
            y = (self.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#fdf2f8"))

class WaitSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        
    def start(self):
        self.show()
        self.timer.start(50)
        
    def stop(self):
        self.hide()
        self.timer.stop()
        
    def rotate(self):
        self.angle = (self.angle + 30) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        
        num_dots = 12
        for i in range(num_dots):
            painter.setPen(Qt.NoPen)
            alpha = int(255 - (255 / num_dots) * i)
            painter.setBrush(QColor(100, 150, 255, alpha))
            painter.drawEllipse(8, -3, 6, 6)
            painter.rotate(-360 / num_dots)

class UploadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_upload = pyqtSignal(int, int) # success_count, fail_count
    
    def __init__(self, ready_items, jwt_token):
        super().__init__()
        self.ready_items = ready_items
        self.jwt_token = jwt_token
        
    def run(self):
        success_count = 0
        fail_count = 0
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        for i, res in enumerate(self.ready_items):
            data = res["data"]
            name = data.get("studentName", "Unknown")
            self.progress.emit(i, f"[{i+1}/{len(self.ready_items)}] {name} 데이터 전송 중...")
            
            try:
                payload = {
                    "studentName": data.get("studentName"),
                    "currentLevel": data.get("currentLevel"),
                    "currentStar": data.get("currentStar"),
                    "skills": data.get("skills", {}),
                    "equipment": data.get("equipment", {}),
                    "weapon": data.get("weapon", {}),
                    "stats": data.get("stats", {})
                }
                
                resp = requests.post(
                    "https://api.planaai.kro.kr/api/import/screenshot",
                    headers=headers,
                    json=payload,
                    timeout=5
                )
                
                if resp.status_code == 200:
                    res["status"] = "uploaded"
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"업로드 실패 ({name}): {resp.text}")
                    
            except Exception as e:
                fail_count += 1
                print(f"통신 오류 ({name}): {e}")
                
        self.progress.emit(len(self.ready_items), "업로드 완료 처리 중...")
        self.finished_upload.emit(success_count, fail_count)

class UploadProgressDialog(QDialog):
    def __init__(self, total_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 업로드")
        self.setFixedSize(350, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        
        self.spinner = WaitSpinner(self)
        spinner_layout = QHBoxLayout()
        spinner_layout.addStretch()
        spinner_layout.addWidget(self.spinner)
        spinner_layout.addStretch()
        layout.addLayout(spinner_layout)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, total_items)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("서버 연결 중...", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
    def update_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.status_label.setText(text)

class Signals(QObject):
    log_msg = pyqtSignal(str)
    batch_done = pyqtSignal()
    macro_done = pyqtSignal(str)
    scanner_done = pyqtSignal(object)

class ExtractApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("plana.ai 스크린샷 매크로 beta")
        self.setWindowIcon(QIcon(get_asset_path(r"assets\app_icon.ico")))
        self.resize(1200, 700)
        
        self.jwt_token = None
        self.selected_path = None
        self.batch_results = []
        
        # Load Font
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.app_font = QFont(font_family, 12)
            QApplication.setFont(self.app_font)
        else:
            self.app_font = QFont("맑은 고딕", 12)
            
        self.signals = Signals()
        self.signals.log_msg.connect(self.append_log)
        self.signals.batch_done.connect(self.on_batch_done)
        self.signals.macro_done.connect(self.on_macro_done_signal)
        self.signals.scanner_done.connect(self.on_scanner_done_signal)

        self.central_widget = GlassWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        self.main_layout.addWidget(self.stacked_widget)
        
        self.init_login_view()
        self.init_mode_select_view()
        self.init_scanner_view()
        self.init_dashboard_view()
        
        self.detail_view = DetailWindow(self)
        self.scanner_detail_view = ScannerDetailWindow(self)
        self.stacked_widget.addWidget(self.detail_view)
        self.stacked_widget.addWidget(self.scanner_detail_view)
        
        self.stacked_widget.setCurrentWidget(self.login_view)
        
        # redirect stdout/stderr
        class EmittingStream(object):
            def __init__(self, signal):
                self.signal = signal
            def write(self, text):
                if text.strip():
                    self.signal.emit(str(text))
            def flush(self):
                pass
                
        sys.stdout = EmittingStream(self.signals.log_msg)
        sys.stderr = EmittingStream(self.signals.log_msg)

        # Macro init
        def on_macro_done(save_dir):
            self.signals.macro_done.emit(save_dir)
            
        def on_macro_log(msg):
            self.signals.log_msg.emit(msg)
            
        self.macro_instance = macro.CaptureMacro(callback_done=on_macro_done, callback_log=on_macro_log)

        def on_scanner_done(result):
            self.signals.scanner_done.emit(result)
        self.scanner_instance = scanner.ScannerListener(callback_done=on_scanner_done, callback_log=on_macro_log)

        # Check for updates
        self.update_checker = UpdateCheckerThread()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.start()

    def on_update_available(self, version, download_url, notes):
        reply = QMessageBox.question(
            self,
            "업데이트 알림",
            f"새 버전({version})이 출시되었습니다. 다운로드하시겠습니까?\n\n{notes}"
        )
        if reply == CustomMessageBox.Yes:
            self.start_download_update(download_url)

    def start_download_update(self, url):
        self.update_progress = QProgressDialog("업데이트 다운로드 중...", "취소", 0, 100, self)
        self.update_progress.setWindowTitle("다운로드")
        self.update_progress.setWindowModality(Qt.WindowModal)
        self.update_progress.setMinimumDuration(0)
        self.update_progress.show()
        
        is_zip = url.lower().endswith('.zip')
        ext = ".zip" if is_zip else ".exe"
        save_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath("."), f"Plana_AI_Extractor_Update{ext}")
        
        self.download_thread = DownloadUpdateThread(url, save_path)
        self.download_thread.progress.connect(self.update_progress.setValue)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

    def on_download_error(self, err):
        if hasattr(self, 'update_progress'):
            self.update_progress.close()
        QMessageBox.critical(self, "오류", f"다운로드 실패: {err}")

    def on_download_finished(self, save_path):
        if hasattr(self, 'update_progress'):
            self.update_progress.close()
        QMessageBox.information(
            self,
            "업데이트 완료",
            "다운로드가 완료되었습니다. 앱을 재시작하여 업데이트를 적용합니다."
        )
        self.apply_update(save_path)

    def apply_update(self, new_exe_path):
        current_exe = sys.executable
        if not getattr(sys, 'frozen', False):
            QMessageBox.information(self, "안내", "개발 환경이므로 자동 교체를 건너뜁니다.")
            return

        current_dir = os.path.dirname(current_exe)
        bat_path = os.path.join(current_dir, "update.bat")

        if new_exe_path.lower().endswith('.zip'):
            import zipfile
            import shutil
            extract_dir = os.path.join(current_dir, "_update_temp")
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)
            with zipfile.ZipFile(new_exe_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            source_dir = extract_dir
            items = os.listdir(extract_dir)
            if len(items) == 1 and os.path.isdir(os.path.join(extract_dir, items[0])):
                source_dir = os.path.join(extract_dir, items[0])
                
            with open(bat_path, "w", encoding="ansi") as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak >nul\n')
                f.write(f'xcopy /y /e /h /c /i "{source_dir}\\*" "{current_dir}\\"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write(f'rmdir /s /q "{extract_dir}"\n')
                f.write(f'del "{new_exe_path}"\n')
                f.write('del "%~f0"\n')
        else:
            with open(bat_path, "w", encoding="ansi") as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak >nul\n')
                f.write(f'move /y "{new_exe_path}" "{current_exe}"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write('del "%~f0"\n')

        subprocess.Popen(bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)

    def init_login_view(self):
        self.login_view = QWidget()
        layout = QVBoxLayout(self.login_view)
        layout.setAlignment(Qt.AlignCenter)
        
        card = QWidget()
        card.setStyleSheet(f"background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 20px;")
        card.setFixedSize(400, 350)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(15)
        
        lbl_title = QLabel("plana.ai 로그인")
        lbl_title.setStyleSheet(f"color: {COLOR_PINK_HOVER}; font-size: 28px; border: none; background: transparent;")
        lbl_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lbl_title)
        
        self.entry_user = QLineEdit()
        self.entry_user.setPlaceholderText("아이디")
        self.entry_user.setStyleSheet(COMMON_STYLE)
        card_layout.addWidget(self.entry_user)
        
        self.entry_pass = QLineEdit()
        self.entry_pass.setPlaceholderText("비밀번호")
        self.entry_pass.setEchoMode(QLineEdit.Password)
        self.entry_pass.setStyleSheet(COMMON_STYLE)
        card_layout.addWidget(self.entry_pass)
        
        btn_login = QPushButton("로그인")
        btn_login.setStyleSheet(COMMON_STYLE)
        btn_login.setFixedHeight(50)
        btn_login.clicked.connect(self.do_login)
        self.entry_user.returnPressed.connect(self.do_login)
        self.entry_pass.returnPressed.connect(self.do_login)
        card_layout.addWidget(btn_login)
        
        layout.addWidget(card)
        self.stacked_widget.addWidget(self.login_view)
        
    def do_login(self):
        user = self.entry_user.text()
        pwd = self.entry_pass.text()
        if not user or not pwd:
            QMessageBox.warning(self, "입력 오류", "아이디와 비밀번호를 모두 입력하세요.")
            return
            
        try:
            resp = requests.post(
                "https://api.planaai.kro.kr/api/auth/login",
                json={"username": user, "password": pwd},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                self.jwt_token = data.get("token")
                user_info = data.get("user", {})
                nickname = user_info.get("nickname") or user
                QMessageBox.information(self, "로그인 성공", f"환영합니다, {nickname}님!")
                self.stacked_widget.setCurrentWidget(self.mode_select_view)
            else:
                err_msg = resp.json().get("error", "로그인 실패")
                QMessageBox.warning(self, "로그인 실패", err_msg)
        except Exception as e:
            QMessageBox.critical(self, "로그인 오류", f"서버와 통신 중 오류가 발생했습니다:\n{e}")

    def init_mode_select_view(self):
        self.mode_select_view = QWidget()
        layout = QVBoxLayout(self.mode_select_view)
        layout.setAlignment(Qt.AlignCenter)
        
        lbl_title = QLabel("모드 선택")
        lbl_title.setStyleSheet(f"color: {COLOR_PINK_HOVER}; font-size: 28px; border: none; background: transparent; margin-bottom: 20px;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)
        
        card_layout = QHBoxLayout()
        card_layout.setSpacing(30)
        
        btn_scanner = QPushButton("스캐너 모드 (단일)")
        btn_scanner.setStyleSheet(f"background-color: {GLASS_BG}; color: {COLOR_PINK_HOVER}; border: 3px solid {COLOR_PINK}; border-radius: 20px; font-size: 20px; font-weight: bold; padding: 30px;")
        btn_scanner.setFixedSize(300, 200)
        btn_scanner.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.scanner_view))
        
        btn_macro = QPushButton("매크로 모드 (일괄)")
        btn_macro.setStyleSheet(f"background-color: {GLASS_BG}; color: {COLOR_PINK_HOVER}; border: 3px solid {COLOR_PINK}; border-radius: 20px; font-size: 20px; font-weight: bold; padding: 30px;")
        btn_macro.setFixedSize(300, 200)
        btn_macro.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.dash_view))
        
        card_layout.addWidget(btn_scanner)
        card_layout.addWidget(btn_macro)
        
        layout.addLayout(card_layout)
        self.stacked_widget.addWidget(self.mode_select_view)

    def init_scanner_view(self):
        self.scanner_view = QWidget()
        layout = QVBoxLayout(self.scanner_view)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        header = QLabel("스캐너 모드 (단일 추출)")
        header.setStyleSheet(f"background-color: {GLASS_BG}; color: {COLOR_PINK_HOVER}; font-size: 24px; border: 2px solid {COLOR_PINK}; border-radius: 15px; padding: 15px;")
        layout.addWidget(header)
        
        ctrl_card = QWidget()
        ctrl_card.setStyleSheet(f"background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 15px;")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_info = QLabel("▶ 스캐너 모드 시작 버튼을 누르고 게임 창을 띄운 뒤 [F9] 키를 누르면 즉시 캡처 후 검수 창으로 이동합니다.")
        lbl_info.setStyleSheet("border: none; background: transparent; color: #333; font-size: 18px;")
        ctrl_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        self.btn_scanner_start = QPushButton("스캐너 캡처 시작 대기 (F9)")
        self.btn_scanner_start.setStyleSheet(COMMON_STYLE)
        self.btn_scanner_start.clicked.connect(self.start_scanner_listener)
        btn_layout.addWidget(self.btn_scanner_start)
        
        btn_back = QPushButton("모드 선택으로 돌아가기")
        btn_back.setStyleSheet(COMMON_STYLE)
        btn_back.clicked.connect(self.back_to_mode_select)
        btn_layout.addWidget(btn_back)
        
        btn_layout.addStretch()
        ctrl_layout.addLayout(btn_layout)
        layout.addWidget(ctrl_card)
        
        self.scanner_log_area = QTextEdit()
        self.scanner_log_area.setReadOnly(True)
        self.scanner_log_area.setStyleSheet(COMMON_STYLE)
        layout.addWidget(self.scanner_log_area)
        
        self.stacked_widget.addWidget(self.scanner_view)

    def start_scanner_listener(self):
        self.scanner_log_area.clear()
        self.scanner_instance.start_listener()
        
    def back_to_mode_select(self):
        self.scanner_instance.stop_listener()
        self.stacked_widget.setCurrentWidget(self.mode_select_view)

    def back_to_mode_select_from_dash(self):
        self.macro_instance.is_waiting = False
        self.stacked_widget.setCurrentWidget(self.mode_select_view)

    def on_scanner_done_signal(self, result):
        if not result:
            QMessageBox.warning(self, "추출 실패", "화면 캡처 및 인식에 실패했습니다. 다시 시도해주세요.")
            return
            
        self.scanner_detail_view.load_scanner_data(result)
        self.stacked_widget.setCurrentWidget(self.scanner_detail_view)

    def init_dashboard_view(self):
        self.dash_view = QWidget()
        layout = QVBoxLayout(self.dash_view)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("데이터 일괄 추출 대시보드")
        header.setStyleSheet(f"background-color: {GLASS_BG}; color: {COLOR_PINK_HOVER}; font-size: 24px; border: 2px solid {COLOR_PINK}; border-radius: 15px; padding: 15px;")
        layout.addWidget(header)
        
        # Controls
        ctrl_card = QWidget()
        ctrl_card.setStyleSheet(f"background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 15px;")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(20, 20, 20, 20)
        
        self.lbl_path = QLabel("📁 선택된 경로: 없음")
        self.lbl_path.setStyleSheet("border: none; background: transparent; color: #333; font-size: 16px;")
        ctrl_layout.addWidget(self.lbl_path)
        
        btn_layout = QHBoxLayout()
        self.btn_file = QPushButton("단일 파일 선택")
        self.btn_file.setStyleSheet(COMMON_STYLE)
        self.btn_file.clicked.connect(self.select_file)
        btn_layout.addWidget(self.btn_file)
        
        self.btn_folder = QPushButton("폴더 선택 (일괄)")
        self.btn_folder.setStyleSheet(COMMON_STYLE)
        self.btn_folder.clicked.connect(self.select_folder)
        btn_layout.addWidget(self.btn_folder)
        
        btn_layout.addStretch()
        
        self.btn_back_macro = QPushButton("홈으로 돌아가기")
        self.btn_back_macro.setStyleSheet(COMMON_STYLE)
        self.btn_back_macro.clicked.connect(self.back_to_mode_select_from_dash)
        btn_layout.addWidget(self.btn_back_macro)
        
        self.btn_macro = QPushButton("매크로 대기 (F8)")
        self.btn_macro.setStyleSheet(COMMON_STYLE)
        self.btn_macro.clicked.connect(self.start_macro)
        btn_layout.addWidget(self.btn_macro)
        
        self.btn_run = QPushButton("일괄 추출 시작 ▶")
        self.btn_run.setStyleSheet(COMMON_STYLE)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.run_sync)
        btn_layout.addWidget(self.btn_run)
        
        ctrl_layout.addLayout(btn_layout)
        layout.addWidget(ctrl_card)
        
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(COMMON_STYLE)
        layout.addWidget(self.log_area)
        
        self.stacked_widget.addWidget(self.dash_view)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "Image Files (*.png *.jpg *.jpeg)")
        if path:
            self.selected_path = path
            self.lbl_path.setText(f"📁 선택된 파일: {path}")
            self.btn_run.setEnabled(True)
            
    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if path:
            self.selected_path = path
            self.lbl_path.setText(f"📁 선택된 폴더: {path}")
            self.btn_run.setEnabled(True)

    def start_macro(self):
        self.log_area.clear()
        self.macro_instance.start_listener()

    def on_macro_done_signal(self, save_dir):
        self.selected_path = save_dir
        self.lbl_path.setText(f"📁 선택된 경로(매크로): {save_dir}")
        self.btn_run.setEnabled(True)
        self.run_sync()

    def append_log(self, msg):
        if hasattr(self, 'log_area'):
            self.log_area.append(msg)
        if hasattr(self, 'scanner_log_area'):
            self.scanner_log_area.append(msg)

    def run_sync(self):
        if not self.selected_path:
            return
            
        self.btn_run.setEnabled(False)
        self.btn_file.setEnabled(False)
        self.btn_folder.setEnabled(False)
        self.btn_macro.setEnabled(False)
        self.log_area.clear()
        
        print("작업 시작...")
        threading.Thread(target=self.process_path_thread, args=(self.selected_path,), daemon=True).start()

    def process_path_thread(self, path):
        self.batch_results.clear()
        try:
            if os.path.isdir(path):
                files = [f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                print(f"폴더 내 대상 이미지 {len(files)}개 발견.")
                for i, f in enumerate(files):
                    print(f"[{i+1}/{len(files)}] {f} 이미지 추출 중...")
                    self.process_single_image(os.path.join(path, f))
            else:
                self.process_single_image(path)
                
            self.deduplicate_results()
            print("모든 파일 추출 완료! 요약 창을 엽니다.")
        except Exception as e:
            import traceback
            print(f"오류 발생: {e}")
            traceback.print_exc()
        finally:
            self.signals.batch_done.emit()

    def process_single_image(self, img_path):
        data = extractor.extract_screenshot_data(img_path)
        if not data:
            self.batch_results.append({
                "path": img_path, "data": {}, "status": "failed", "needs_review": True
            })
            return
        needs_review = False
        if not data.get("studentName"): needs_review = True
        if data.get("currentLevel") is None: needs_review = True
            
        self.batch_results.append({
            "path": img_path, "data": data, "status": "pending", "needs_review": needs_review
        })

    def deduplicate_results(self):
        seen = {}
        for res in self.batch_results:
            name = res["data"].get("studentName")
            if not name:
                continue
            if name in seen:
                print(f"⚠️ 경고: '{name}' 캐릭터 스크린샷이 여러 장 발견되었습니다. 하나는 제외(건너뜀) 처리됩니다.")
                res["status"] = "skipped"
                res["needs_review"] = True
            else:
                seen[name] = res

    def on_batch_done(self):
        self.btn_run.setEnabled(True)
        self.btn_file.setEnabled(True)
        self.btn_folder.setEnabled(True)
        self.btn_macro.setEnabled(True)
        
        if not self.batch_results:
            QMessageBox.information(self, "결과 없음", "추출된 데이터가 없습니다.")
            return
            
        self.hide()
        self.overview_window = OverviewWindow(self.batch_results, self.jwt_token, self)
        self.overview_window.show()

class OverviewWindow(QMainWindow):
    def __init__(self, batch_results, jwt_token, parent_app):
        super().__init__()
        self.batch_results = batch_results
        self.jwt_token = jwt_token
        self.parent_app = parent_app
        
        self.setWindowTitle("배치 추출 결과 요약")
        self.resize(1100, 700)
        
        self.central_widget = GlassWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        lbl_title = QLabel("추출 결과 요약")
        lbl_title.setStyleSheet(f"background-color: transparent; color: {COLOR_PINK_HOVER}; font-size: 24px; font-weight: bold;")
        layout.addWidget(lbl_title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["상태", "파일명", "학생 이름", "레벨"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.doubleClicked.connect(self.open_detail)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {GLASS_BG};
                border: 2px solid {COLOR_PINK};
                border-radius: 10px;
                gridline-color: {COLOR_PINK};
                font-size: 16px;
            }}
            QHeaderView::section {{
                background-color: {COLOR_PINK};
                color: white;
                font-weight: bold;
                border: 1px solid #fbcfe8;
                padding: 5px;
                font-size: 17px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_PINK};
                color: white;
            }}
        """)
        layout.addWidget(self.table)
        
        self.refresh_tree()
        
        btn_layout = QHBoxLayout()
        
        btn_back = QPushButton("◀ 이전 (캡처 화면으로)")
        btn_back.setStyleSheet(COMMON_STYLE)
        btn_back.clicked.connect(self.close)
        btn_layout.addWidget(btn_back)
        
        btn_detail = QPushButton("🔍 선택 항목 상세 검수")
        btn_detail.setStyleSheet(COMMON_STYLE)
        btn_detail.clicked.connect(self.open_detail)
        btn_layout.addWidget(btn_detail)
        
        btn_layout.addStretch()
        
        btn_upload = QPushButton("☁️ 서버에 일괄 업로드")
        btn_upload.setStyleSheet(COMMON_STYLE)
        btn_upload.clicked.connect(self.upload_all)
        btn_layout.addWidget(btn_upload)
        
        btn_sync = QPushButton("📦 데이터 압축 저장")
        btn_sync.setStyleSheet(COMMON_STYLE)
        btn_sync.clicked.connect(self.save_local_zip)
        btn_layout.addWidget(btn_sync)
        
        layout.addLayout(btn_layout)

    def refresh_tree(self):
        self.table.setRowCount(0)
        for i, res in enumerate(self.batch_results):
            self.table.insertRow(i)
            status_text = "✅ 준비됨"
            if res["needs_review"]: status_text = "⚠️ 검수 필요"
            if res["status"] == "uploaded": status_text = "🚀 업로드 완료"
            elif res["status"] == "skipped": status_text = "⏭️ 건너뜀"
            elif res["status"] == "failed": status_text = "❌ 추출 실패"
            
            filename = os.path.basename(res["path"])
            s_name = res["data"].get("studentName", "알 수 없음")
            level = str(res["data"].get("currentLevel", "-"))
            
            self.table.setItem(i, 0, QTableWidgetItem(status_text))
            self.table.setItem(i, 1, QTableWidgetItem(filename))
            self.table.setItem(i, 2, QTableWidgetItem(s_name))
            self.table.setItem(i, 3, QTableWidgetItem(level))
            
            # center alignment
            for col in [0, 2, 3]:
                item = self.table.item(i, col)
                if item: item.setTextAlignment(Qt.AlignCenter)

    def upload_all(self):
        if not self.jwt_token:
            QMessageBox.warning(self, "권한 오류", "로그인이 필요합니다.")
            return
            
        ready_items = [res for res in self.batch_results if res["status"] == "pending" and not res.get("needs_review")]
        if not ready_items:
            QMessageBox.information(self, "알림", "업로드할 준비된 항목이 없습니다.\n(검수 필요 상태인 항목은 수정 후 업로드 가능합니다)")
            return
            
        reply = QMessageBox.question(self, "업로드 확인", f"총 {len(ready_items)}명의 데이터를 서버로 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
            
        self.progress_dialog = UploadProgressDialog(len(ready_items), self)
        self.progress_dialog.spinner.start()
        
        self.worker = UploadWorker(ready_items, self.jwt_token)
        self.worker.progress.connect(self.progress_dialog.update_progress)
        self.worker.finished_upload.connect(self.on_upload_finished)
        
        self.worker.start()
        self.progress_dialog.exec_()
        
    def on_upload_finished(self, success_count, fail_count):
        self.progress_dialog.spinner.stop()
        self.progress_dialog.accept()
        self.refresh_tree()
        QMessageBox.information(self, "업로드 완료", f"업로드 완료!\n성공: {success_count}건\n실패: {fail_count}건")

    def open_detail(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "선택 오류", "상세 검수할 항목을 선택하세요.")
            return
        self.parent_app.detail_view.set_overview(self)
        self.parent_app.detail_view.load_data(self.batch_results, row)
        self.parent_app.stacked_widget.setCurrentWidget(self.parent_app.detail_view)
        self.hide()
        self.parent_app.show()

    def save_local_zip(self):
        ready_count = sum(1 for res in self.batch_results if res["status"] not in ["uploaded", "skipped"])
        if ready_count == 0:
            QMessageBox.information(self, "알림", "저장할 준비된 항목이 없습니다.")
            return
            
        reply = QMessageBox.question(self, "압축 저장 확인", f"총 {ready_count}명의 데이터, 이미지 및 로그를 압축 저장하시겠습니까?\n(검수 필요 항목도 함께 저장됩니다)", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "TAR 저장", "extracted_data.tar", "TAR Files (*.tar)")
        if not path:
            return
            
        export_data = []
        image_paths = []
        for res in self.batch_results:
            if res["status"] in ["uploaded", "skipped"]:
                continue
            
            data_copy = res["data"].copy()
            data_copy["needs_review"] = res.get("needs_review", False)
            export_data.append(data_copy)
            
            image_paths.append(res["path"])
            res["status"] = "uploaded"
            
        try:
            import tarfile
            import io
            with tarfile.open(path, 'w') as tf:
                # JSON 저장
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                json_bytes = json_str.encode('utf-8')
                ti_json = tarfile.TarInfo(name="extracted_data.json")
                ti_json.size = len(json_bytes)
                tf.addfile(ti_json, io.BytesIO(json_bytes))
                
                # 이미지 저장
                for img_p in image_paths:
                    if os.path.exists(img_p):
                        tf.add(img_p, arcname=f"images/{os.path.basename(img_p)}")
                        
                # 로그 저장
                log_text = self.parent_app.log_area.toPlainText()
                log_bytes = log_text.encode('utf-8')
                ti_log = tarfile.TarInfo(name="session_log.txt")
                ti_log.size = len(log_bytes)
                tf.addfile(ti_log, io.BytesIO(log_bytes))
                
                extractor_log = os.path.join("logs", "extractor_debug.log")
                if os.path.exists(extractor_log):
                    tf.add(extractor_log, arcname="extractor_debug.log")
                    
            self.refresh_tree()
            QMessageBox.information(self, "완료", f"{path}에 성공적으로 TAR 압축 저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def closeEvent(self, event):
        self.parent_app.stacked_widget.setCurrentWidget(self.parent_app.dash_view)
        self.parent_app.show()
        event.accept()

class DetailWindow(GlassWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.batch_results = []
        self.current_idx = 0
        self.parent_app = parent_app
        self.current_overview = None
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Left side: Image
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setStyleSheet(f"background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 10px;")
        main_layout.addWidget(self.lbl_img, stretch=2)
        
        # Right side: Form
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background-color: {GLASS_BG}; border: 2px solid {COLOR_PINK}; border-radius: 10px;")
        right_layout = QVBoxLayout(right_panel)
        
        # Nav
        nav_layout = QHBoxLayout()
        self.lbl_title = QLabel("추출 결과 검수")
        self.lbl_title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLOR_PINK_HOVER}; border: none; background: transparent;")
        nav_layout.addWidget(self.lbl_title)
        right_layout.addLayout(nav_layout)
        
        btn_nav_layout = QHBoxLayout()
        btn_prev = QPushButton("◀ 이전")
        btn_prev.setStyleSheet(COMMON_STYLE)
        btn_prev.clicked.connect(self.on_prev)
        btn_nav_layout.addWidget(btn_prev)
        
        btn_next = QPushButton("다음 ▶")
        btn_next.setStyleSheet(COMMON_STYLE)
        btn_next.clicked.connect(self.on_next)
        btn_nav_layout.addWidget(btn_next)
        right_layout.addLayout(btn_nav_layout)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget#scrollAreaWidgetContents { background: transparent; }")
        
        scroll_widget = QWidget()
        scroll_widget.setObjectName("scrollAreaWidgetContents")
        self.form_layout = QFormLayout(scroll_widget)
        scroll.setWidget(scroll_widget)
        right_layout.addWidget(scroll)
        
        self.entries = {}
        
        def add_section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {COLOR_PINK_HOVER}; font-size: 16px; font-weight: bold; margin-top: 10px; border: none; background: transparent;")
            self.form_layout.addRow(lbl)
            
        def add_field(key, label):
            ent = QLineEdit()
            ent.setStyleSheet(f"background-color: rgba(255,255,255,150); border: 1px solid {COLOR_PINK}; border-radius: 5px; padding: 5px;")
            self.form_layout.addRow(label, ent)
            self.entries[key] = ent

        add_section("기본 정보")
        add_field("studentName", "학생 이름")
        add_field("currentLevel", "현재 레벨")
        add_field("currentStar", "성급")
        add_field("bondRank", "인연 랭크")
        
        add_section("스킬 레벨")
        add_field("skills.ex", "EX 스킬")
        add_field("skills.basic", "기본 스킬")
        add_field("skills.enh", "강화 스킬")
        add_field("skills.sub", "서브 스킬")
        
        add_section("고유 무기")
        add_field("weapon.level", "무기 레벨")
        add_field("weapon.star", "무기 성급")
        
        add_section("장비")
        add_field("equipment.slot1.tier", "슬롯1 티어")
        add_field("equipment.slot1.level", "슬롯1 레벨")
        add_field("equipment.slot2.tier", "슬롯2 티어")
        add_field("equipment.slot2.level", "슬롯2 레벨")
        add_field("equipment.slot3.tier", "슬롯3 티어")
        add_field("equipment.slot3.level", "슬롯3 레벨")
        add_field("equipment.slot4.tier", "애장품 티어")
        
        add_section("능력치")
        add_field("stats.maxHP", "최대 HP")
        add_field("stats.hpAbility", "HP 개방")
        add_field("stats.attackPower", "공격력")
        add_field("stats.atkAbility", "공격 개방")
        add_field("stats.defensePower", "방어력")
        add_field("stats.healPower", "치유력")
        add_field("stats.healAbility", "치유 개방")
        
        # Action Bar
        action_layout = QHBoxLayout()
        btn_back = QPushButton("◀ 이전 (요약으로)")
        btn_back.setStyleSheet("background-color: #6b7280; color: white; border-radius: 10px; padding: 10px; font-size: 15px;")
        btn_back.clicked.connect(self.on_cancel_detail)
        action_layout.addWidget(btn_back)

        btn_save = QPushButton("💾 저장 후 목록으로")
        btn_save.setStyleSheet(f"background-color: {COLOR_GREEN}; color: white; border-radius: 10px; padding: 10px; font-size: 15px;")
        btn_save.clicked.connect(self.on_save_close)
        action_layout.addWidget(btn_save)
        
        btn_skip = QPushButton("⏭️ 건너뛰기")
        btn_skip.setStyleSheet(f"background-color: {COLOR_RED}; color: white; border-radius: 10px; padding: 10px; font-size: 15px;")
        btn_skip.clicked.connect(self.on_skip)
        action_layout.addWidget(btn_skip)
        
        right_layout.addLayout(action_layout)
        main_layout.addWidget(right_panel, stretch=1)
        
    def load_data(self, batch_results, start_idx):
        self.batch_results = batch_results
        self.current_idx = start_idx
        if self.batch_results:
            self.load_current_index()
        
    def set_val(self, key, val):
        if val is not None:
            self.entries[key].setText(str(val))
        else:
            self.entries[key].setText("")
            
    def load_current_index(self):
        idx = self.current_idx
        res = self.batch_results[idx]
        self.lbl_title.setText(f"추출 결과 검수 ({idx+1}/{len(self.batch_results)})")
        
        pixmap = QPixmap(res['path'])
        if not pixmap.isNull():
            # Resize image to fit nicely within label
            self.lbl_img.setPixmap(pixmap)
            # Wait, better to scale it dynamically, but we can just set scaled contents
            self.lbl_img.setScaledContents(True)
            # But setScaledContents ignores aspect ratio. Let's handle it manually or just let it be since images are 1920x1080.
            # actually we can keep it simple:
            pixmap = pixmap.scaled(900, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_img.setPixmap(pixmap)
            self.lbl_img.setScaledContents(False)
            
        data = res["data"]
        self.set_val("studentName", data.get("studentName"))
        self.set_val("currentLevel", data.get("currentLevel"))
        self.set_val("currentStar", data.get("currentStar"))
        self.set_val("bondRank", data.get("bondRank"))
        
        sk = data.get("skills", {})
        self.set_val("skills.ex", sk.get("ex"))
        self.set_val("skills.basic", sk.get("basic"))
        self.set_val("skills.enh", sk.get("enh"))
        self.set_val("skills.sub", sk.get("sub"))
        
        wp = data.get("weapon", {})
        self.set_val("weapon.level", wp.get("level"))
        self.set_val("weapon.star", wp.get("star"))
        
        eq = data.get("equipment", {})
        self.set_val("equipment.slot1.tier", eq.get("slot1", {}).get("tier"))
        self.set_val("equipment.slot1.level", eq.get("slot1", {}).get("level"))
        self.set_val("equipment.slot2.tier", eq.get("slot2", {}).get("tier"))
        self.set_val("equipment.slot2.level", eq.get("slot2", {}).get("level"))
        self.set_val("equipment.slot3.tier", eq.get("slot3", {}).get("tier"))
        self.set_val("equipment.slot3.level", eq.get("slot3", {}).get("level"))
        self.set_val("equipment.slot4.tier", eq.get("slot4", {}).get("tier"))
        
        st = data.get("stats", {})
        self.set_val("stats.maxHP", st.get("maxHP"))
        self.set_val("stats.hpAbility", st.get("hpAbility"))
        self.set_val("stats.attackPower", st.get("attackPower"))
        self.set_val("stats.atkAbility", st.get("atkAbility"))
        self.set_val("stats.defensePower", st.get("defensePower"))
        self.set_val("stats.healPower", st.get("healPower"))
        self.set_val("stats.healAbility", st.get("healAbility"))

    def safe_int(self, key):
        val = self.entries[key].text().strip()
        if not val: return None
        try: return int(val)
        except: return val

    def save_current_index(self):
        res = self.batch_results[self.current_idx]
        
        edited_data = {
            "studentName": self.entries["studentName"].text().strip(),
            "bondRank": self.safe_int("bondRank"),
            "currentLevel": self.safe_int("currentLevel"),
            "currentStar": self.safe_int("currentStar"),
            "skills": {
                "ex": self.entries["skills.ex"].text().strip(),
                "basic": self.entries["skills.basic"].text().strip(),
                "enh": self.entries["skills.enh"].text().strip(),
                "sub": self.entries["skills.sub"].text().strip()
            },
            "weapon": {
                "level": self.safe_int("weapon.level"),
                "star": self.safe_int("weapon.star")
            },
            "equipment": {
                "slot1": { "tier": self.safe_int("equipment.slot1.tier"), "level": self.safe_int("equipment.slot1.level") },
                "slot2": { "tier": self.safe_int("equipment.slot2.tier"), "level": self.safe_int("equipment.slot2.level") },
                "slot3": { "tier": self.safe_int("equipment.slot3.tier"), "level": self.safe_int("equipment.slot3.level") },
                "slot4": { "tier": self.safe_int("equipment.slot4.tier") }
            },
            "stats": {
                "maxHP": self.safe_int("stats.maxHP"),
                "hpAbility": self.safe_int("stats.hpAbility"),
                "attackPower": self.safe_int("stats.attackPower"),
                "atkAbility": self.safe_int("stats.atkAbility"),
                "defensePower": self.safe_int("stats.defensePower"),
                "healPower": self.safe_int("stats.healPower"),
                "healAbility": self.safe_int("stats.healAbility")
            }
        }
        res["data"] = edited_data
        if edited_data["studentName"] and edited_data["currentLevel"] is not None:
            res["needs_review"] = False

    def on_prev(self):
        self.save_current_index()
        if self.batch_results:
            self.current_idx = (self.current_idx - 1) % len(self.batch_results)
            self.load_current_index()
        
    def on_next(self):
        self.save_current_index()
        if self.batch_results:
            self.current_idx = (self.current_idx + 1) % len(self.batch_results)
            self.load_current_index()
        
    def on_skip(self):
        res = self.batch_results[self.current_idx]
        res["status"] = "skipped"
        res["needs_review"] = False
        self.on_next()
        
    def set_overview(self, overview_win):
        self.current_overview = overview_win

    def on_save_close(self):
        self.save_current_index()
        if self.current_overview:
            self.current_overview.refresh_tree()
            self.parent_app.hide()
            self.current_overview.show()

    def on_cancel_detail(self):
        if self.current_overview:
            self.parent_app.hide()
            self.current_overview.show()

class ScannerDetailWindow(DetailWindow):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.jwt_token = parent_app.jwt_token
        self.single_result = None
        
        # Replace action buttons
        self.replace_action_buttons()
        
    def load_scanner_data(self, result):
        self.single_result = result
        self.jwt_token = self.parent_app.jwt_token
        # use DetailWindow's load_data with fake batch
        self.load_data([result], 0)
        
    def replace_action_buttons(self):
        # Find the action layout which is the last layout in right_layout
        right_panel = self.layout().itemAt(1).widget()
        right_layout = right_panel.layout()
        action_layout = right_layout.itemAt(right_layout.count() - 1).layout()
        
        # Clear old buttons
        while action_layout.count():
            item = action_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        # Add new buttons
        btn_upload = QPushButton("☁️ 바로 업로드")
        btn_upload.setStyleSheet(f"background-color: {COLOR_GREEN}; color: white; border-radius: 10px; padding: 10px; font-size: 15px;")
        btn_upload.clicked.connect(self.on_upload)
        action_layout.addWidget(btn_upload)
        
        btn_cancel = QPushButton("◀ 이전 (캡처 화면으로)")
        btn_cancel.setStyleSheet("background-color: #6b7280; color: white; border-radius: 10px; padding: 10px; font-size: 15px;")
        btn_cancel.clicked.connect(self.on_cancel)
        action_layout.addWidget(btn_cancel)
        
        # Also hide the nav buttons (prev/next)
        nav_btn_layout = right_layout.itemAt(1).layout()
        for i in range(nav_btn_layout.count()):
            w = nav_btn_layout.itemAt(i).widget()
            if w: w.hide()
            
    def on_upload(self):
        self.save_current_index()
        if not self.jwt_token:
            QMessageBox.warning(self, "권한 오류", "로그인이 필요합니다.")
            return
            
        res = self.single_result
        data = res["data"]
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        payload = {
            "studentName": data.get("studentName"),
            "bondRank": data.get("bondRank"),
            "currentLevel": data.get("currentLevel"),
            "currentStar": data.get("currentStar"),
            "skills": data.get("skills", {}),
            "equipment": data.get("equipment", {}),
            "weapon": data.get("weapon", {}),
            "stats": data.get("stats", {})
        }
        
        try:
            resp = requests.post(
                "https://api.planaai.kro.kr/api/import/screenshot",
                headers=headers,
                json=payload,
                timeout=5
            )
            if resp.status_code == 200:
                QMessageBox.information(self, "업로드 완료", "성공적으로 업로드되었습니다.")
                self.close_and_wait()
            else:
                QMessageBox.warning(self, "업로드 실패", resp.text)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 통신 오류: {e}")
            
    def on_cancel(self):
        self.close_and_wait()
        
    def close_and_wait(self):
        self.parent_app.stacked_widget.setCurrentWidget(self.parent_app.scanner_view)
        self.parent_app.start_scanner_listener()

if __name__ == "__main__":
    import ctypes
    try:
        myappid = 'plana.ai.screenshot.macro.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    
    from PyQt5.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#fdf2f8"))
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor("#fdf2f8"))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.black)
    palette.setColor(QPalette.Button, QColor("#fdf2f8"))
    palette.setColor(QPalette.ButtonText, Qt.black)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    app.setWindowIcon(QIcon(get_asset_path(r"assets\app_icon.ico")))
    app.setStyleSheet("""
        QMessageBox { background-color: #fdf2f8; }
        QMessageBox QLabel { color: black; font-size: 13px; }
        QMessageBox QPushButton { background-color: #f9a8d4; color: white; border: none; border-radius: 5px; padding: 5px 15px; font-size: 13px; }
        QMessageBox QPushButton:hover { background-color: #f472b6; }
    """)
    window = ExtractApp()
    window.show()
    sys.exit(app.exec_())
