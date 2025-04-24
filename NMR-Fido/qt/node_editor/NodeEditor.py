import sys
import os
import numpy as np

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

from qt.node_editor.Node import Node

class NodeEditor(QGraphicsView):
    def __init__(self, graph, size: tuple=(10_000, 5_000), background_color: str="#1d1d1d"):
        self.graph = graph
        
        self.scene_ref = QGraphicsScene()
        width, height = size
        self.scene_ref.setSceneRect(-width/2, -height/2, width, height)
        
        super().__init__(self.scene_ref)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor(background_color))
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._mouse_offset = QPointF()
        self._pressed_item = None
        self._selected_item_offsets = {}
        
        self._is_panning = False
        self._pan_start = QPoint()
        
        self._cutting = False
        self._cut_path = None
        self._cut_points = []
        
        self._zoom = 0
        self._zoom_step = 0.1
        self._zoom_range = (0.1, 2.0)  # min and max zoom scale
        
    
    #region Events
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
        
        if event.button() == Qt.MouseButton.RightButton and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._cutting = True
            self._cut_points = [self.mapToScene(event.position().toPoint())]
            self._cut_path = QGraphicsPathItem()
            self._cut_path.setZValue(1000)  # Always on top
            self._cut_path.setPen(QPen(QColor("#ff5555"), 2, Qt.PenStyle.DashLine))
            self.scene().addItem(self._cut_path)
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
        
        if self._cutting:
            pos = self.mapToScene(event.position().toPoint())
            self._cut_points.append(pos)

            path = QPainterPath(self._cut_points[0])
            for point in self._cut_points[1:]:
                path.lineTo(point)

            self._cut_path.setPath(path)
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
            
  
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        
        if self._cutting:
            self._cutting = False

            if self._cut_path:
                self._disconnect_wires_along_path(self._cut_path.path())
                self.scene().removeItem(self._cut_path)
                self._cut_path = None
                self._cut_points.clear()

            event.accept()
            return
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)
        return
    
    
    def _disconnect_wires_along_path(self, path: QPainterPath):
        for item in self.scene().items():
            if isinstance(item, QGraphicsPathItem) and hasattr(item, "input_port") and hasattr(item, "output_port"):
                # Test if wire intersects the cut path
                if path.intersects(item.path()):
                    # Disconnect logic
                    wire = item
                    input_port = wire.input_port
                    output_port = wire.output_port

                    # Remove from scene
                    self.scene().removeItem(wire)

                    # Clear connections
                    if input_port.connected_wire == wire:
                        input_port.connected_wire = None
                        
                        widget = input_port.parentItem()
                        if hasattr(widget, "on_connection_changed"):
                            widget.on_connection_changed()

                    if wire in output_port.connected_wires:
                        output_port.connected_wires.remove(wire)
    
    
    def add(self, item: Node, pos: QPointF|QPoint|tuple=(0, 0)) -> None:
        self.scene_ref.addItem(item)
        self.graph.add_node(item)
        
        if isinstance(pos, tuple):
            item.setPos(*pos)
        else:
            item.setPos(pos)
        
        return

