from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *


class Wire(QGraphicsPathItem):
    def __init__(self, output_port, input_port, parent=None):
        super().__init__(parent)

        input_port.connected_port = output_port

        self.output_port = output_port
        self.input_port = input_port
        
        self.setZValue(-1)
        
        self.color_start = QColor(output_port.color)
        self.color_end = QColor(input_port.color)

        # Add wire to scene
        self.scene_ref = self.output_port.scene()
        self.scene_ref.addItem(self)

        # Register wire with ports
        self.output_port.connected_wires.append(self)
        self.input_port.connected_wire = self

        
        input_widget = self.input_port.parent_widget
        if hasattr(input_widget, "on_connection_changed"):
            input_widget.on_connection_changed()
        
        
        self.update_path()


    def update_path(self):
        
        p1 = self.output_port.scenePos() + QPointF(self.output_port.radius, self.output_port.radius)
        p2 = self.input_port.scenePos() + QPointF(self.input_port.radius, self.input_port.radius)

        dx = abs(p2.x() - p1.x()) * 0.5
        path = QPainterPath(p1)

        ctrl1 = QPointF(p1.x() + dx, p1.y())
        ctrl2 = QPointF(p2.x() - dx, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)

        self.setPath(path)

        # Create gradient from p1 to p2
        gradient = QLinearGradient(p1, p2)
        gradient.setColorAt(0, self.color_start)
        gradient.setColorAt(1, self.color_end)

        pen = QPen(QBrush(gradient), 4)
        self.setPen(pen)

    def remove(self):
        self.scene_ref.removeItem(self)
        if self in self.output_port.connected_wires:
            self.output_port.connected_wires.remove(self)
        self.input_port.connected_wire = None
        
        input_widget = self.input_port.parent_widget
        if hasattr(input_widget, "on_connection_changed"):
            input_widget.on_connection_changed()
