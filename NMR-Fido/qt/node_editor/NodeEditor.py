import sys
import os
import numpy as np
import importlib
import inspect

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from qt.node_editor.Node import Node
from qt.node_editor.nodes import *
from qt.node_editor.Wire import Wire
from qt.node_editor.Port import Port

class NodeEditor(QGraphicsView):
    def __init__(self, scene_size: tuple=(10_000, 5_000), background_color: str="#1d1d1d"):
        self.nodes = []
        self.connections = []
        self.cache = {}
        
        self.graphics_scene = QGraphicsScene()
        width, height = scene_size
        self.graphics_scene.setSceneRect(-width/2, -height/2, width, height)
        super().__init__(self.graphics_scene)
        
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor(background_color))
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._mouse_offset = QPointF()
        self._pressed_item = None
        self._selected_item_offsets = {}
        
        self._is_panning = False
        self._pan_start = QPoint()
        
        self._dragged_port = None
        self._temp_wire = None
        
        self._cutting = False
        self._cut_path = None
        self._cut_points = []
        
        self._zoom = 0
        self._zoom_step = 0.1
        self._zoom_range = (0.1, 2.0)  # min and max zoom scale
        
        self._pending_node = None
        
        self._copied_nodes = []
        
        self._pre_rubberband_selection = set()
        
        self._init_context_menu()
    
    
    def _load_nodes(self) -> dict:
        module = importlib.import_module("qt.node_editor.nodes")
        node_classes = {}

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Node) and obj is not Node:
                category = getattr(obj, "category", "Uncategorized")
                if category not in node_classes:
                    node_classes[category] = []
                node_classes[category].append(obj)

        return node_classes
    
    
    def _init_context_menu(self) -> None:
        self.context_menu = QMenu(self)

        # Add actions to the menu
        self.add_node_menu = self.context_menu.addMenu("Add Node")
        self.node_class_map = self._load_nodes()
        for category, class_list in self.node_class_map.items():
            category_menu = self.add_node_menu.addMenu(category)
            for cls in class_list:
                action = QAction(cls.title, self)
                action.triggered.connect(lambda checked=False, cls=cls: self._spawn_node(cls))
                category_menu.addAction(action)

        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.triggered.connect(self.reset_zoom)
        self.context_menu.addAction(reset_zoom_action)
        
        self._context_menu_scene_pos = QPointF()
        return
    
    
    def _spawn_node(self, node_cls):
        node = node_cls()
        node.node_editor = self
        self._pending_node = node
        self.graphics_scene.addItem(node)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
    
    
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
        if self.dragMode() == QGraphicsView.RubberBandDrag and event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._pre_rubberband_selection = set(self.scene().selectedItems())
            else:
                self._pre_rubberband_selection.clear()
        self._pressed_item = self.itemAt(event.position().toPoint())
        
        if isinstance(self._pressed_item, Node):
            proxy = self._pressed_item  # QGraphicsProxyWidget
            widget = proxy.widget()
            if widget is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                widget_pos = proxy.mapFromScene(scene_pos)
                child = widget.childAt(widget_pos.x(), widget_pos.y())

                while child is not None:
                    if isinstance(child, (QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, pg.PlotWidget)):
                        super().mousePressEvent(event)
                        return
                    child = child.parentWidget()
        
        
        original_selection = set(self.scene().selectedItems())
        super().mousePressEvent(event)

        if isinstance(self._pressed_item, Node):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Toggle selection for Shift+Click
                if self._pressed_item in original_selection:
                    self._pressed_item.setSelected(False)
                else:
                    self._pressed_item.setSelected(True)
                for item in original_selection:
                    item.setSelected(True)
            else:
                # Regular click selects only this node
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
        
        if self._dragged_port:
            self._update_temp_wire_path(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        
        if self._pending_node:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._pending_node.setPos(scene_pos)
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
        
        if self._dragged_port:
            mouse_pos = self.mapToScene(event.position().toPoint())
            items = self.scene().items(mouse_pos)
            for item in items:
                if isinstance(item, Port):
                    source, dest = (self._dragged_port, item) if self._dragged_port.port_type == "output" else (item, self._dragged_port)
                    if source.port_type == "output" and dest.port_type == "input":
                        if not dest.accept_multiple_wires and dest.connected_wire:
                            dest.connected_wire.remove()
                        Wire(output_port=source, input_port=dest)
                        break

            if self._temp_wire:
                self.scene().removeItem(self._temp_wire)
                self._temp_wire = None
            self._dragged_port = None

            event.accept()
            return
        
        if self._pending_node:
            self.nodes.append(self._pending_node)
            self._pending_node = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        if self.dragMode() == QGraphicsView.RubberBandDrag and event.button() == Qt.MouseButton.LeftButton:
            if self._pre_rubberband_selection:
                # Use cached selection to toggle
                view_rect = self.rubberBandRect()
                scene_rect = self.mapToScene(view_rect).boundingRect()
                items_in_band = [item for item in self.scene().items(scene_rect) if isinstance(item, Node)]

                toggled_set = set()
                for item in items_in_band:
                    item.setSelected(item not in self._pre_rubberband_selection)
                    toggled_set.add(item)

                # Restore rest of original selection
                for item in self._pre_rubberband_selection:
                    if item not in toggled_set:
                        item.setSelected(True)

                self._pre_rubberband_selection.clear()
                event.accept()
                return
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)
        return
    
    
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        item = self.itemAt(event.pos())

        if item is None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._context_menu_scene_pos = self.mapToScene(event.pos())
            self.context_menu.popup(event.globalPos())
        return
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete:
            for item in self.scene().selectedItems():
                if isinstance(item, Node):
                    self.remove(item)
            event.accept()
            return
        
        if (event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._copied_nodes = [node for node in self.nodes if node.isSelected()]
            event.accept()
            return
        
        if (event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._paste_nodes()
            event.accept()
            return
        
        if (event.key() == Qt.Key.Key_A and
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            
            # Store mouse position in scene coords
            cursor_pos = QCursor.pos()
            self._context_menu_scene_pos = self.mapToScene(self.mapFromGlobal(cursor_pos))
            
            # Open just the "Add Node" submenu
            self.add_node_menu.popup(cursor_pos)
            event.accept()
            return

        # pass other keys to the default handler
        super().keyPressEvent(event)
    #endregion Events
    
    
    
    def _paste_nodes(self):
        cursor_pos = QCursor.pos()
        scene_center = self.mapToScene(self.mapFromGlobal(cursor_pos))
        
        bounding_rect = self._copied_nodes[0].sceneBoundingRect()
        for node in self._copied_nodes[1:]:
            bounding_rect = bounding_rect.united(node.sceneBoundingRect())
        group_center = bounding_rect.center()
        print(group_center)

        new_nodes = []
        for node in self._copied_nodes:
            # Instantiate a new node of the same class
            new_node = node.__class__()
            new_node.node_editor = self

            original_center = node.sceneBoundingRect().center()
            original_top_left = node.sceneBoundingRect().topLeft()
            offset_from_center_to_top_left = original_top_left - original_center
            
            new_pos = scene_center + (node.sceneBoundingRect().center() - group_center) + offset_from_center_to_top_left
            new_node.setPos(new_pos)

            # Copy parameter values if applicable
            for param_id, param in node.parameters.items():
                new_param = new_node.parameters.get(param_id)
                if new_param and hasattr(param, "_value_widget") and hasattr(new_param, "_value_widget"):
                    val = param.get_value()
                    if hasattr(new_param._value_widget, "setValue"):
                        new_param._value_widget.setValue(val)
                    elif isinstance(new_param._value_widget, QLineEdit):
                        new_param._value_widget.setText(val)
                    elif isinstance(new_param._value_widget, QComboBox):
                        new_param._value_widget.setCurrentText(val)
                    elif isinstance(new_param._value_widget, QCheckBox):
                        new_param._value_widget.setChecked(val)

            self.graphics_scene.addItem(new_node)
            self.nodes.append(new_node)
            new_nodes.append(new_node)

        # Optionally select pasted nodes
        for node in new_nodes:
            node.setSelected(True)
    
    
    def begin_wire_drag(self, port, scene_pos):
        if port.port_type == "input" and port.connected_wire:
            # Reuse output port and delete old wire
            output_port = port.connected_wire.output_port
            port.connected_wire.remove()
            port = output_port  # switch to dragging from output

        self._dragged_port = port
        self._temp_wire = QGraphicsPathItem()
        self._temp_wire.setPen(QPen(QColor(port.color), 4))
        self._temp_wire.setZValue(1)
        self.scene().addItem(self._temp_wire)

        self._update_temp_wire_path(scene_pos)


    def _update_temp_wire_path(self, mouse_pos):
        if not self._dragged_port or not self._temp_wire:
            return

        start = self._dragged_port.scenePos() + QPointF(self._dragged_port.radius, self._dragged_port.radius)
        path = QPainterPath(start)
        dx = abs(mouse_pos.x() - start.x()) * 0.5

        if self._dragged_port.port_type == "output":
            ctrl1 = QPointF(start.x() + dx, start.y())
            ctrl2 = QPointF(mouse_pos.x() - dx, mouse_pos.y())
        else:
            ctrl1 = QPointF(start.x() - dx, start.y())
            ctrl2 = QPointF(mouse_pos.x() + dx, mouse_pos.y())

        path.cubicTo(ctrl1, ctrl2, mouse_pos)
        self._temp_wire.setPath(path)
    
    
    def reset_zoom(self) -> None:
        self.resetTransform()
        self._zoom = 0
        return
    
    #region Node/Graph
    def add(self, node: Node, pos: QPointF|QPoint|tuple=(0, 0)) -> None:
        node.node_editor = self
        
        self.graphics_scene.addItem(node)
        self.nodes.append(node)
        
        if isinstance(pos, tuple):
            node.setPos(*pos)
        else:
            node.setPos(pos)
        
        return
    
    def remove(self, node: Node) -> None:
        if node not in self.nodes:
            return  # already removed
    
        # Disconnect all ports
        for param in node.parameters.values():
            port = getattr(param, "port", None)
            if port:
                if port.accept_multiple_wires:
                    for wire in list(port.connected_wires):
                        wire.remove()
                    port.connected_wires.clear()
                elif port.connected_wire:
                    port.connected_wire.remove()
                    port.connected_wire = None
                    
        for param in node.outputs.values():
            port = getattr(param, "port", None)
            if port:
                for wire in list(port.connected_wires):
                    wire.remove()
                port.connected_wires.clear()
        
        # Remove node from scene
        self.graphics_scene.removeItem(node)
        
        # Remove from internal list
        self.nodes.remove(node)
        
        # Clean cache
        if node in self.cache:
            del self.cache[node]
        
        return
    
    
    def connect(self, output_port: Port, input_port: Port) -> Wire:
        return Wire(output_port, input_port)
    
    
    def disconnect(self, target_port: Port) -> None:
        target_port.connected_port = None
        target_port.connected_wire.remove()
        return
    
    
    def _disconnect_wires_along_path(self, path: QPainterPath):
        for item in self.scene().items():
            if isinstance(item, QGraphicsPathItem) and hasattr(item, "input_port") and hasattr(item, "output_port"):
                if path.intersects(item.path()):
                    # Disconnect logic
                    item.remove()
    
    
    def evaluate_node(self, node):
        inputs = node.prepare_inputs()
        
        if node not in self.cache: self.cache[node] = {};
        
        def compare(x, y):
            try:
                if type(x) != type(y):
                    return False
                
                if isinstance(x, np.ndarray):
                    return x.dtype == y.dtype and np.array_equal(x, y)
                
                return x == y
            except:
                return False
        
        if "inputs" in self.cache[node] and all(compare(x, y) for x, y in zip(self.cache[node]["inputs"].values(), inputs.values())):
            return self.cache[node]["result"]
        else:
            self.cache[node]["inputs"] = inputs
            
            result = node.compute(inputs)
            self.cache[node]["result"] = result
            
            return result


    def evaluate_graph(self):
        visited = set()
        results = {}

        def visit(node):
            if node in visited:
                return

            # Visit upstream dependencies first
            for param in node.parameters.values():
                port = getattr(param, "port", None)
                if not port or port.port_type != "input":
                    continue

                wires = port.connected_wires if port.accept_multiple_wires else [port.connected_wire] if port.connected_wire else []
                for wire in wires:
                    upstream_node = wire.output_port.parent_node
                    visit(upstream_node)

            # Then evaluate the node itself
            results[node] = self.evaluate_node(node)
            visited.add(node)

        # Start from all leaf nodes (no output wires)
        for node in self.nodes:
            has_outputs = any(
                port.connected_wires for param in node.outputs.values()
                if (port := getattr(param, "port", None))
            )
            if not has_outputs:
                visit(node)

        return results

    #endregion Node/Graph
