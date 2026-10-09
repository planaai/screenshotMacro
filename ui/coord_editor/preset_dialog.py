from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox
from PyQt5.QtCore import Qt
import os
import json
from core.paths import get_user_data_dir

class PresetDialog(QDialog):
    def __init__(self, svc, parent=None):
        super().__init__(parent)
        self.svc = svc
        self.setWindowTitle("새 프리셋으로 저장")
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("프리셋 이름:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        
        layout.addWidget(QLabel("메모 (선택):"))
        self.note_edit = QLineEdit()
        layout.addWidget(self.note_edit)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("저장")
        self.btn_cancel = QPushButton("취소")
        
        self.btn_save.clicked.connect(self.save)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "경고", "이름을 입력하세요.")
            return
        if name == "default":
            QMessageBox.warning(self, "경고", "default는 예약된 이름입니다.")
            return
            
        self.saved_name = name
        self.saved_note = self.note_edit.text().strip()
        self.accept()
