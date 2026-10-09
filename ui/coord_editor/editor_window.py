import sys
import os
import json
import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QSplitter, 
                             QTreeWidget, QTreeWidgetItem, QTabWidget, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from core.coordinates import CoordinateService, Preset
from core.paths import get_user_data_dir
from .canvas import CoordinateCanvas
from .preset_dialog import PresetDialog

class CoordinateEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.svc = CoordinateService.instance()
        self.setWindowTitle("좌표 설정")
        self.resize(1400, 900)
        
        self.current_edits = {}
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top bar
        top_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self.on_preset_combo_changed)
        top_layout.addWidget(QLabel("프리셋:"))
        top_layout.addWidget(self.preset_combo)
        
        btn_save = QPushButton("새 프리셋으로 저장")
        btn_save.clicked.connect(self.save_as_new)
        top_layout.addWidget(btn_save)
        
        self.btn_overwrite = QPushButton("덮어쓰기 저장")
        self.btn_overwrite.clicked.connect(self.save_overwrite)
        top_layout.addWidget(self.btn_overwrite)
        
        btn_apply = QPushButton("적용")
        btn_apply.clicked.connect(self.apply_preset)
        top_layout.addWidget(btn_apply)
        
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left: Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["항목"])
        self.tree.itemSelectionChanged.connect(self.on_tree_selection)
        splitter.addWidget(self.tree)

        # Middle: Canvas area with tabs
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        canvas_layout.addWidget(self.tabs)
        
        btn_load_img = QPushButton("스크린샷 불러오기")
        btn_load_img.clicked.connect(self.load_image)
        canvas_layout.addWidget(btn_load_img)
        
        self.canvas = CoordinateCanvas()
        self.canvas.signals.item_selected.connect(self.on_canvas_item_selected)
        self.canvas.signals.item_moved.connect(self.on_canvas_item_moved)
        canvas_layout.addWidget(self.canvas)
        
        splitter.addWidget(canvas_widget)

        # Right: Guide
        self.guide_label = QLabel("항목을 선택하면 가이드가 표시됩니다.")
        self.guide_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.guide_label.setWordWrap(True)
        splitter.addWidget(self.guide_label)
        
        splitter.setSizes([300, 800, 300])

    def load_data(self):
        # Populate preset combo
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in self.svc.presets.keys():
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(self.svc.active_preset_name)
        self.preset_combo.blockSignals(False)
        self.on_preset_combo_changed()
        
        # Build tabs
        self.tabs.clear()
        for scene_id, scene_info in self.svc.schema.get("scenes", {}).items():
            self.tabs.addTab(QWidget(), scene_info.get("label", scene_id))
            
    def on_preset_combo_changed(self):
        name = self.preset_combo.currentText()
        if name:
            preset = self.svc.presets.get(name)
            if preset:
                self.current_edits = dict(preset.values)
                self.btn_overwrite.setEnabled(name != "default")
                self.update_tree_for_current_tab()

    def on_tab_changed(self):
        self.update_tree_for_current_tab()
        
    def get_current_scene_id(self):
        idx = self.tabs.currentIndex()
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
                
        self.canvas.scene.clear()
        self.canvas.items_dict.clear()
        self.tree.blockSignals(False)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "이미지 열기", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            pixmap = QPixmap(path)
            self.canvas.load_image(pixmap)
            
            # Draw items for current scene
            scene_id = self.get_current_scene_id()
            if not scene_id: return
            
            items = self.svc.schema.get("items", {})
            for key, info in items.items():
                if info.get("scene") == scene_id:
                    typ = info.get("type", "region")
                    val = self.current_edits.get(key)
                    if not val:
                        val = self.svc.presets["default"].values.get(key)
                    if val:
                        self.canvas.add_item(key, typ, val)

    def on_tree_selection(self):
        sel = self.tree.selectedItems()
        if sel:
            key = sel[0].data(0, Qt.UserRole)
            if key:
                self.canvas.select_item(key)
                self.update_guide(key)

    def on_canvas_item_selected(self, key):
        pass

    def on_canvas_item_moved(self, key, val):
        self.current_edits[key] = val

    def update_guide(self, key):
        info = self.svc.schema.get("items", {}).get(key, {})
        text = f"**{info.get('label', key)}**\n\n타입: {info.get('type')}\n가이드 경로: {info.get('guide')}"
        self.guide_label.setText(text)

    def save_as_new(self):
        dialog = PresetDialog(self.svc, self)
        if dialog.exec_():
            name = dialog.saved_name
            
            diff = {}
            for k, v in self.current_edits.items():
                if self.svc.presets["default"].values.get(k) != v:
                    diff[k] = v
                    
            data = {
                "schema_version": 1,
                "name": name,
                "base": "default",
                "note": dialog.saved_note,
                "created_at": datetime.datetime.now().isoformat(),
                "values": diff
            }
            
            path = os.path.join(get_user_data_dir(), "presets", f"{name}.json")
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
            if self.svc.presets["default"].values.get(k) != v:
                diff[k] = v
                
        path = os.path.join(get_user_data_dir(), "presets", f"{name}.json")
        data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
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
            QMessageBox.information(self, "적용 완료", f"'{name}' 프리셋이 적용되었습니다.")
