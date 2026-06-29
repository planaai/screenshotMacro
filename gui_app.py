import sys
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import threading
import extractor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QStackedWidget, QFileDialog, 
                             QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
                             QFormLayout, QMessageBox, QDialog, QAbstractItemView)
from PyQt5.QtGui import QFontDatabase, QFont, QPixmap, QPainter, QColor, QIcon, QResizeEvent
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
import sync_to_db
import macro

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

class Signals(QObject):
    log_msg = pyqtSignal(str)
    batch_done = pyqtSignal()
    macro_done = pyqtSignal(str)

class ExtractApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("plana.ai 스크린샷 매크로")
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

        self.central_widget = GlassWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        self.main_layout.addWidget(self.stacked_widget)
        
        self.init_login_view()
        self.init_dashboard_view()
        
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
            
        token, err = sync_to_db.login_to_backend(user, pwd)
        if token:
            self.jwt_token = token
            self.stacked_widget.setCurrentWidget(self.dash_view)
        else:
            QMessageBox.critical(self, "로그인 실패", f"로그인 실패: {err}")

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
        self.log_area.append(msg)

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
        btn_detail = QPushButton("🔍 선택 항목 상세 검수")
        btn_detail.setStyleSheet(COMMON_STYLE)
        btn_detail.clicked.connect(self.open_detail)
        btn_layout.addWidget(btn_detail)
        
        btn_layout.addStretch()
        
        btn_sync = QPushButton("⚡ 서버에 업로드")
        btn_sync.setStyleSheet(COMMON_STYLE)
        btn_sync.clicked.connect(self.upload_all)
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

    def open_detail(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "선택 오류", "상세 검수할 항목을 선택하세요.")
            return
        self.detail_window = DetailWindow(self.batch_results, row, self)
        self.detail_window.show()

    def upload_all(self):
        ready_count = sum(1 for res in self.batch_results if res["status"] not in ["uploaded", "skipped"] and not res["needs_review"])
        if ready_count == 0:
            QMessageBox.information(self, "알림", "동기화할 준비된 항목이 없습니다.")
            return
            
        reply = QMessageBox.question(self, "DB 동기화 확인", f"총 {ready_count}명의 학생 데이터를 웹 서버 DB에 동기화하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
            
        for res in self.batch_results:
            if res["status"] in ["uploaded", "skipped"] or res["needs_review"]:
                continue
            success, msg = sync_to_db.upload_to_backend(res["data"], self.jwt_token)
            if success:
                res["status"] = "uploaded"
            else:
                QMessageBox.critical(self, "오류", f"업로드 실패: {msg}")
        self.refresh_tree()
        QMessageBox.information(self, "완료", "동기화가 완료되었습니다.")

    def closeEvent(self, event):
        self.parent_app.show()
        event.accept()

class DetailWindow(QMainWindow):
    def __init__(self, batch_results, start_idx, parent_overview):
        super().__init__()
        self.batch_results = batch_results
        self.current_idx = start_idx
        self.parent_overview = parent_overview
        
        self.setWindowTitle("상세 검수 창")
        self.resize(1500, 900)
        
        self.central_widget = GlassWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
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
        
    def on_save_close(self):
        self.save_current_index()
        self.parent_overview.refresh_tree()
        self.close()

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
    app.setWindowIcon(QIcon(get_asset_path(r"assets\app_icon.ico")))
    window = ExtractApp()
    window.show()
    sys.exit(app.exec_())
