from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *


from qt.node_editor.Wire import Wire


class Port(QGraphicsEllipseItem):
    color_map = {
        "boolean": "#cca6d6",
        "int": "#598c5c",
        "float": "#a1a1a1",
        "str": "#70b2ff",
        "array": "#6363c7"
    }
    
    def __init__(self, port_type: str, data_type: str, parent_widget, accept_multiple_wires: bool=False):
        self.radius = 6
        self.port_type = port_type
        self.data_type = data_type
        self.color = self.color_map.get(self.data_type, "#a1a1a1")
        
        self.accept_multiple_wires = accept_multiple_wires
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

        self.temp_wire = None

    def hoverEnterEvent(self, event):
        #self.setBrush(QColor("#ff6e40"))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        #self.setBrush(QColor(self.color))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        editor = self.scene().views()[0]  # assumes one view
        if hasattr(editor, "begin_wire_drag"):
            editor.begin_wire_drag(self, event.scenePos())
        super().mousePressEvent(event)
