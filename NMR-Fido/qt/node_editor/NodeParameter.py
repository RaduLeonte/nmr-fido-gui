from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *


from qt.node_editor.Port import Port


class NodeParameter(QWidget):
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
        
        self.setFixedHeight(30)

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # Port on left if input
        if self.input_port_enabled:
            self._ensure_port("input")
        
        if label is not None:
            parameter_label = QLabel(label)
            if output_port:
                parameter_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(parameter_label)

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
            box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
            return box
        elif t == "float":
            box = QDoubleSpinBox()
            box.setRange(-9999.0, 9999.0)
            box.setValue(0.0)
            box.setSingleStep(0.1)
            box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        if self.port and self.port.port_type == "input":
            is_connected = self.port.connected_wire is not None
            if self._value_widget:
                self._value_widget.setVisible(not is_connected)