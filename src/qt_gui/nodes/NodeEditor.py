import sys
import os

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

class NodeEditor(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor("#1d1d1d"))
        self._mouse_offset = QPointF()
        self._pressed_item = None
        self._selected_item_offsets = {}

    def mousePressEvent(self, event):
        self._pressed_item = self.itemAt(event.position().toPoint())

        # Store current selection before it gets changed
        original_selection = set(self.scene().selectedItems())

        super().mousePressEvent(event)

        # Restore multi-selection if dragging a selected item
        if self._pressed_item and isinstance(self._pressed_item, QGraphicsProxyWidget):
            if self._pressed_item in original_selection:
                for item in original_selection:
                    item.setSelected(True)
            else:
                self.scene().clearSelection()
                self._pressed_item.setSelected(True)
        else:
            self.scene().clearSelection()

        # Store the offset of each selected item to the mouse
        self._selected_item_offsets.clear()
        scene_pos = self.mapToScene(event.position().toPoint())
        for item in self.scene().selectedItems():
            self._selected_item_offsets[item] = item.pos() - scene_pos

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.LeftButton and
            self._pressed_item in self.scene().selectedItems()
        ):
            scene_pos = self.mapToScene(event.position().toPoint())
            for item, offset in self._selected_item_offsets.items():
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                    item.setPos(scene_pos + offset)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)


class Node(QGraphicsProxyWidget):
    def __init__(self, scene_ref, title="Node", pos=QPointF(0, 0), header_color: str ="#1d1d1d"):
        super().__init__()

        self.scene_ref = scene_ref
        self.title = title
        self.node_frame = QFrame()
        self.node_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.node_frame.setMinimumWidth(200)
        self.node_frame.setObjectName("NodeContainer")
        #self.node_frame.setStyleSheet("#NodeContainer {background-color: #2cde85;}")

        self.container_layout = QVBoxLayout(self.node_frame)
        self.container_layout.setContentsMargins(0, 0, 0, 0) # left top right bottom

        self.inner_frame = QFrame()
        self.inner_frame.setObjectName("InnerFrame")
        self.inner_frame.setStyleSheet("#InnerFrame { border: 2px solid black; border-radius: 5px; }")

        self.inner_frame_layout = QVBoxLayout()
        self.inner_frame_layout.setSpacing(0)
        self.inner_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_frame.setLayout(self.inner_frame_layout)
        
        self.node_header = QWidget()
        self.node_header.setStyleSheet(f"background-color: {header_color};")
        self.node_header_layout = QVBoxLayout()
        self.node_header_layout.setContentsMargins(10, 5, 10, 5)
        self.node_header.setLayout(self.node_header_layout)
        self.inner_frame_layout.addWidget(self.node_header)
        
        
        self.node_title = QLabel(self.title)
        self.node_header_layout.addWidget(self.node_title)
        
        self.node_body = QWidget()
        self.node_body.setStyleSheet("background-color: #303030;")
        self.node_body_layout = QVBoxLayout()
        self.node_body_layout.setContentsMargins(5, 10, 5, 10)
        self.node_body.setLayout(self.node_body_layout)
        self.inner_frame_layout.addWidget(self.node_body)

        self._populate_node_body_layout()

        self.container_layout.addWidget(self.inner_frame)

        self.setWidget(self.node_frame)
        self.setPos(pos)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)


    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                self.inner_frame.setStyleSheet("#InnerFrame { border: 2px solid white; border-radius: 5px; }")
                self.setZValue(1)  # bring to front
            else:
                self.inner_frame.setStyleSheet("#InnerFrame { border: 2px solid black; border-radius: 5px; }")
                self.setZValue(0)  # send to back
        return super().itemChange(change, value)
    
    
    def showEvent(self, event):
        print("showing Node", self.title)
        super().showEvent(event)
        self._position_circles()
        return 
    
    def moveEvent(self, event):
        #print("moving Node", self.title)
        super().moveEvent(event)
        self._position_circles()
        return
    
    
    def _position_circles(self):
        for i in range(self.node_body_layout.count()):
            item = self.node_body_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, (NodeOutput, NodeInput)):
                if hasattr(widget, "_update_circle_position"):
                    print("Positioning circles ->", widget.label)
                    widget._update_circle_position()
    
    
    def _populate_node_body_layout(self) -> None:
        self.node_body_layout.addWidget(NodeOutput("Output", "float", proxy_ref=self))
        
        self.node_body_layout.addWidget(NodeDropdown("Dropdown ", ["Option 1", "Option 2", "Option 3"]))
        self.node_body_layout.addWidget(NodeCheckBox("Checkbox!"))
        
        self.node_body_layout.addWidget(NodeInput("Input int", "int", proxy_ref=self))
        self.node_body_layout.addWidget(NodeInput("Input float", "float", proxy_ref=self))
        self.node_body_layout.addWidget(NodeInput("Input string", "string", proxy_ref=self))


