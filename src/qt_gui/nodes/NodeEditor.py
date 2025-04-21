import sys
import os
import numpy as np

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *



class Graph:
    def __init__(self):
        self.nodes = []
        self.connections = []

    def add_node(self, node):
        self.nodes.append(node)

    def connect(self, output_port, input_port):
        self.connections.append((output_port, input_port))
        input_port.connected_port = output_port

    def evaluate(self, node, cache=None):
        if cache is None:
            cache = {}

        if node in cache:
            return cache[node]

        result = node.compute(self, cache)
        cache[node] = result
        return result


class NodeEditor(QGraphicsView):
    def __init__(self, scene, background_color="#1d1d1d"):
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor(background_color))
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._mouse_offset = QPointF()
        self._pressed_item = None
        self._selected_item_offsets = {}
        
        self._is_panning = False
        self._pan_start = QPoint()
        
        self._zoom = 0
        self._zoom_step = 0.1
        self._zoom_range = (0.1, 2.0)  # min and max zoom scale
        
    
    def wheelEvent(self, event):
        modifiers = event.modifiers()
        delta = event.angleDelta().y()

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
            return

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta)
            return

        # 1. Get position before zoom (in scene coords)
        old_pos = self.mapToScene(event.position().toPoint())

        # 2. Zoom
        factor = 1.0 + self._zoom_step if delta > 0 else 1.0 - self._zoom_step
        new_scale = self.transform().m11() * factor

        if self._zoom_range[0] <= new_scale <= self._zoom_range[1]:
            self.scale(factor, factor)
            self._zoom += (1 if delta > 0 else -1)

        # 3. Get position after zoom (new scene coords under mouse)
        new_pos = self.mapToScene(event.position().toPoint())

        # 4. Calculate how much the scene moved under the cursor
        delta_scene = new_pos - old_pos

        # 5. Move the scrollbars to keep the scene fixed under cursor
        self.translate(delta_scene.x(), delta_scene.y())
    
    
    def reset_zoom(self):
        self.resetTransform()
        self._zoom = 0
    
    

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self._pan_start = event.position().toPoint()
            event.accept()
            return

        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pressed_item = self.itemAt(event.position().toPoint())
        original_selection = set(self.scene().selectedItems())
        super().mousePressEvent(event)

        if isinstance(self._pressed_item, Node):
            if self._pressed_item in original_selection:
                for item in original_selection:
                    item.setSelected(True)
            else:
                self.scene().clearSelection()
                self._pressed_item.setSelected(True)
        else:
            self.scene().clearSelection()

        self._selected_item_offsets.clear()
        scene_pos = self.mapToScene(event.position().toPoint())
        for item in self.scene().selectedItems():
            if isinstance(item, Node):
                self._selected_item_offsets[item] = item.pos() - scene_pos

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        self.setCursor(Qt.CursorShape.ArrowCursor)

        if (
            event.buttons() & Qt.MouseButton.LeftButton and
            self._pressed_item in self.scene().selectedItems()
        ):
            scene_pos = self.mapToScene(event.position().toPoint())
            for item, offset in self._selected_item_offsets.items():
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                    item.setPos(scene_pos + offset)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)


