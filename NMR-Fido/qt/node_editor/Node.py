from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

from misc import set_css_attribute
from qt.node_editor.NodeParameter import NodeParameter


class Node(QGraphicsProxyWidget):
    def __init__(self, node_structure: dict=None):
        super().__init__()
        
        
        self.node_editor = None
        
        cls = self.__class__
        self.title = getattr(cls, 'title', "Node")
        self.header_color = getattr(cls, 'header_color', "#121212")

        self.node_structure = node_structure
        
        self.outputs = {}
        self.parameters = {}

        self._init_ui()


    #region Events
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = value == True
            set_css_attribute(self.inner_frame, "selected", "true" if selected else "false")
        
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.parameters.values():
                if hasattr(port, "port") and port.port and port.port.port_type == "input":
                    if port.port.accept_multiple_wires:
                        for wire in port.port.connected_wires:
                            wire.update_path()
                    else:
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
        self.node_header.setFixedHeight(30)
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


    def _on_widget_changed(self, *args):
        if self.node_editor:
            self.node_editor.trigger_evaluation()

    def _build_body_from_structure(self) -> None:
        """Use the specified node structure to create the node body"""
        if "outputs" in self.node_structure:
            for output in self.node_structure["outputs"]:
                output_id = output["id"]
                label = output.get("label", output_id)
                data_type = output.get("data_type", "any")

                widget = NodeParameter(
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

                widget = NodeParameter(
                    param_type=param_type,
                    label=label,
                    data_type=param_type,
                    default_value=param.get("default_value", None),
                    clamp=param.get("clamp", None),
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
    
    
    def prepare_inputs(self):
        inputs = {}
        for param_id, widget in self.parameters.items():
            port = getattr(widget, "port", None)

            if port is not None and port.accept_multiple_wires and hasattr(port, "connected_wires"):
                values = []
                for wire in port.connected_wires:
                    source_node = wire.output_port.parent_node
                    upstream_result = self.node_editor.evaluate_node(source_node)
                    values.append(upstream_result.get(wire.output_port.port_id) if upstream_result is not None else None)
                value = values
            elif port is not None and port.connected_wire:
                source_node = port.connected_wire.output_port.parent_node
                upstream_result = self.node_editor.evaluate_node(source_node)
                value = upstream_result.get(port.connected_wire.output_port.port_id) if upstream_result is not None else None
            else:
                value = widget.get_value() if hasattr(widget, "get_value") else None

            inputs[param_id] = value
        #print(f"[{self.title}] Preparing inputs:", inputs)
        return inputs
        

    def compute(self, inputs: dict) -> dict:
        """Process inputs and return a dictionary of outputs."""
        raise NotImplementedError("Each node must implement compute().")
    
    
    


