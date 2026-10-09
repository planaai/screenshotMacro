import sys
import os
import json
import datetime
import shutil
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QComboBox, QSplitter, 
                             QTreeWidget, QTreeWidgetItem, QTabBar, QMessageBox, 
                             QFileDialog, QSpinBox, QGroupBox, QScrollArea, QFrame,
                             QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont

from core.coordinates import CoordinateService, Preset
from core.paths import get_user_data_dir
from .canvas import CoordinateCanvas
from .preset_dialog import PresetDialog

ITEM_DESCRIPTIONS = {
    # 1. 학생 정보 화면 (공통 / 실시간)
    "student_name": "[학생 정보] 학생 이름 텍스트 영역 (OCR 추출용)",
    "bond_rank": "[학생 정보] 인연 랭크 수치 영역 (OCR 추출용)",
    "student_level": "[학생 정보] 학생 레벨 수치 영역 (OCR 추출용)",
    "student_stars": "[학생 정보] 학생 성급(별) 아이콘 영역",
    "equipment_button_search": "[실시간 조작] 학생 정보 화면에서 [장비 성장] 버튼 위치를 탐색하는 영역",
    "equipment_button": "[실시간 조작] 학생 정보 화면에서 [장비 성장] 버튼을 클릭하는 좌표 (모달 열기)",
    "skill_ex": "[스킬/스탯] EX 스킬 아이콘 및 레벨 텍스트 영역",
    "skill_basic": "[스킬/스탯] 기본 스킬(1스) 영역",
    "skill_enh": "[스킬/스탯] 강화 스킬(2스) 영역",
    "skill_sub": "[스킬/스탯] 서브 스킬(3스) 영역",
    "weapon_level": "[스킬/스탯] 고유무기 레벨 텍스트 영역",
    "weapon_stars_area": "[스킬/스탯] 고유무기 한계돌파 성급 영역",
    "stat_hp": "[스킬/스탯] 최대체력 수치 텍스트 영역 (OCR 추출용)",
    "stat_attack": "[스킬/스탯] 공격력 수치 텍스트 영역 (OCR 추출용)",
    "stat_defense": "[스킬/스탯] 방어력 수치 텍스트 영역 (OCR 추출용)",
    "stat_heal": "[스킬/스탯] 치유력 수치 텍스트 영역 (OCR 추출용)",
    "macro_name_compare": "[매크로] 다음 학생 이동 검증용 이름 비교 영역",
    "next_student_button": "[매크로] 다음 학생 이동 버튼(>) 클릭 좌표",

    # 2. 단일 스캔 장비 (메인 화면 Fallback)
    "equip_1_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 메인 화면의 1번 장비(모자/장갑/신발) 슬롯 영역",
    "equip_2_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 메인 화면의 2번 장비(헤어핀/배지/부적) 슬롯 영역",
    "equip_3_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 메인 화면의 3번 장비(시계/목걸이) 슬롯 영역",
    "equip_4_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 메인 화면의 4번 애용품 슬롯 영역",
    "equip_1_tier_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 1번 장비의 티어(T1~T10) 텍스트 영역",
    "equip_2_tier_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 2번 장비의 티어(T1~T10) 텍스트 영역",
    "equip_3_tier_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 3번 장비의 티어(T1~T10) 텍스트 영역",
    "equip_4_tier_box": "[단일 스캔 전용] 정지 이미지 캡처본 분석 시 4번 애용품의 티어(T1~T2) 텍스트 영역",

    # 3. 장비 성장 창 (실시간 모달 고정밀)
    "equipment_menu_title": "[실시간 모달] 장비 성장 창 상단 타이틀 인식 영역 (창 오픈 확인용)",
    "detail_panel": "[실시간 모달] 장비 상세 정보 패널 영역",
    "detail_tier_badge": "[실시간 모달] 장비 성장 창의 대형 티어(T1~T10) 배지 고정밀 판독 영역",
    "detail_level": "[실시간 모달] 장비 성장 창의 장비 레벨(Lv.70) 판독 영역",
    "equipment_menu_close": "[실시간 모달] 장비 성장 창 닫기(X) 버튼 클릭 좌표",
    "slot_1": "[실시간 모달] 1번 장비 슬롯 선택 클릭 좌표",
    "slot_2": "[실시간 모달] 2번 장비 슬롯 선택 클릭 좌표",
    "slot_3": "[실시간 모달] 3번 장비 슬롯 선택 클릭 좌표",
    "main_slot_4": "[실시간 모달] 4번 애용품 슬롯 선택 클릭 좌표 (애용품 팝업 열기)",

    # 4. 애용품 정보 팝업
    "favorite_tier_badge": "[애용품 팝업] 애용품 T1/T2 배지 영역",
    "popup_detect_area": "[애용품 팝업] 애용품 팝업 오픈 감지 영역",
    "favorite_popup_close": "[애용품 팝업] 애용품 팝업 닫기(확인) 클릭 좌표",
}