class NodePort(QWidget):
    def __init__(self, port_type, label: str, data_type: str = None, proxy_ref: QGraphicsProxyWidget = None, parent=None):
        super().__init__(parent)

        self.port_type = port_type
        self.label = label
        self.data_type = data_type
        self.proxy = proxy_ref 
        self.port = None

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        self.label_widget = QLabel(label)
        
        self.input_field = None
        if port_type == "input":
            match data_type:
                case "int":
                    self.input_field = QSpinBox()
                    self.input_field.setStyleSheet("QSpinBox { background-color: #1d1d1d; color: white; }")
                    self.input_field.setMinimum(0)
                    self.input_field.setMaximum(9999)
                    self.input_field.setSingleStep(1)
                    self.input_field.setValue(0)
                    
                case "float":
                    self.input_field = QDoubleSpinBox()
                    self.input_field.setStyleSheet("QDoubleSpinBox { background-color: #1d1d1d; color: white; }")
                    self.input_field.setMinimum(0.0)
                    self.input_field.setMaximum(9999.0)
                    self.input_field.setSingleStep(0.1)
                    self.input_field.setValue(0.0)
                    
                case "string":
                    self.input_field = QLineEdit()
                    self.input_field.setStyleSheet("QLineEdit { background-color: #1d1d1d; color: white; }")
            
            layout.addWidget(self.label_widget, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.input_field)
        
        else:
            layout.addWidget(self.label_widget, alignment=Qt.AlignmentFlag.AlignRight)
        
        
        self.setLayout(layout)
    
    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_port()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_port_position()


    def _ensure_port(self):
        if self.port is not None:
            return

        self.port = Port(self.port_type, self.data_type)
        self.port.setParentItem(self.proxy)

        self._update_port_position()


    def _update_port_position(self):
        if not self.port or not self.proxy:
            return

        if self.port_type == "input":
            widget_pos = self.mapTo(self.proxy.widget(), self.rect().topLeft())
            x = widget_pos.x() - self.port.radius*2 # this is weird
        else:
            widget_pos = self.mapTo(self.proxy.widget(), self.rect().topRight())
            x = widget_pos.x()

        y = widget_pos.y() + self.height()/2 - self.port.radius
        self.port.setPos(QPointF(x, y))


class NodeInput(NodePort):
    def __init__(self, label: str, data_type: str = None, proxy_ref: QGraphicsProxyWidget = None, parent=None):
        super().__init__("input", label, data_type, proxy_ref, parent)


class NodeOutput(NodePort):
    def __init__(self, label: str, data_type: str = None, proxy_ref: QGraphicsProxyWidget = None, parent=None):
        super().__init__("output", label, data_type, proxy_ref, parent)


class NodeDropdown(QWidget):
    def __init__(self, label: str, items: list, parent=None):
        super().__init__(parent)

        self.label = label

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        self.label_widget = QLabel(label)
        layout.addWidget(self.label_widget)
        
        self.dropdown = QComboBox()
        self.dropdown.setStyleSheet("QComboBox { background-color: #303030; color: white; }")
        layout.addWidget(self.dropdown)
        
        self.dropdown.addItems(items)

        self.setLayout(layout)
        