class Node(QGraphicsProxyWidget):
    def __init__(self, scene_ref, title="Node", pos=QPointF(0, 0), node_structure: dict=None, header_color: str ="#121212"):
        super().__init__()

        self.scene_ref = scene_ref
        self.title = title
        self.node_structure = node_structure
        
        self.outputs = {}
        self.parameters = {}
        self.inputs = {}
        
        
        
        self.node_frame = QFrame()
        self.node_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.node_frame.setMinimumWidth(200)
        self.node_frame.setObjectName("NodeContainer")
        

        self.container_layout = QVBoxLayout(self.node_frame)
        self.container_layout.setContentsMargins(0, 0, 0, 0) # left top right bottom

        self.inner_frame = QFrame()
        self.inner_frame.setObjectName("NodeInnerFrame")

        self.inner_frame_layout = QVBoxLayout()
        self.inner_frame_layout.setSpacing(0)
        self.inner_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_frame.setLayout(self.inner_frame_layout)
        
        self.node_header = QWidget()
        palette = self.node_header.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(header_color))
        self.node_header.setAutoFillBackground(True)
        self.node_header.setPalette(palette)
        self.node_header_layout = QVBoxLayout()
        self.node_header_layout.setContentsMargins(10, 5, 10, 5)
        self.node_header.setLayout(self.node_header_layout)
        self.inner_frame_layout.addWidget(self.node_header)
        
        
        self.node_title = QLabel(self.title)
        self.node_header_layout.addWidget(self.node_title)
        
        self.node_body = QWidget()
        self.node_body.setObjectName("NodeBody")
        self.node_body_layout = QVBoxLayout()
        self.node_body_layout.setContentsMargins(5, 10, 5, 10)
        self.node_body.setLayout(self.node_body_layout)
        self.inner_frame_layout.addWidget(self.node_body)

        if self.node_structure is not None:
            self._build_body_from_structure()
        else:
            self._build_custom_body()

        self.container_layout.addWidget(self.inner_frame)
        

        self.setWidget(self.node_frame)
        self.setPos(pos)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)


    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.inner_frame.setProperty("selected", value == 1)
            self.inner_frame.style().unpolish(self.inner_frame)
            self.inner_frame.style().polish(self.inner_frame)

            self.setZValue(1 if value else 0)
        return super().itemChange(change, value)
    
    
    def showEvent(self, event):
        super().showEvent(event)
        self._position_circles()
        return 
    
    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_circles()
        return
    
    
    def _position_circles(self):
        for i in range(self.node_body_layout.count()):
            item = self.node_body_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, (NodeOutput, NodeInput)):
                if hasattr(widget, "_update_circle_position"):
                    widget._update_circle_position()


    def _build_body_from_structure(self) -> None:
        """Use the specified node structure to create the node body"""
        if "outputs" in self.node_structure:
            for output in self.node_structure["outputs"]:
                output_port = NodeOutput(label=output.get("label", ""), data_type=output.get("data_type", "any"), proxy_ref=self)
                output_port.setObjectName(output["id"])
                output_port.parent_node = self
                output_port.port_id = output["id"]
                self.outputs[output["id"]] = output_port
                self.node_body_layout.addWidget(output_port)
            
        if "parameters" in self.node_structure:
            for parameter in self.node_structure["parameters"]:
                parameter_field = None
                
                match parameter["data_type"]:
                    case "dropdown":
                        parameter_field = NodeDropdown(label=parameter.get("label", ""), items=parameter.get("items"))
                        
                    case "checkbox":
                        parameter_field = NodeCheckBox(label=parameter.get("label", ""))
                
                parameter_field.setObjectName(parameter["id"])
                self.parameters[parameter["id"]] = parameter_field
                
                if parameter_field is not None:
                    self.node_body_layout.addWidget(parameter_field)
                
        if "inputs" in self.node_structure:
            for input in self.node_structure["inputs"]:
                input_port = NodeInput(label=input.get("label", ""), data_type=input.get("data_type", "any"), proxy_ref=self)
                
                input_port.setObjectName(input["id"])
                input_port.parent_node = self
                input_port.port_id = input["id"]
                self.inputs[input["id"]] = input_port
                self.node_body_layout.addWidget(input_port)
                
        return
    

    def _build_custom_body(self) -> None:
        """Create the body of the node"""
        pass
    
    
    def get_input_value(self, input_id, graph, cache):
        input_port = self.inputs.get(input_id)
        if not input_port or not input_port.connected_port:
            return None

        source_node = input_port.connected_port.parent_node
        output_id = input_port.connected_port.port_id

        result = graph.evaluate(source_node, cache)
        return result.get(output_id)
    

    def compute(self, graph, cache) -> dict:
        """Process inputs and return a dictionary of outputs."""
        raise NotImplementedError("Each node must implement compute().")



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
                    self.input_field.setMinimum(-9999)
                    self.input_field.setMaximum(9999)
                    self.input_field.setSingleStep(1)
                    self.input_field.setValue(0)
                    
                case "float":
                    self.input_field = QDoubleSpinBox()
                    self.input_field.setMinimum(-9999.0)
                    self.input_field.setMaximum(9999.0)
                    self.input_field.setSingleStep(0.1)
                    self.input_field.setValue(0.0)
                    
                case "str":
                    self.input_field = QLineEdit()

            
            layout.addWidget(self.label_widget, alignment=Qt.AlignmentFlag.AlignLeft)
            if self.input_field is not None:
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
        layout.addWidget(self.dropdown)
        
        self.dropdown.addItems(items)

        self.setLayout(layout)
        

