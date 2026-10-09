from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QPointF, pyqtSignal, QObject
from PyQt5.QtGui import QPen, QColor, QPixmap, QBrush, QPainterPath, QPainterPathStroker, QPainter

class CanvasSignals(QObject):
    item_selected = pyqtSignal(str)
    item_moved = pyqtSignal(str, object)

class DraggablePoint(QGraphicsEllipseItem):
    def __init__(self, key, x, y, img_w, img_h, signals):
        r = 5
        super().__init__(-r, -r, 2*r, 2*r)
        self.key = key
        self.img_w = img_w
        self.img_h = img_h
        self.signals = signals
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
            if value:
                self.signals.item_selected.emit(self.key)
        elif change == QGraphicsRectItem.ItemPositionHasChanged:
            pos = value
            self.signals.item_moved.emit(self.key, [pos.x() / self.img_w, pos.y() / self.img_h])
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
            self._emit_change()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.current_handle = None
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget):
        if self.isSelected():
            self.setPen(QPen(QColor(0, 255, 0), 3))
            painter.fillRect(self.rect(), QColor(0, 255, 0, 40))
        else:
            self.setPen(QPen(QColor(255, 0, 0), 2))
            painter.fillRect(self.rect(), QColor(255, 0, 0, 40))
        super().paint(painter, option, widget)
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(self.rect().topLeft() + QPointF(5, 15), self.key)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedHasChanged:
            self.setZValue(1.0 if value else 0.0)
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
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        
        self.signals = CanvasSignals()
        self.img_item = None
        self.items_dict = {}

    def load_image(self, pixmap: QPixmap):
        self.scene.clear()
        self.items_dict.clear()
        self.img_item = self.scene.addPixmap(pixmap)
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def add_item(self, key: str, typ: str, val: list):
        if not self.img_item: return
        w, h = self.img_item.pixmap().width(), self.img_item.pixmap().height()
        
        if typ == "region":
            item = ResizableRect(key, val[0], val[1], val[2], val[3], w, h, self.signals)
        else:
            item = DraggablePoint(key, val[0], val[1], w, h, self.signals)
            
        self.scene.addItem(item)
        self.items_dict[key] = item

    def select_item(self, key: str):
        for k, item in self.items_dict.items():
            if k == key:
                item.setSelected(True)
                # Ensure it's visible
                self.ensureVisible(item)
            else:
                item.setSelected(False)

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)