class NodeCheckBox(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)

        self.checked = False

        self.box = QLabel(" ")  # initially empty
        self.box.setFixedSize(16, 16)
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.setStyleSheet("background-color: #656565; color: white;")

        self.label_widget = QLabel(label)
        self.label_widget.setStyleSheet("color: white;")

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        layout.addWidget(self.box)
        layout.addWidget(self.label_widget)

        self.setLayout(layout)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = self.toggle

    def toggle(self, event):
        self.checked = not self.checked
        self.box.setText("✓" if self.checked else " ")
        self.box.setStyleSheet("background-color: #4772b3; color: white;"if self.checked else "background-color: #656565; color: white;")


class Port(QGraphicsEllipseItem):
    def __init__(self, port_type, data_type, parent=None):
        self.radius = 6
        self.port_type = port_type
        self.data_type = data_type
        self.color = PORT_COLOR_MAP[self.data_type]
        
        super().__init__(0, 0, self.radius * 2, self.radius * 2, parent)
        
        self.setBrush(QBrush(QColor(self.color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setZValue(2)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self.dragging = False
        self.temp_wire = None

    def hoverEnterEvent(self, event):
        #self.setBrush(QColor("#ff6e40"))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        #self.setBrush(QColor(self.color))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.start_drag(event.scenePos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging and self.temp_wire:
            center = self.scenePos() + QPointF(self.radius, self.radius)
            path = self._create_bezier_path(center, event.scenePos())
            self.temp_wire.setPath(path)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.finish_drag(event.scenePos())
        super().mouseReleaseEvent(event)


    def start_drag(self, start_pos):
        self.dragging = True
        center = self.scenePos() + QPointF(self.radius, self.radius)
        path = self._create_bezier_path(center, start_pos)
        self.temp_wire = QGraphicsPathItem(path)
        self.temp_wire.setPen(QPen(QColor(self.color), 2))
        self.temp_wire.setZValue(1)
        self.scene().addItem(self.temp_wire)


    def finish_drag(self, end_pos):
        self.dragging = False
        if self.temp_wire:
            self.scene().removeItem(self.temp_wire)
            self.temp_wire = None

        # Collision detection: find input port under cursor
        items = self.scene().items(end_pos)
        for item in items:
            if isinstance(item, Port) and item.port_type == "input":
                print("Connected to input port!")
                self.create_wire_to(item)
                break
            
            
    def _create_bezier_path(self, p1: QPointF, p2: QPointF) -> QPainterPath:
        path = QPainterPath(p1)
        dx = abs(p2.x() - p1.x()) * 0.5

        if self.port_type == "output":
            ctrl1 = QPointF(p1.x() + dx, p1.y())
            ctrl2 = QPointF(p2.x() - dx, p2.y())
        else:  # input
            ctrl1 = QPointF(p1.x() - dx, p1.y())
            ctrl2 = QPointF(p2.x() + dx, p2.y())

        path.cubicTo(ctrl1, ctrl2, p2)
        return path

    def create_wire_to(self, target_port):
        p1 = self.scenePos() + QPointF(self.radius, self.radius)
        p2 = target_port.scenePos() + QPointF(target_port.radius, target_port.radius)

        path = self._create_bezier_path(p1, p2)
        wire = QGraphicsPathItem(path)
        wire.setPen(QPen(QColor(self.color), 2))
        wire.setZValue(1)
        self.scene().addItem(wire)


PORT_COLOR_MAP = {
    "boolean": "#cca6d6",
    "int": "#598c5c",
    "float": "#a1a1a1",
    "string": "#70b2ff",
}

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

    app: QApplication = QApplication(sys.argv)
    app.setStyle("fusion")

    scene = QGraphicsScene()
    view = NodeEditor(scene)
    view.setWindowTitle("Node Editor")
    view.setMinimumSize(1500, 1000)

    # Create and embed widgets
    node1 = Node(scene, "Add", QPointF(100, 100), "#9c343e")
    node2 = Node(scene, "Multiply", QPointF(300, 200), "#079371")

    scene.addItem(node1)
    scene.addItem(node2)

    view.show()
    sys.exit(app.exec())