class NodeCheckBox(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)

        self.checked = False

        self.box = QLabel(" ")  # initially empty
        self.box.setObjectName("CustomCheckBox")
        self.box.setFixedSize(16, 16)
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_widget = QLabel(label)

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
        # Set dynamic property
        self.box.setProperty("checked", self.checked)
        
        # Re-apply styling to refresh
        self.box.style().unpolish(self.box)
        self.box.style().polish(self.box)


class Port(QGraphicsEllipseItem):
    def __init__(self, port_type, data_type, parent=None):
        self.radius = 6
        self.port_type = port_type
        self.data_type = data_type
        self.color = PORT_COLOR_MAP.get(self.data_type, "#a1a1a1")
        
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
    "str": "#70b2ff",
    "array": "#6363c7"
}


def create_node_input():
    return


class ValueIntNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        node_structure = {
            "inputs": [
                {"data_type": "int", "id": "input_1", "label": "Value"},
            ],
            "outputs": [
                {"data_type": "int", "id": "output", "label": "Integer"},
            ]
        }
        
        super().__init__(scene_ref, title="Integer value", pos=pos, node_structure=node_structure, header_color="#9c343e")
        
    
    def compute(self, graph, cache):
        input_widget = self.inputs["input_1"].input_field
        value = int(input_widget.text()) if input_widget else 0
        print("ValueIntNode.compute() -> ", value)
        return {"output": value}
    
    
class AddNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        node_structure = {
            "inputs": [
                {"data_type": "any", "id": "input_1", "label": "Value"},
                {"data_type": "any", "id": "input_2", "label": "Value"},
            ],
            "outputs": [
                {"data_type": "any", "id": "output", "label": "Output"},
            ]
        }
        
        super().__init__(scene_ref, title="Add", pos=pos, node_structure=node_structure, header_color="#246283")
        
    
    def compute(self, graph, cache):
        a = self.get_input_value("input_1", graph, cache) or 0
        b = self.get_input_value("input_2", graph, cache) or 0
        res = a + b
        print(f"AddNode.compute() -> {a} + {b} = {res}")
        return {"output": res}
    

class DisplayDataNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        super().__init__(scene_ref, title="Display data", pos=pos, header_color="#9c343e")
    
    
    def _build_custom_body(self) -> None:
        input_port = NodeInput("Data", data_type="any", proxy_ref=self)
        input_port.setObjectName("input")
        input_port.parent_node = self
        input_port.port_id = "input"
        self.inputs["input"] = input_port
        self.node_body_layout.addWidget(input_port)
        
        self.display_label = QLabel()
        self.node_body_layout.addWidget(self.display_label)
    
    
    def compute(self, graph, cache):
        print("DisplayDataNode.compute() -> ")
        value = self.get_input_value("input", graph, cache)

        # Show result on label
        self.display_label.setText(str(value) if value is not None else "None")

        return {}


class TestNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        node_structure = {
            "inputs": [
                {"data_type": "int", "id": "input_int", "label": "Input int"},
                {"data_type": "float", "id": "input_float", "label": "Input float"},
                {"data_type": "str", "id": "input_str", "label": "Input str"},
            ],
            "parameters": [
                {"data_type": "dropdown", "id": "dropdown", "label": "Dropdown", "items": ["Option 1", "Option 2", "Option 3"]},
                {"data_type": "checkbox", "id": "checkbox", "label": "Checkbox!"},
            ],
            "outputs": [
                {"data_type": "float", "id": "output", "label": "Output"},
            ]
        }
        
        super().__init__(scene_ref, title="Test node", pos=pos, node_structure=node_structure, header_color="#707171")
        
    
    def compute():
        pass


class ImportDataNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        super().__init__(scene_ref, title="Import data", pos=pos, header_color="#121212")
        
    def _build_custom_body(self) -> None:
        self.node_body_layout.addWidget(NodeOutput("Data", "array", proxy_ref=self))
        
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        self.file_path_input = QLineEdit()
        layout.addWidget(self.file_path_input)

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self._open_file_dialog)
        layout.addWidget(self.open_button)
        
        self.node_body_layout.addLayout(layout)
        
    
    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(caption="Select File")
        if file_path:
            self.file_path_input.setText(file_path)
    
    def compute():
        pass


class PlotDataNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        super().__init__(scene_ref, title="Plot data", pos=pos, header_color="#121212")
        
    def _build_custom_body(self) -> None:
        self.node_body_layout.addWidget(NodeInput("Data", "array", proxy_ref=self))
        
        
    def compute():
        pass


class EvaluateGraphNode(Node):
    def __init__(self, scene_ref, pos=QPointF(0, 0)):
        super().__init__(scene_ref, title="Evaluate graph", pos=pos, header_color="#121212")
        
    def _build_custom_body(self) -> None:
        button = QPushButton("Evaluate graph")
        display_node = next((obj for obj in graph.nodes if isinstance(obj, DisplayDataNode)), None)
        button.clicked.connect(lambda: graph.evaluate(display_node))
        self.node_body_layout.addWidget(button)
        
        
    def compute(self, graph, cache):
        pass

graph = Graph()
if __name__ == "__main__":
    def load_stylesheet(app: QApplication, path: str):
        with open(path, "r") as f:
            app.setStyleSheet(f.read())
    
    app: QApplication = QApplication(sys.argv)
    app.setStyle("fusion")
    load_stylesheet(app, "src/styles.css")
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

    scene = QGraphicsScene()
    width = 10_000
    height = 5_000
    scene.setSceneRect(-width/2, -height/2, width, height)
    view = NodeEditor(scene)
    view.setWindowTitle("Node Editor")
    view.setMinimumSize(1500, 1000)
    #view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    #view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


    scene.addItem(ImportDataNode(scene, QPointF(-300, 0)))
    scene.addItem(TestNode(scene))
    scene.addItem(PlotDataNode(scene, QPointF(300, 0)))
    
    value_node_1 = ValueIntNode(scene, QPointF(-500, -300))
    value_node_2 = ValueIntNode(scene, QPointF(-500, -150))
    add_node = AddNode(scene, QPointF(-200, -300))
    display_node = DisplayDataNode(scene, QPointF(100, -300))
    
    graph.add_node(value_node_1)
    graph.add_node(value_node_2)
    graph.add_node(add_node)
    graph.add_node(display_node)
    
    graph.connect(value_node_1.outputs["output"], add_node.inputs["input_1"])
    graph.connect(value_node_2.outputs["output"], add_node.inputs["input_2"])
    graph.connect(add_node.outputs["output"], display_node.inputs["input"])
    
    scene.addItem(value_node_1)
    scene.addItem(value_node_2)
    scene.addItem(add_node)
    scene.addItem(display_node)
    scene.addItem(EvaluateGraphNode(scene, QPointF(400, -300)))

    view.show()
    sys.exit(app.exec())