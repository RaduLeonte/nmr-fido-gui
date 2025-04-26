import sys
import os
import numpy as np
import importlib
import inspect
import time
import traceback

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
        
        self._init_context_menu()
        
        self._is_ready = False
    
    
    #region Load nodes
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
    
    
    #region Context menu
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
        
        
        debug_menu = self.context_menu.addMenu("Debug")
        
        print_node_pos = QAction("Print node positions", self)
        print_node_pos.triggered.connect(self._print_node_positions)
        debug_menu.addAction(print_node_pos)
        
        self._context_menu_scene_pos = QPointF()
        return
    
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        item = self.itemAt(event.pos())

        if item is None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._context_menu_scene_pos = self.mapToScene(event.pos())
            self.context_menu.popup(event.globalPos())
        return
    
    
    #region Events
    def showEvent(self, event):
        super().showEvent(event)
        if not self._is_ready:
            QTimer.singleShot(0, self._mark_ready)
    
    def _mark_ready(self):
        self._is_ready = True
        self.trigger_evaluation()
    
    
    #region Zoom
    def wheelEvent(self, event):
        if self._forward_event_to_plotwidget(event):
            return
        
        modifiers = event.modifiers()
        delta = event.angleDelta().y()

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
            return

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta)
            return

        old_pos = self.mapToScene(event.position().toPoint())

        factor = 1.0 + self._zoom_step if delta > 0 else 1.0 - self._zoom_step
        new_scale = self.transform().m11() * factor

        if self._zoom_range[0] <= new_scale <= self._zoom_range[1]:
            self.scale(factor, factor)
            self._zoom += (1 if delta > 0 else -1)

        new_pos = self.mapToScene(event.position().toPoint())

        delta_scene = new_pos - old_pos

        self.translate(delta_scene.x(), delta_scene.y())
    

    #region Mouse press
    def mousePressEvent(self, event):
        if self._forward_event_to_plotwidget(event):
            return
        
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
        pressed_item = self.itemAt(event.position().toPoint())
        
        if isinstance(pressed_item, Node):
            proxy = pressed_item  # QGraphicsProxyWidget
            widget = proxy.widget()
            if widget is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                widget_pos = proxy.mapFromScene(scene_pos)
                child = widget.childAt(widget_pos.x(), widget_pos.y())

                while child is not None:
                    if isinstance(child, (QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, pg.PlotWidget)):
                        event.setAccepted(False)
                        super().mousePressEvent(event)
                        return
                    child = child.parentWidget()
        
        
        original_selection = set(self.scene().selectedItems())
        super().mousePressEvent(event)

        self._pressed_item = self.itemAt(event.position().toPoint())
        if isinstance(self._pressed_item, Node):
            if self._pressed_item in original_selection:
                for item in original_selection:
                    item.setSelected(True)
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._pressed_item.setSelected(False)
            else:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._pressed_item.setSelected(True)
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

    #region Mouse move
    def mouseMoveEvent(self, event):
        if self._forward_event_to_plotwidget(event):
            return
        
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
        
        
        hovered_item = self.itemAt(event.position().toPoint())
        
        if isinstance(hovered_item, Node):
            proxy = hovered_item  # QGraphicsProxyWidget
            widget = proxy.widget()
            if widget is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                widget_pos = proxy.mapFromScene(scene_pos)
                child = widget.childAt(widget_pos.x(), widget_pos.y())

                while child is not None:
                    if isinstance(child, pg.PlotWidget):
                        event.setAccepted(False)
                        super().mouseMoveEvent(event)
                        return
                    child = child.parentWidget()

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
            
  
    #region Mouse release
    def mouseReleaseEvent(self, event) -> None:
        if self._forward_event_to_plotwidget(event):
            return
        
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
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)
        return


    #region Key press
    def keyPressEvent(self, event: QKeyEvent):
        """Del | X"""
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_X:
            for item in self.scene().selectedItems():
                if isinstance(item, Node):
                    self.remove(item)
            event.accept()
            return
        
        """CTRL + C"""
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C):
            self._copied_nodes = [node for node in self.nodes if node.isSelected()]
            event.accept()
            return
        """CTRL + V"""
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V):
            self._paste_nodes()
            event.accept()
            return
        
        """CTRL + R"""
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_R):
            self.trigger_evaluation()
            event.accept()
            return
        
        """SHIFT + A"""
        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier and
            event.key() == Qt.Key.Key_A):
            
            # Store mouse position in scene coords
            cursor_pos = QCursor.pos()
            self._context_menu_scene_pos = self.mapToScene(self.mapFromGlobal(cursor_pos))
            
            # Open just the "Add Node" submenu
            self.add_node_menu.popup(cursor_pos)
            event.accept()
            return

        # pass other keys to the default handler
        super().keyPressEvent(event)
    
    
    def _forward_event_to_plotwidget(self, event):
        hovered_item = self.itemAt(event.position().toPoint())
        if isinstance(hovered_item, Node):
            proxy = hovered_item
            widget = proxy.widget()
            if widget is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                widget_pos = proxy.mapFromScene(scene_pos)
                child = widget.childAt(widget_pos.x(), widget_pos.y())

                while child is not None:
                    if isinstance(child, pg.PlotWidget):
                        view = child.viewport()

                        if isinstance(event, QMouseEvent):
                            forwarded_event = QMouseEvent(
                                event.type(),
                                widget_pos,
                                event.globalPosition().toPoint(),
                                event.button(),
                                event.buttons(),
                                event.modifiers(),
                            )
                            QApplication.sendEvent(view, forwarded_event)
                            return True

                        elif isinstance(event, QWheelEvent):
                            forwarded_event = QWheelEvent(
                                widget_pos,
                                event.globalPosition(),
                                event.pixelDelta(),
                                event.angleDelta(),
                                event.buttons(),
                                event.modifiers(),
                                event.phase(),
                                event.inverted(),
                                event.source()
                            )
                            QApplication.sendEvent(view, forwarded_event)
                            return True

                    child = child.parentWidget()
        return False

    
    
    
    #region Paste nodes
    def _paste_nodes(self):
        cursor_pos = QCursor.pos()
        scene_center = self.mapToScene(self.mapFromGlobal(cursor_pos))
        
        bounding_rect = self._copied_nodes[0].sceneBoundingRect()
        for node in self._copied_nodes[1:]:
            bounding_rect = bounding_rect.united(node.sceneBoundingRect())
        group_center = bounding_rect.center()

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

        self.scene().clearSelection()
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
    
    def _spawn_node(self, node_cls) -> None:
        node = node_cls()
        node.node_editor = self
        self._pending_node = node
        self.graphics_scene.addItem(node)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
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
    
    
    #region Evaluate graph
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
            
            try:
                result = node.compute(inputs)
                self.cache[node]["result"] = result
            except Exception as e:
                print("Node evaluation")
                traceback.print_exc()
                result = None
                self.cache[node].clear()
            
            return result

    def trigger_evaluation(self) -> None:
        if not self._is_ready:
            return
        
        self.evaluate_graph()
        return


    def evaluate_graph(self):
        start = time.time()
        self._is_ready = False
        
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


        for node in self.nodes:
            has_outputs = any(
                port.connected_wires for param in node.outputs.values()
                if (port := getattr(param, "port", None))
            )
            if not has_outputs:
                visit(node)

        elapsed = time.time() - start
        minutes, seconds = divmod(elapsed, 60)
        milliseconds = (seconds - int(seconds)) * 1000
        print(f"Graph evaluated in: {int(minutes)}m {int(seconds)}s {int(milliseconds):.0f}ms")
        self._is_ready = True
        return results
    
    
    #region Debugging
    def _spawn_debugging_nodes(self) -> None:
        import_node = ImportDataNode(default_path="test.fid")
        self.add(import_node, QPointF(-1100, 0))
        
        sine = SineWindowNode()
        self.add(sine, QPointF(-800, 0))
        
        plot1 = Plot1DDataNode()
        self.add(plot1, QPointF(-200, 500))
        
        zf = ZeroFillingNode()
        self.add(zf, QPointF(-200, 0))
        
        ft = FourierTransformNode()
        self.add(ft, QPointF(200, 0))
        
        extfid1 = ExtractRow()
        self.add(extfid1, QPointF(-500, 300))
        
        math = MathNode(default_values=[None, 350], default_mode="Multiply")
        self.add(math, QPointF(-500, 500))
        
        extfid2 = ExtractRow()
        self.add(extfid2, QPointF(-500, 700))
        
        extfid3 = ExtractRow()
        self.add(extfid3, QPointF(500, 300))
        
        plot2 = Plot1DDataNode()
        self.add(plot2, QPointF(800, 500))
        
        phase = PhaseNode()
        self.add(phase, QPointF(800, 0))
        
        extract_x = CropDataPPMNode()
        self.add(extract_x, QPointF(1200, 0))
        
        transpose1 = TransposeNode()
        self.add(transpose1, QPointF(1500, 0))
        
        sine2 = SineWindowNode()
        self.add(sine2, QPointF(1800, 0))
        
        zf2 = ZeroFillingNode()
        self.add(zf2, QPointF(2100, 0))
        
        ft2 = FourierTransformNode()
        self.add(ft2, QPointF(2400, 0))
        
        phase2 = PhaseNode()
        self.add(phase2, QPointF(2700, 0))
        
        extract_y = CropDataPPMNode()
        self.add(extract_y, QPointF(3000, 0))
        
        transpose2 = TransposeNode()
        self.add(transpose2, QPointF(3300, 0))
        
        plot2d = Plot2DDataNode()
        self.add(plot2d, QPointF(3600, 0))
        
        
        self.connect(import_node.outputs["data"].port, sine.parameters["data"].port)
        self.connect(import_node.outputs["data"].port, extfid2.parameters["data"].port)
        
        self.connect(sine.outputs["data"].port, zf.parameters["data"].port)
        self.connect(sine.outputs["data"].port, extfid1.parameters["data"].port)
        self.connect(sine.outputs["window"].port, math.parameters["a"].port)
        
        
        self.connect(list(extfid2.outputs.values())[0].port, plot1.parameters["data"].port)
        self.connect(list(extfid1.outputs.values())[0].port, plot1.parameters["data"].port)
        self.connect(list(math.outputs.values())[0].port, plot1.parameters["data"].port)
        
        
        self.connect(zf.outputs["data"].port, ft.parameters["data"].port)
        
        self.connect(list(ft.outputs.values())[0].port, extfid3.parameters["data"].port)
        self.connect(list(extfid3.outputs.values())[0].port, plot2.parameters["data"].port)
        
        self.connect(list(ft.outputs.values())[0].port, phase.parameters["data"].port)
        
        self.connect(list(phase.outputs.values())[0].port, extract_x.parameters["data"].port)
        
        self.connect(list(extract_x.outputs.values())[0].port, transpose1.parameters["data"].port)
        
        self.connect(list(transpose1.outputs.values())[0].port, sine2.parameters["data"].port)
        
        self.connect(list(sine2.outputs.values())[0].port, zf2.parameters["data"].port)
        
        self.connect(list(zf2.outputs.values())[0].port, ft2.parameters["data"].port)
        
        self.connect(list(ft2.outputs.values())[0].port, phase2.parameters["data"].port)
        
        self.connect(list(phase2.outputs.values())[0].port, extract_y.parameters["data"].port)
        
        self.connect(list(extract_y.outputs.values())[0].port, transpose2.parameters["data"].port)
        
        self.connect(list(transpose2.outputs.values())[0].port, plot2d.parameters["data"].port)
        
        
        return
    
    
    def _print_node_positions(self) -> None:
        for node in self.nodes:
            print(f"{node.title}: Position = {node.pos()}")
        return
