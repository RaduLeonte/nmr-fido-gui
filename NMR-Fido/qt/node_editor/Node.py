from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

from qt.node_editor.Wire import Wire


class Node(QGraphicsProxyWidget):
    def __init__(self, node_structure: dict=None):
        super().__init__()
        
        cls = self.__class__
        self.title = getattr(cls, 'title', "Node")
        self.header_color = getattr(cls, 'header_color', "#121212")

        self.node_structure = node_structure
        
        self.outputs = {}
        self.parameters = {}
        self.inputs = {}

        self._init_ui()


    #region Events
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.parameters.values():
                if hasattr(port, "port") and port.port and port.port.port_type == "input":
                    wire = getattr(port.port, "connected_wire", None)
                    if wire:
                        wire.update_path()

            for port in self.outputs.values():
                if hasattr(port, "port") and port.port:
                    for wire in port.port.connected_wires:
                        wire.update_path()
        return super().itemChange(change, value)
    
    
    def showEvent(self, event):
        super().showEvent(event)
        self._position_circles()
        return 
    
    
    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_circles()
        return
    #endregion
    
    def _position_circles(self):
        for i in range(self.node_body_layout.count()):
            item = self.node_body_layout.itemAt(i)
            widget = item.widget()
            if not widget:
                continue

            # Check if the widget has a port and an update method
            if hasattr(widget, "port") and widget.port is not None:
                if hasattr(widget, "_update_port_position"):
                    widget._update_port_position()


    def _init_ui(self) -> None:
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
        palette.setColor(QPalette.ColorRole.Window, QColor(self.header_color))
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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        return


    def _build_body_from_structure(self) -> None:
        """Use the specified node structure to create the node body"""
        if "outputs" in self.node_structure:
            for output in self.node_structure["outputs"]:
                output_id = output["id"]
                label = output.get("label", output_id)
                data_type = output.get("data_type", "any")

                widget = NodeParameterWidget(
                    param_type="output",
                    label=label,
                    data_type=data_type,
                    input_port=False,
                    output_port=True,
                    proxy_ref=self,
                    parent_node=self,
                    port_id=output_id,
                )
                widget.setObjectName(output_id)
                widget.parent_node = self
                widget.port_id = output_id
                self.outputs[output_id] = widget
                self.node_body_layout.addWidget(widget)
            
        if "parameters" in self.node_structure:
            for param in self.node_structure["parameters"]:
                param_id = param["id"]
                param_type = param.get("data_type", "any")
                label = param.get("label", param_id)

                widget = NodeParameterWidget(
                    param_type=param_type,
                    label=label,
                    data_type=param_type,
                    input_port=param.get("input", False),
                    output_port=False,
                    items=param.get("items", []),
                    proxy_ref=self,
                    parent_node=self,
                    port_id=param_id,
                )
                widget.setObjectName(param_id)
                widget.parent_node = self
                widget.port_id = param_id
                self.parameters[param_id] = widget
                self.node_body_layout.addWidget(widget)
        
        return
    

    def _build_custom_body(self) -> None:
        """Create the body of the node"""
        pass
    
    
    def prepare_inputs(self, graph, cache):
        inputs = {}
        print(f"[{self.title}] Preparing inputs:")
        for param_id, widget in self.parameters.items():
            print(f" - {param_id}: port={hasattr(widget, 'port')}, connected={getattr(widget.port, 'connected_port', None)}")
            port = getattr(widget, "port", None)
            connected_port = getattr(port, "connected_port", None)

            if port and port.port_type == "input" and connected_port:
                # Connected: get value from upstream
                source_node = connected_port.parent_node
                upstream_result = graph.evaluate(source_node, cache)  
                value = upstream_result.get(connected_port.port_id)
            else:
                # Not connected or no port: get local value
                value = widget.get_value() if hasattr(widget, "get_value") else None

            inputs[param_id] = value
        return inputs
        

    def compute(self, inputs) -> dict:
        """Process inputs and return a dictionary of outputs."""
        raise NotImplementedError("Each node must implement compute().")
    
    

