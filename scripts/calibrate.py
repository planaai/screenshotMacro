import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QGraphicsRectItem, QGraphicsEllipseItem, QVBoxLayout, QHBoxLayout, QWidget, 
                             QPushButton, QListWidget, QFileDialog, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPixmap, QPainter, QBrush, QPainterPath, QPainterPathStroker

class DraggablePoint(QGraphicsEllipseItem):
    def __init__(self, key, x, y, img_w, img_h):
        r = 5
        super().__init__(-r, -r, 2*r, 2*r)
        self.key = key
        self.setPos(x * img_w, y * img_h)
        self.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor(0, 0, 255), 2))
        self.setBrush(QBrush(QColor(0, 0, 255, 128)))

    def paint(self, painter, option, widget):
        if self.isSelected():
            self.setPen(QPen(QColor(0, 255, 0), 3))
            self.setBrush(QBrush(QColor(0, 255, 0, 128)))
        else:
            self.setPen(QPen(QColor(0, 0, 255), 2))
            self.setBrush(QBrush(QColor(0, 0, 255, 128)))
        super().paint(painter, option, widget)
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(QPointF(10, 10), self.key)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedHasChanged:
            self.setZValue(1.0 if value else 0.0)
        return super().itemChange(change, value)

class ResizableRect(QGraphicsRectItem):
    def __init__(self, key, x, y, w, h, img_w, img_h):
        super().__init__(x * img_w, y * img_h, w * img_w, h * img_h)
        self.key = key
        self.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor(255, 0, 0), 2))
        self.handle_size = 10
        self.current_handle = None

    def hoverMoveEvent(self, event):
        pos = event.pos()
        rect = self.rect()
        if self._is_on_edge(pos, rect.bottomRight()):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._is_on_right_edge(pos, rect):
            self.setCursor(Qt.SizeHorCursor)
        elif self._is_on_bottom_edge(pos, rect):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def _is_on_edge(self, pos, corner):
        return (pos.x() - corner.x())**2 + (pos.y() - corner.y())**2 < self.handle_size**2
        
    def _is_on_right_edge(self, pos, rect):
        return abs(pos.x() - rect.right()) < self.handle_size and rect.top() < pos.y() < rect.bottom()

    def _is_on_bottom_edge(self, pos, rect):
        return abs(pos.y() - rect.bottom()) < self.handle_size and rect.left() < pos.x() < rect.right()

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect())
        stroker = QPainterPathStroker()
        stroker.setWidth(max(10, self.handle_size))
        return stroker.createStroke(path)

    def mousePressEvent(self, event):
        pos = event.pos()
        rect = self.rect()
        if self._is_on_edge(pos, rect.bottomRight()):
            self.current_handle = 'br'
        elif self._is_on_right_edge(pos, rect):
            self.current_handle = 'r'
        elif self._is_on_bottom_edge(pos, rect):
            self.current_handle = 'b'
        else:
            self.current_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_handle is not None:
            pos = event.pos()
            rect = self.rect()
            if self.current_handle == 'br':
                rect.setBottomRight(pos)
            elif self.current_handle == 'r':
                rect.setRight(pos.x())
            elif self.current_handle == 'b':
                rect.setBottom(pos.y())
            self.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.current_handle = None
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget):
        if self.isSelected():
            self.setPen(QPen(QColor(0, 255, 0), 3))
        else:
            self.setPen(QPen(QColor(255, 0, 0), 2))
        super().paint(painter, option, widget)
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(self.rect().topLeft() + QPointF(5, 15), self.key)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedHasChanged:
            self.setZValue(1.0 if value else 0.0)
        return super().itemChange(change, value)


class CalibrationTool(QMainWindow):
    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.setWindowTitle("Interactive Calibration Tool")
        self.setGeometry(100, 100, 1400, 900)
        
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(250)
        self.list_widget.currentRowChanged.connect(self.on_list_selected)
        
        btn_load = QPushButton("Load Image")
        btn_load.clicked.connect(self.load_image)
        btn_save = QPushButton("Save (S)")
        btn_save.clicked.connect(self.save_config)
        
        vbox = QVBoxLayout()
        vbox.addWidget(btn_load)
        vbox.addWidget(self.list_widget)
        vbox.addWidget(btn_save)
        
        right_panel = QWidget()
        right_panel.setLayout(vbox)
        
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.view)
        main_layout.addWidget(right_panel)
        
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        self.img_item = None
        self.rect_items = {}
        
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.config = {}
            
    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Test Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            pixmap = QPixmap(path)
            self.scene.clear()
            self.rect_items.clear()
            self.list_widget.clear()
            
            self.img_item = self.scene.addPixmap(pixmap)
            w, h = pixmap.width(), pixmap.height()
            
            regions = self.config.get("regions", {})
            for key, val in regions.items():
                if isinstance(val, dict):
                    x, y, rw, rh = val['x'], val['y'], val['w'], val['h']
                else:
                    x, y, rw, rh = val
                rect = ResizableRect(key, x, y, rw, rh, w, h)
                self.scene.addItem(rect)
                self.rect_items[key] = rect
                self.list_widget.addItem(key)
                
            points = self.config.get("points", {})
            for key, val in points.items():
                px, py = val[0], val[1]
                pt = DraggablePoint(key, px, py, w, h)
                self.scene.addItem(pt)
                self.rect_items[key] = pt
                self.list_widget.addItem(key)

    def on_list_selected(self, idx):
        if idx < 0: return
        key = self.list_widget.item(idx).text()
        for k, r in self.rect_items.items():
            is_selected = (k == key)
            r.setSelected(is_selected)
            r.setZValue(1.0 if is_selected else 0.0)

    def save_config(self):
        if not self.img_item:
            return
        w, h = self.img_item.pixmap().width(), self.img_item.pixmap().height()
        regions = self.config.get("regions", {})
        points = self.config.get("points", {})
        
        for key, item in self.rect_items.items():
            if isinstance(item, ResizableRect):
                scene_rect = item.sceneBoundingRect()
                if key in regions and isinstance(regions[key], list):
                    regions[key] = [
                        round(scene_rect.x() / w, 3),
                        round(scene_rect.y() / h, 3),
                        round(scene_rect.width() / w, 3),
                        round(scene_rect.height() / h, 3)
                    ]
                else:
                    regions[key] = {
                        "x": round(scene_rect.x() / w, 3),
                        "y": round(scene_rect.y() / h, 3),
                        "w": round(scene_rect.width() / w, 3),
                        "h": round(scene_rect.height() / h, 3)
                    }
            elif isinstance(item, DraggablePoint):
                pos = item.pos()
                points[key] = [round(pos.x() / w, 3), round(pos.y() / h, 3)]
            
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
            
        QMessageBox.information(self, "Saved", "Coordinates saved successfully!")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S:
            self.save_config()
            return
            
        selected = self.scene.selectedItems()
        if not selected:
            return super().keyPressEvent(event)
            
        item = selected[0]
        step = 1
        if event.key() == Qt.Key_Up:
            item.moveBy(0, -step)
        elif event.key() == Qt.Key_Down:
            item.moveBy(0, step)
        elif event.key() == Qt.Key_Left:
            item.moveBy(-step, 0)
        elif event.key() == Qt.Key_Right:
            item.moveBy(step, 0)
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "coordinates.json")
    window = CalibrationTool(config_file)
    window.show()
    sys.exit(app.exec_())
