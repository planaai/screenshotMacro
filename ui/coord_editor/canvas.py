from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QObject
from PyQt5.QtGui import QPen, QColor, QPixmap, QBrush, QPainterPath, QPainterPathStroker, QPainter, QFont

class CanvasSignals(QObject):
    item_selected = pyqtSignal(str)
    item_moved = pyqtSignal(str, object)

class DraggablePoint(QGraphicsEllipseItem):
    def __init__(self, key, x, y, img_w, img_h, signals):
        r = 6
        super().__init__(-r, -r, 2*r, 2*r)
        self.key = key
        self.img_w = img_w
        self.img_h = img_h
        self.signals = signals
        self.setPos(x * img_w, y * img_h)
        self.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

    def update_geometry(self, x, y):
        self.setPos(x * self.img_w, y * self.img_h)
        self.update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.signals.item_selected.emit(self.key)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 255, 128), 3))
            painter.setBrush(QBrush(QColor(0, 255, 128, 220)))
        else:
            painter.setPen(QPen(QColor(0, 140, 255), 2))
            painter.setBrush(QBrush(QColor(0, 140, 255, 180)))
        painter.drawEllipse(self.rect())

        # Badge
        font = QFont("Malgun Gothic", 9, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        txt = self.key
        txt_w = (metrics.horizontalAdvance(txt) if hasattr(metrics, 'horizontalAdvance') else metrics.width(txt)) + 8
        txt_h = 18
        badge_rect = QRectF(10, -9, txt_w, txt_h)
        painter.setBrush(QBrush(QColor(20, 20, 20, 210)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 3, 3)

        painter.setPen(QColor(0, 255, 128) if self.isSelected() else QColor(255, 255, 255))
        painter.drawText(badge_rect, Qt.AlignCenter, txt)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedHasChanged:
            self.setZValue(10.0 if value else 1.0)
            if value:
                self.signals.item_selected.emit(self.key)
        elif change == QGraphicsRectItem.ItemPositionHasChanged:
            pos = value
            self.signals.item_moved.emit(self.key, [
                round(pos.x() / self.img_w, 4),
                round(pos.y() / self.img_h, 4)
            ])
        return super().itemChange(change, value)


class ResizableRect(QGraphicsRectItem):
    def __init__(self, key, x, y, w, h, img_w, img_h, signals):
        super().__init__(0, 0, w * img_w, h * img_h)
        self.setPos(x * img_w, y * img_h)
        self.key = key
        self.img_w = img_w
        self.img_h = img_h
        self.signals = signals
        self.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable | QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.handle_size = 10
        self.current_handle = None

    def update_geometry(self, x, y, w, h):
        self.setPos(x * self.img_w, y * self.img_h)
        self.setRect(0, 0, max(4, w * self.img_w), max(4, h * self.img_h))
        self.update()

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
        self.signals.item_selected.emit(self.key)

    def mouseMoveEvent(self, event):
        if self.current_handle is not None:
            pos = event.pos()
            rect = self.rect()
            if self.current_handle == 'br':
                rect.setWidth(max(4, pos.x() - rect.left()))
                rect.setHeight(max(4, pos.y() - rect.top()))
            elif self.current_handle == 'r':
                rect.setWidth(max(4, pos.x() - rect.left()))
            elif self.current_handle == 'b':
                rect.setHeight(max(4, pos.y() - rect.top()))
            self.setRect(rect)
            self._emit_change()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.current_handle = None
        super().mouseReleaseEvent(event)
        self._emit_change()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 255, 128), 3))
            painter.fillRect(rect, QColor(0, 255, 128, 45))
        else:
            painter.setPen(QPen(QColor(255, 60, 60), 2))
            painter.fillRect(rect, QColor(255, 60, 60, 30))
        painter.drawRect(rect)

        # Label badge
        font = QFont("Malgun Gothic", 9, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        txt = self.key
        txt_w = (metrics.horizontalAdvance(txt) if hasattr(metrics, 'horizontalAdvance') else metrics.width(txt)) + 8
        txt_h = 18
        badge_y = rect.top() - txt_h if rect.top() >= txt_h else rect.top()
        badge_rect = QRectF(rect.left(), badge_y, txt_w, txt_h)
        painter.setBrush(QBrush(QColor(20, 20, 20, 210)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 3, 3)

        painter.setPen(QColor(0, 255, 128) if self.isSelected() else QColor(255, 255, 255))
        painter.drawText(badge_rect, Qt.AlignCenter, txt)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedHasChanged:
            self.setZValue(10.0 if value else 1.0)
            if value:
                self.signals.item_selected.emit(self.key)
        elif change == QGraphicsRectItem.ItemPositionHasChanged:
            self._emit_change(value)
        return super().itemChange(change, value)

    def _emit_change(self, pos=None):
        if pos is None: pos = self.pos()
        rect = self.rect()
        val = [
            round(pos.x() / self.img_w, 4),
            round(pos.y() / self.img_h, 4),
            round(rect.width() / self.img_w, 4),
            round(rect.height() / self.img_h, 4)
        ]
        self.signals.item_moved.emit(self.key, val)


class CoordinateCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setStyleSheet("background-color: #1e1e24; border: 1px solid #444;")
        
        self.signals = CanvasSignals()
        self.img_item = None
        self.items_dict = {}

    def load_image(self, pixmap: QPixmap):
        self.scene.clear()
        self.items_dict.clear()
        self.img_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.zoom_fit()

    def add_item(self, key: str, typ: str, val: list):
        if not self.img_item: return
        w, h = self.img_item.pixmap().width(), self.img_item.pixmap().height()
        
        if typ == "region":
            item = ResizableRect(key, val[0], val[1], val[2], val[3], w, h, self.signals)
        else:
            item = DraggablePoint(key, val[0], val[1], w, h, self.signals)
            
        self.scene.addItem(item)
        self.items_dict[key] = item

    def set_item_value(self, key: str, val: list):
        if key not in self.items_dict or not self.img_item:
            return
        item = self.items_dict[key]
        if isinstance(item, ResizableRect) and len(val) >= 4:
            item.update_geometry(val[0], val[1], val[2], val[3])
        elif isinstance(item, DraggablePoint) and len(val) >= 2:
            item.update_geometry(val[0], val[1])

    def select_item(self, key: str):
        selected_obj = None
        for k, item in self.items_dict.items():
            if k == key:
                item.setSelected(True)
                item.setZValue(10.0)
                selected_obj = item
            else:
                item.setSelected(False)
                item.setZValue(1.0)
        if selected_obj:
            self.ensureVisible(selected_obj, 50, 50)

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(1 / 1.2, 1 / 1.2)

    def zoom_fit(self):
        if self.img_item:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def zoom_100(self):
        self.resetTransform()

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)