class NodeParameterWidget(QWidget):
    def __init__(
        self,
        param_type: str,  # "int", "float", "str", "dropdown", "checkbox", "output"
        label: str,
        data_type: str = None,
        input_port: bool = False,
        output_port: bool = False,
        items: list = None,
        proxy_ref: QGraphicsProxyWidget = None,
        parent_node=None,
        port_id: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.port_id = port_id or label
        self.parent_node = parent_node
        self.param_type = param_type
        self.label = label
        self.data_type = data_type
        self.proxy = proxy_ref
        self.input_port_enabled = input_port
        self.output_port_enabled = output_port
        self.port = None
        self._value_widget = None

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # Port on left if input
        if self.input_port_enabled:
            self._ensure_port("input")
        
        layout.addWidget(QLabel(label))

        # Input widget (if needed)
        if param_type in ("int", "float", "str"):
            self._value_widget = self._build_numeric(param_type)
            layout.addWidget(self._value_widget)

        elif param_type == "dropdown" and items:
            self._value_widget = QComboBox()
            self._value_widget.addItems(items)
            layout.addWidget(self._value_widget)

        elif param_type == "checkbox":
            self._value_widget = QCheckBox()
            layout.addWidget(self._value_widget)

        # Port on right if output
        if self.output_port_enabled:
            self._ensure_port("output")

        self.setLayout(layout)

    def _build_numeric(self, t):
        if t == "int":
            box = QSpinBox()
            box.setRange(-9999, 9999)
            box.setValue(0)
            return box
        elif t == "float":
            box = QDoubleSpinBox()
            box.setRange(-9999.0, 9999.0)
            box.setValue(0.0)
            box.setSingleStep(0.1)
            return box
        elif t == "str":
            return QLineEdit()

    def _ensure_port(self, port_type):
        if self.port is not None:
            return

        self.port = Port(port_type, self.data_type, parent_widget=self)
        self.port.setParentItem(self.proxy)
        self.port.parent_node = self.parent_node
        self.port.port_id = self.port_id


    def showEvent(self, event):
        super().showEvent(event)
        self._update_port_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_port_position()

    def _update_port_position(self):
        if not self.port or not self.proxy:
            return

        if self.port.port_type == "input":
            pos = self.mapTo(self.proxy.widget(), self.rect().topLeft())
            x = pos.x() - self.port.radius * 2
        else:
            pos = self.mapTo(self.proxy.widget(), self.rect().topRight())
            x = pos.x()

        y = pos.y() + self.height() / 2 - self.port.radius
        self.port.setPos(QPointF(x, y))

    def get_value(self):
        if isinstance(self._value_widget, QSpinBox) or isinstance(self._value_widget, QDoubleSpinBox):
            return self._value_widget.value()
        elif isinstance(self._value_widget, QLineEdit):
            return self._value_widget.text()
        elif isinstance(self._value_widget, QComboBox):
            return self._value_widget.currentText()
        elif isinstance(self._value_widget, QCheckBox):
            return self._value_widget.isChecked()
        return None
    
    
    def on_connection_changed(self):
        print("on_connection_changed")
        if self.port.port_type == "input":
            is_connected = getattr(self.port, "connected_wire", None) is not None
            if self._value_widget:
                self._value_widget.setVisible(not is_connected)


class Port(QGraphicsEllipseItem):
    color_map = {
        "boolean": "#cca6d6",
        "int": "#598c5c",
        "float": "#a1a1a1",
        "str": "#70b2ff",
        "array": "#6363c7"
    }
    
    def __init__(self, port_type, data_type, parent_widget):
        self.radius = 6
        self.port_type = port_type
        self.data_type = data_type
        self.color = self.color_map.get(self.data_type, "#a1a1a1")
        
        self.connected_wires = []  # for output ports
        self.connected_wire = None  # for input ports
        
        self.parent_widget = parent_widget
        
        super().__init__(0, 0, self.radius * 2, self.radius * 2)
        
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
        if target_port.connected_wire:
            existing_wire = target_port.connected_wire
            if existing_wire:
                target_port.scene().removeItem(existing_wire)
                if existing_wire in self.connected_wires:
                    self.connected_wires.remove(existing_wire)
                
        target_port.connected_wire = self
        
        Wire(output_port=self, input_port=target_port)