def ensure_reference_images():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scenes_dir = os.path.join(base_dir, "guides", "scenes")
    os.makedirs(scenes_dir, exist_ok=True)
    mapping = {
        "student_info.png": "test_images/20260715015320_1.jpg",
        "equipment_modal.png": "test_images/20261003230305_1.jpg",
        "favorite_popup.png": "test_images/20261003230521_1.jpg"
    }
    for dest_name, src_rel in mapping.items():
        dest_path = os.path.join(scenes_dir, dest_name)
        if not os.path.exists(dest_path):
            src_path = os.path.join(base_dir, src_rel)
            if os.path.exists(src_path):
                try:
                    shutil.copyfile(src_path, dest_path)
                except Exception:
                    pass


class CoordinateEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.svc = CoordinateService.instance()
        self.setWindowTitle("좌표 설정 및 보정")
        self.resize(1600, 950)
        
        self.current_edits = {}
        self.current_selected_key = None
        self.is_updating_inputs = False
        self.scene_images = {}
        self.current_img_w = 1920
        self.current_img_h = 1080
        self.nudge_step = 1

        ensure_reference_images()
        self.init_ui()
        self.load_data()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.canvas.zoom_fit)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Top bar: Presets & actions
        top_bar = QFrame()
        top_bar.setStyleSheet("QFrame { background-color: #f7f9fa; border: 1px solid #dcdfe6; border-radius: 6px; padding: 4px; }")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        top_layout.setSpacing(10)

        lbl_preset = QLabel("<b>프리셋:</b>")
        lbl_preset.setStyleSheet("font-size: 13px;")
        top_layout.addWidget(lbl_preset)

        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_combo_changed)
        top_layout.addWidget(self.preset_combo)
        
        btn_save = QPushButton("➕ 새 프리셋으로 저장")
        btn_save.clicked.connect(self.save_as_new)
        top_layout.addWidget(btn_save)
        
        self.btn_overwrite = QPushButton("💾 덮어쓰기 저장")
        self.btn_overwrite.clicked.connect(self.save_overwrite)
        top_layout.addWidget(self.btn_overwrite)
        
        btn_apply = QPushButton("✔️ 활성 프리셋 적용")
        btn_apply.setStyleSheet("font-weight: bold; color: #2e7d32;")
        btn_apply.clicked.connect(self.apply_preset)
        top_layout.addWidget(btn_apply)
        
        top_layout.addStretch()
        main_layout.addWidget(top_bar)

        # 2. Main 3-Column Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter, 1)

        # Left Column: Item Tree
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl_tree = QLabel("<b>항목 목록</b>")
        left_layout.addWidget(lbl_tree)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["설정 항목"])
        self.tree.itemSelectionChanged.connect(self.on_tree_selection)
        self.tree.setStyleSheet("QTreeWidget { border: 1px solid #dcdfe6; border-radius: 6px; font-size: 12px; }")
        left_layout.addWidget(self.tree)
        self.splitter.addWidget(left_widget)

        # Center Column: Scene Tabs + Canvas Controls + Large Coordinate Canvas
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        # Scene TabBar (Native thin bar without expanding empty page)
        self.scene_bar = QTabBar()
        self.scene_bar.setShape(QTabBar.RoundedNorth)
        self.scene_bar.setDrawBase(False)
        self.scene_bar.currentChanged.connect(self.on_tab_changed)
        self.scene_bar.setStyleSheet("""
            QTabBar::tab {
                background: #e8ecf0;
                color: #333;
                padding: 7px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1976d2;
                color: white;
            }
        """)
        center_layout.addWidget(self.scene_bar)

        # Scene description banner
        self.scene_banner = QLabel()
        self.scene_banner.setStyleSheet("""
            QLabel {
                background: #eef3f8;
                border: 1px solid #cfdbe6;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                color: #2c3e50;
            }
        """)
        self.scene_banner.setWordWrap(True)
        center_layout.addWidget(self.scene_banner)

        # Canvas Sub-toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_load_img = QPushButton("📁 스크린샷 불러오기")
        btn_load_img.clicked.connect(self.load_image)
        toolbar.addWidget(btn_load_img)

        btn_zoom_fit = QPushButton("🔍 화면 맞춤")
        btn_zoom_fit.clicked.connect(lambda: self.canvas.zoom_fit())
        toolbar.addWidget(btn_zoom_fit)

        btn_zoom_100 = QPushButton("1:1")
        btn_zoom_100.clicked.connect(lambda: self.canvas.zoom_100())
        toolbar.addWidget(btn_zoom_100)

        btn_zoom_in = QPushButton("➕ 확대")
        btn_zoom_in.clicked.connect(lambda: self.canvas.zoom_in())
        toolbar.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("➖ 축소")
        btn_zoom_out.clicked.connect(lambda: self.canvas.zoom_out())
        toolbar.addWidget(btn_zoom_out)

        self.lbl_resolution = QLabel("해상도: 1920 × 1080")
        self.lbl_resolution.setStyleSheet("color: #666; font-size: 12px; margin-left: 8px;")
        toolbar.addWidget(self.lbl_resolution)

        toolbar.addStretch()
        lbl_hint = QLabel("💡 마우스 휠: 줌 | 드래그: 이동/크기 | 박스 클릭: 선택")
        lbl_hint.setStyleSheet("color: #777; font-size: 11px;")
        toolbar.addWidget(lbl_hint)

        center_layout.addLayout(toolbar)

        # Coordinate Canvas (Takes remaining vertical & horizontal space)
        self.canvas = CoordinateCanvas()
        self.canvas.signals.item_selected.connect(self.on_canvas_item_selected)
        self.canvas.signals.item_moved.connect(self.on_canvas_item_moved)
        center_layout.addWidget(self.canvas, 1)

        self.splitter.addWidget(center_widget)

        # Right Column: Coordinate Editor Panel & Guide
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 6, 6)
        right_layout.setSpacing(12)

        # 1) Item Info Card
        info_group = QGroupBox("선택 항목 정보")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #dcdfe6; border-radius: 6px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(4)

        self.lbl_item_name = QLabel("항목을 선택하세요")
        self.lbl_item_name.setStyleSheet("font-size: 15px; font-weight: bold; color: #1976d2;")
        info_layout.addWidget(self.lbl_item_name)

        self.lbl_item_key = QLabel("Key: -")
        self.lbl_item_key.setStyleSheet("font-size: 11px; color: #666;")
        info_layout.addWidget(self.lbl_item_key)

        self.lbl_item_meta = QLabel("장면: - | 그룹: -")
        self.lbl_item_meta.setStyleSheet("font-size: 11px; color: #777;")
        info_layout.addWidget(self.lbl_item_meta)

        self.lbl_item_type = QLabel("타입: -")
        self.lbl_item_type.setStyleSheet("font-size: 11px; font-weight: bold; color: #333;")
        info_layout.addWidget(self.lbl_item_type)

        right_layout.addWidget(info_group)

        # 2) Coordinate Value Editor Card
        self.coord_group = QGroupBox("좌표 직접 수정 (Pixel)")
        self.coord_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #dcdfe6; border-radius: 6px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        coord_layout = QVBoxLayout(self.coord_group)
        coord_layout.setSpacing(10)

        # Spinboxes Grid
        spin_grid = QGridLayout()
        spin_grid.setSpacing(8)

        # X
        lbl_x = QLabel("X (좌측 시작):")
        lbl_x.setStyleSheet("font-weight: bold;")
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 4000)
        self.spin_x.setSuffix(" px")
        self.spin_x.valueChanged.connect(self.on_spinbox_changed)
        spin_grid.addWidget(lbl_x, 0, 0)
        spin_grid.addWidget(self.spin_x, 0, 1)

        # Y
        lbl_y = QLabel("Y (상단 시작):")
        lbl_y.setStyleSheet("font-weight: bold;")
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 4000)
        self.spin_y.setSuffix(" px")
        self.spin_y.valueChanged.connect(self.on_spinbox_changed)
        spin_grid.addWidget(lbl_y, 0, 2)
        spin_grid.addWidget(self.spin_y, 0, 3)

        # W
        self.lbl_w = QLabel("W (너비):")
        self.lbl_w.setStyleSheet("font-weight: bold;")
        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 4000)
        self.spin_w.setSuffix(" px")
        self.spin_w.valueChanged.connect(self.on_spinbox_changed)
        spin_grid.addWidget(self.lbl_w, 1, 0)
        spin_grid.addWidget(self.spin_w, 1, 1)

        # H
        self.lbl_h = QLabel("H (높이):")
        self.lbl_h.setStyleSheet("font-weight: bold;")
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 4000)
        self.spin_h.setSuffix(" px")
        self.spin_h.valueChanged.connect(self.on_spinbox_changed)
        spin_grid.addWidget(self.lbl_h, 1, 2)
        spin_grid.addWidget(self.spin_h, 1, 3)

        coord_layout.addLayout(spin_grid)

        # Normalized values text
        self.lbl_norm_val = QLabel("정규화 좌표: [0.0000, 0.0000, 0.0000, 0.0000]")
        self.lbl_norm_val.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #555; background: #f0f2f5; padding: 4px; border-radius: 4px;")
        coord_layout.addWidget(self.lbl_norm_val)

        # Micro-adjustment controls (Nudge D-Pad)
        nudge_box = QGroupBox("정밀 미세 조정")
        nudge_box.setStyleSheet("QGroupBox { font-size: 11px; }")
        nudge_layout = QVBoxLayout(nudge_box)
        nudge_layout.setSpacing(6)

        # Step size radio
        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("조정 단위:"))
        self.btn_step_1 = QRadioButton("1px")
        self.btn_step_5 = QRadioButton("5px")
        self.btn_step_10 = QRadioButton("10px")
        self.btn_step_1.setChecked(True)
        
        step_group = QButtonGroup(self)
        step_group.addButton(self.btn_step_1, 1)
        step_group.addButton(self.btn_step_5, 5)
        step_group.addButton(self.btn_step_10, 10)
        step_group.buttonClicked[int].connect(self.on_step_changed)

        step_row.addWidget(self.btn_step_1)
        step_row.addWidget(self.btn_step_5)
        step_row.addWidget(self.btn_step_10)
        step_row.addStretch()
        nudge_layout.addLayout(step_row)

        # Position D-Pad
        dpad_layout = QGridLayout()
        dpad_layout.setSpacing(4)

        btn_up = QPushButton("▲")
        btn_up.setFixedWidth(50)
        btn_up.clicked.connect(lambda: self.nudge_position(0, -self.nudge_step))
        dpad_layout.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("◀")
        btn_left.setFixedWidth(50)
        btn_left.clicked.connect(lambda: self.nudge_position(-self.nudge_step, 0))
        dpad_layout.addWidget(btn_left, 1, 0)

        btn_down = QPushButton("▼")
        btn_down.setFixedWidth(50)
        btn_down.clicked.connect(lambda: self.nudge_position(0, self.nudge_step))
        dpad_layout.addWidget(btn_down, 1, 1)

        btn_right = QPushButton("▶")
        btn_right.setFixedWidth(50)
        btn_right.clicked.connect(lambda: self.nudge_position(self.nudge_step, 0))
        dpad_layout.addWidget(btn_right, 1, 2)

        nudge_layout.addLayout(dpad_layout)

        # Size Buttons
        self.size_btn_widget = QWidget()
        size_btn_layout = QHBoxLayout(self.size_btn_widget)
        size_btn_layout.setContentsMargins(0, 0, 0, 0)
        size_btn_layout.setSpacing(4)

        btn_w_minus = QPushButton("W -")
        btn_w_minus.clicked.connect(lambda: self.nudge_size(-self.nudge_step, 0))
        size_btn_layout.addWidget(btn_w_minus)

        btn_w_plus = QPushButton("W +")
        btn_w_plus.clicked.connect(lambda: self.nudge_size(self.nudge_step, 0))
        size_btn_layout.addWidget(btn_w_plus)

        btn_h_minus = QPushButton("H -")
        btn_h_minus.clicked.connect(lambda: self.nudge_size(0, -self.nudge_step))
        size_btn_layout.addWidget(btn_h_minus)

        btn_h_plus = QPushButton("H +")
        btn_h_plus.clicked.connect(lambda: self.nudge_size(0, self.nudge_step))
        size_btn_layout.addWidget(btn_h_plus)

        nudge_layout.addWidget(self.size_btn_widget)
        coord_layout.addWidget(nudge_box)

        # Reset button
        btn_reset_item = QPushButton("↺ 이 항목 기본값(default)으로 복원")
        btn_reset_item.clicked.connect(self.reset_current_item)
        coord_layout.addWidget(btn_reset_item)

        right_layout.addWidget(self.coord_group)

        # 3) Guide / Explanation Card
        guide_group = QGroupBox("가이드 및 설명")
        guide_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #dcdfe6; border-radius: 6px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        guide_layout = QVBoxLayout(guide_group)

        self.guide_text = QLabel("항목을 선택하면 해당 좌표의 용도와 상세 가이드가 표시됩니다.")
        self.guide_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.guide_text.setWordWrap(True)
        self.guide_text.setStyleSheet("font-size: 12px; color: #444; line-height: 140%;")
        guide_layout.addWidget(self.guide_text)

        right_layout.addWidget(guide_group)
        right_layout.addStretch()

        right_scroll.setWidget(right_widget)
        self.splitter.addWidget(right_scroll)

        # Splitter sizing: Left 250, Center 970 (stretched), Right 380
        self.splitter.setSizes([250, 970, 380])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)

    def on_step_changed(self, step):
        self.nudge_step = step

    def load_data(self):
        self.svc.load_schema()
        # Populate preset combo
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in self.svc.presets.keys():
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(self.svc.active_preset_name)
        self.preset_combo.blockSignals(False)
        
        # Build scene tabs
        self.scene_bar.blockSignals(True)
        while self.scene_bar.count() > 0:
            self.scene_bar.removeTab(0)
            
        scenes = self.svc.schema.get("scenes", {})
        for scene_id, scene_info in scenes.items():
            self.scene_bar.addTab(scene_info.get("label", scene_id))
        self.scene_bar.blockSignals(False)

        self.on_preset_combo_changed()

    def on_preset_combo_changed(self):
        name = self.preset_combo.currentText()
        if name:
            preset = self.svc.presets.get(name)
            if preset:
                self.current_edits = dict(preset.values)
                self.btn_overwrite.setEnabled(name != "default")
                self.on_tab_changed()

    def on_tab_changed(self):
        scene_id = self.get_current_scene_id()
        if not scene_id: return

        # Update scene banner
        desc = self.svc.schema.get("scenes", {}).get(scene_id, {}).get("description", "")
        if desc:
            self.scene_banner.setText(f"💡 <b>모드 안내:</b> {desc}")
            self.scene_banner.show()
        else:
            self.scene_banner.hide()
        
        # Update left tree
        self.update_tree_for_current_tab()
        
        # Load screenshot for this scene
        self.load_scene_screenshot(scene_id)
        
        # Select first item in tree
        if self.tree.topLevelItemCount() > 0:
            first_group = self.tree.topLevelItem(0)
            if first_group.childCount() > 0:
                self.tree.setCurrentItem(first_group.child(0))

    def get_current_scene_id(self):
        idx = self.scene_bar.currentIndex()
        if idx < 0: return None
        scenes = list(self.svc.schema.get("scenes", {}).keys())
        if idx < len(scenes):
            return scenes[idx]
        return None

    def update_tree_for_current_tab(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        scene_id = self.get_current_scene_id()
        if not scene_id: 
            self.tree.blockSignals(False)
            return
        
        groups = {}
        items = self.svc.schema.get("items", {})
        for key, info in items.items():
            if info.get("scene") == scene_id:
                if info.get("advanced", False):
                    gname = "고급 설정"
                else:
                    gname = info.get("group", "기본")
                
                if gname not in groups:
                    groups[gname] = []
                groups[gname].append((key, info))
                
        for gname, glist in groups.items():
            parent = QTreeWidgetItem(self.tree, [gname])
            parent.setExpanded(True)
            for key, info in glist:
                child = QTreeWidgetItem(parent, [info.get("label", key)])
                child.setData(0, Qt.UserRole, key)
                
        self.tree.blockSignals(False)

    def load_scene_screenshot(self, scene_id):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        img_path = None
        
        if scene_id in self.scene_images and os.path.exists(self.scene_images[scene_id]):
            img_path = self.scene_images[scene_id]
        else:
            scene_info = self.svc.schema.get("scenes", {}).get(scene_id, {})
            ref_rel = scene_info.get("reference_image")
            if ref_rel:
                candidate = os.path.join(base_dir, ref_rel)
                if os.path.exists(candidate):
                    img_path = candidate
                    
            if not img_path:
                fallbacks = {
                    "student_info": "test_images/20260715015320_1.jpg",
                    "single_scan_equip": "test_images/20260715015320_1.jpg",
                    "equipment_modal": "test_images/20261003230305_1.jpg",
                    "favorite_popup": "test_images/20261003230521_1.jpg"
                }
                fb_rel = fallbacks.get(scene_id)
                if fb_rel:
                    candidate = os.path.join(base_dir, fb_rel)
                    if os.path.exists(candidate):
                        img_path = candidate

        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            self.canvas.load_image(pixmap)
            self.current_img_w = pixmap.width()
            self.current_img_h = pixmap.height()
            self.lbl_resolution.setText(f"해상도: {self.current_img_w} × {self.current_img_h}")
        else:
            self.current_img_w = 1920
            self.current_img_h = 1080
            self.lbl_resolution.setText("해상도: 1920 × 1080 (기본)")

        # Populate canvas items for current scene
        self.populate_canvas_items(scene_id)

    def populate_canvas_items(self, scene_id):
        items = self.svc.schema.get("items", {})
        for key, info in items.items():
            if info.get("scene") == scene_id:
                typ = info.get("type", "region")
                val = self.current_edits.get(key)
                if not val:
                    val = self.svc.presets.get("default", Preset("default", {})).values.get(key)
                if val:
                    self.canvas.add_item(key, typ, val)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "이미지 열기", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            scene_id = self.get_current_scene_id()
            if scene_id:
                self.scene_images[scene_id] = path
            pixmap = QPixmap(path)
            self.canvas.load_image(pixmap)
            self.current_img_w = pixmap.width()
            self.current_img_h = pixmap.height()
            self.lbl_resolution.setText(f"해상도: {self.current_img_w} × {self.current_img_h}")
            
            if scene_id:
                self.populate_canvas_items(scene_id)
                if self.current_selected_key:
                    self.canvas.select_item(self.current_selected_key)

    def on_tree_selection(self):
        sel = self.tree.selectedItems()
        if sel:
            key = sel[0].data(0, Qt.UserRole)
            if key:
                self.current_selected_key = key
                self.canvas.select_item(key)
                self.update_detail_panel(key)

    def on_canvas_item_selected(self, key):
        self.current_selected_key = key
        # Select in tree without loop
        self.tree.blockSignals(True)
        found = False
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.data(0, Qt.UserRole) == key:
                    self.tree.setCurrentItem(child)
                    found = True
                    break
            if found: break
        self.tree.blockSignals(False)
        self.update_detail_panel(key)

    def on_canvas_item_moved(self, key, val):
        self.current_edits[key] = val
        if key == self.current_selected_key:
            self.update_spinboxes_from_val(val)

    def update_detail_panel(self, key):
        info = self.svc.schema.get("items", {}).get(key, {})
        val = self.current_edits.get(key)
        if not val:
            val = self.svc.presets.get("default", Preset("default", {})).values.get(key, [0, 0, 0, 0])

        typ = info.get("type", "region")
        is_region = (typ == "region")

        self.lbl_item_name.setText(info.get("label", key))
        self.lbl_item_key.setText(f"Key: {key}")
        scene_name = self.svc.schema.get("scenes", {}).get(info.get("scene", ""), {}).get("label", info.get("scene", ""))
        group_name = "고급 설정" if info.get("advanced") else info.get("group", "기본")
        self.lbl_item_meta.setText(f"장면: {scene_name} | 분류: {group_name}")
        self.lbl_item_type.setText(f"타입: {'영역 (Region)' if is_region else '클릭 좌표 (Point)'}")

        # Show/hide width and height for point
        self.lbl_w.setVisible(is_region)
        self.spin_w.setVisible(is_region)
        self.lbl_h.setVisible(is_region)
        self.spin_h.setVisible(is_region)
        self.size_btn_widget.setVisible(is_region)

        self.update_spinboxes_from_val(val)

        # Update guide text
        guide_rel = info.get("guide", "")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        guide_path = os.path.join(base_dir, guide_rel) if guide_rel else None

        desc = ITEM_DESCRIPTIONS.get(key, "이 항목의 좌표를 화면에 맞게 조절하세요.")
        text = f"<b>{desc}</b><br><br>"
        
        if guide_path and os.path.exists(guide_path):
            try:
                with open(guide_path, "r", encoding="utf-8") as f:
                    content = f.read()
                text += f"<div style='background:#f9f9f9; padding:8px; border:1px solid #eee; border-radius:4px;'>{content}</div>"
            except Exception:
                text += f"가이드 파일: <code>{guide_rel}</code>"
        else:
            text += f"가이드 경로: <code>{guide_rel}</code><br><br>"
            text += "💡 <b>조정 팁:</b> 드래그하거나 방향키(D-Pad)로 1px씩 정밀 조정할 수 있습니다."

        self.guide_text.setText(text)

    def update_spinboxes_from_val(self, val):
        self.is_updating_inputs = True
        img_w, img_h = self.current_img_w, self.current_img_h
        
        px_x = int(round(val[0] * img_w))
        px_y = int(round(val[1] * img_h))
        self.spin_x.setValue(px_x)
        self.spin_y.setValue(px_y)

        if len(val) >= 4:
            px_w = int(round(val[2] * img_w))
            px_h = int(round(val[3] * img_h))
            self.spin_w.setValue(px_w)
            self.spin_h.setValue(px_h)
            self.lbl_norm_val.setText(f"정규화: [{val[0]:.4f}, {val[1]:.4f}, {val[2]:.4f}, {val[3]:.4f}]")
        else:
            self.lbl_norm_val.setText(f"정규화: [{val[0]:.4f}, {val[1]:.4f}]")

        self.is_updating_inputs = False

    def on_spinbox_changed(self):
        if self.is_updating_inputs or not self.current_selected_key:
            return

        key = self.current_selected_key
        info = self.svc.schema.get("items", {}).get(key, {})
        typ = info.get("type", "region")

        img_w, img_h = self.current_img_w, self.current_img_h
        nx = round(self.spin_x.value() / img_w, 4)
        ny = round(self.spin_y.value() / img_h, 4)

        if typ == "region":
            nw = round(self.spin_w.value() / img_w, 4)
            nh = round(self.spin_h.value() / img_h, 4)
            val = [nx, ny, nw, nh]
            self.lbl_norm_val.setText(f"정규화: [{nx:.4f}, {ny:.4f}, {nw:.4f}, {nh:.4f}]")
        else:
            val = [nx, ny]
            self.lbl_norm_val.setText(f"정규화: [{nx:.4f}, {ny:.4f}]")

        self.current_edits[key] = val
        self.canvas.set_item_value(key, val)

    def nudge_position(self, dx, dy):
        if not self.current_selected_key: return
        self.spin_x.setValue(max(0, self.spin_x.value() + dx))
        self.spin_y.setValue(max(0, self.spin_y.value() + dy))

    def nudge_size(self, dw, dh):
        if not self.current_selected_key: return
        self.spin_w.setValue(max(1, self.spin_w.value() + dw))
        self.spin_h.setValue(max(1, self.spin_h.value() + dh))

    def reset_current_item(self):
        key = self.current_selected_key
        if not key: return
        default_val = self.svc.presets.get("default", Preset("default", {})).values.get(key)
        if default_val:
            self.current_edits[key] = list(default_val)
            self.canvas.set_item_value(key, list(default_val))
            self.update_spinboxes_from_val(default_val)

    def save_as_new(self):
        dialog = PresetDialog(self.svc, self)
        if dialog.exec_():
            name = dialog.saved_name
            
            diff = {}
            for k, v in self.current_edits.items():
                if self.svc.presets.get("default", Preset("default", {})).values.get(k) != v:
                    diff[k] = v
                    
            data = {
                "schema_version": 1,
                "name": name,
                "base": "default",
                "note": dialog.saved_note,
                "created_at": datetime.datetime.now().isoformat(),
                "values": diff
            }
            
            preset_dir = os.path.join(get_user_data_dir(), "presets")
            os.makedirs(preset_dir, exist_ok=True)
            path = os.path.join(preset_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            QMessageBox.information(self, "저장 완료", f"'{name}' 프리셋이 저장되었습니다.")
            self.svc.load_all_presets()
            self.load_data()
            self.preset_combo.setCurrentText(name)

    def save_overwrite(self):
        name = self.preset_combo.currentText()
        if name == "default":
            QMessageBox.warning(self, "경고", "default 프리셋은 덮어쓸 수 없습니다.")
            return
            
        preset = self.svc.presets.get(name)
        if not preset: return
        
        diff = {}
        for k, v in self.current_edits.items():
            if self.svc.presets.get("default", Preset("default", {})).values.get(k) != v:
                diff[k] = v
                
        preset_dir = os.path.join(get_user_data_dir(), "presets")
        os.makedirs(preset_dir, exist_ok=True)
        path = os.path.join(preset_dir, f"{name}.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data["values"] = diff
        data["updated_at"] = datetime.datetime.now().isoformat()
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        QMessageBox.information(self, "저장 완료", f"'{name}' 프리셋을 덮어썼습니다.")
        self.svc.load_all_presets()

    def apply_preset(self):
        name = self.preset_combo.currentText()
        if name:
            self.svc.set_active_preset(name)
            QMessageBox.information(self, "적용 완료", f"'{name}' 프리셋이 활성 프리셋으로 적용되었습니다.")
