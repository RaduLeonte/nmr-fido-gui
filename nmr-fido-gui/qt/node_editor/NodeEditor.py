import sys
import os
import numpy as np
import importlib
import inspect
import time
import traceback
import json


from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from qt.node_editor.Node import Node
from qt.node_editor.nodes import *
from qt.node_editor.Wire import Wire
from qt.node_editor.Port import Port

class NodeEditor(QGraphicsView):
    def __init__(self, parent_container: QWidget, scene_size: tuple=(10_000, 5_000), background_color: str="#1d1d1d"):
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
        
        
        self.parent_container = parent_container
        self._graph_path = ""
        self._file_name = "untitled" 
        self._unsaved_changes = False
        self._update_container_title()
        
        
        self._autosave_timer = QTimer()
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(30 * 1E3)  # s
        self._autosave_path = ".autosave.json"
        
        self._init_context_menu()
        self._update_cursor()
        
        self._allow_graph_evaluation = False
        
        
    def _update_container_title(self):
        if self._graph_path:
            self._file_name = os.path.basename(self._graph_path)
        else:
            self._file_name = "untitled"
        
        base_name = self._file_name
        if self._unsaved_changes:
            base_name = base_name + "*"

        self.parent_container.setTitle(f'Node Editor - {base_name}')
    
    
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

        """ Add nodes menu """
        self.add_node_menu = self.context_menu.addMenu("Add Node")
        self.node_class_map = self._load_nodes()
        for category, class_list in self.node_class_map.items():
            category_menu = self.add_node_menu.addMenu(category)
            for cls in class_list:
                action = QAction(cls.title, self)
                action.triggered.connect(lambda checked=False, cls=cls: self._spawn_node(cls))
                category_menu.addAction(action)
        
        
        self.context_menu.addSeparator()


        """ Viewer actions """
        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.triggered.connect(self.reset_zoom)
        self.context_menu.addAction(reset_zoom_action)
        
        
        self.context_menu.addSeparator()

        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_graph_dialog)
        self.context_menu.addAction(open_action)
        
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_graph)
        self.context_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_graph_dialog)
        self.context_menu.addAction(save_as_action)

        
        """ Debug menu """
        debug_menu = self.context_menu.addMenu("Debug")
        
        # Print node positions
        print_node_pos = QAction("Print node positions", self)
        print_node_pos.triggered.connect(self._print_node_positions)
        debug_menu.addAction(print_node_pos)
        
        # Init position of context menu in scene
        self._context_menu_scene_pos = QPointF()
        return
    
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        item = self.itemAt(event.pos())

        if item is None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._context_menu_scene_pos = self.mapToScene(event.pos())
            self.context_menu.popup(event.globalPos())
        return
    
    
    #region Events
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._allow_graph_evaluation:
            QTimer.singleShot(0, self._mark_ready)
        return
    
    def _mark_ready(self) -> None:
        self._allow_graph_evaluation= True
        self.trigger_evaluation()
        return 
    
    
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
        
        self._update_cursor()
    

    #region Mouse press
    def mousePressEvent(self, event):
        # If clicking on a plot widget, send the event to the widget
        if self._forward_event_to_plotwidget(event):
            return
        
        
        """ Mouse wheel -> Start pan"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start = event.position().toPoint()
            event.accept()
            self._update_cursor()
            return
        
        
        """ CTRL + Right click -> Start wire cutting"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.button() == Qt.MouseButton.RightButton
        ):
            self._cutting = True
            self._cut_points = [self.mapToScene(event.position().toPoint())]
            self._cut_path = QGraphicsPathItem()
            self._cut_path.setZValue(1000)  # Always on top
            self._cut_path.setPen(QPen(QColor("#ff5555"), 2, Qt.PenStyle.DashLine))
            self.scene().addItem(self._cut_path)
            event.accept()
            return


        """ Default """
        scene_pos = self.mapToScene(event.position().toPoint())
        clicked_item = self.itemAt(event.position().toPoint())
        
        """ Check for clicking inside input fields """
        if isinstance(clicked_item, Node):
            proxy = clicked_item  # QGraphicsProxyWidget
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
        
        # Save selection
        original_selection = set(self.scene().selectedItems())
        
        super().mousePressEvent(event)
        self._update_cursor()

        """ Single click on Node"""
        self._pressed_item = self.itemAt(event.position().toPoint())
        if isinstance(self._pressed_item, Node):
            if self._pressed_item in original_selection:
                """ Node is already in selection """
                # Reselect everything
                for item in original_selection:
                    item.setSelected(True)
                
                # If the shift key is pressed -> remove Node from selection
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self._pressed_item.setSelected(False)
            else:
                """ Node is not already in the selection"""
                
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift -> add Node to selection
                    self._pressed_item.setSelected(True)
                    
                    # Reselect everything
                    for item in original_selection:
                        item.setSelected(True)
                else:
                    # Default ->  Clear selection and select only pressed Node
                    self.scene().clearSelection()
                    self._pressed_item.setSelected(True)
        else:
            """ Clicked outside a node -> deselect everything"""
            self.scene().clearSelection()


        # Prepare for dragging multiple nodes
        self._selected_item_offsets.clear()
        scene_pos = self.mapToScene(event.position().toPoint())
        for item in self.scene().selectedItems():
            if isinstance(item, Node):
                self._selected_item_offsets[item] = item.pos() - scene_pos
                
        return

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
            self._update_cursor()
            
  
    #region Mouse release
    def mouseReleaseEvent(self, event) -> None:
        if self._forward_event_to_plotwidget(event):
            return
        
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            event.accept()
            self._update_cursor()
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
            self._update_cursor()
            return
        
        self._pressed_item = None
        self._selected_item_offsets.clear()
        super().mouseReleaseEvent(event)
        self._update_cursor()
        return
    
    def _update_cursor(self) -> None:
        if self._is_panning or self._pending_node is not None:
            cursor = Qt.CursorShape.SizeAllCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        
        #print(f"NodeEditor._update_cursor() -> {cursor=}")
        self.setCursor(cursor)
        
        return


    #region Key press
    def keyPressEvent(self, event: QKeyEvent):
        """Del | X -> Delete selected nodes"""
        if (
            event.key() == Qt.Key.Key_Delete or
            event.key() == Qt.Key.Key_X
        ):
            self._allow_graph_evaluation = False
            for item in self.scene().selectedItems():
                if isinstance(item, Node):
                    self.remove(item)
            self._allow_graph_evaluation = True
            self.trigger_evaluation()
            event.accept()
            return
        
        
        """CTRL + C -> Copy nodes"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_C
        ):
            self._copy_nodes()
            event.accept()
            return
        """CTRL + V -> Paste nodes"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_V
        ):
            self._paste_nodes()
            event.accept()
            return
        
        
        """CTRL + R -> Trigger graph evaluation"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_R
        ):
            self.trigger_evaluation()
            event.accept()
            return
        
        
        """CTRL + O -> Open/load graph"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_O
        ):
            self.open_graph_dialog()
            event.accept()
            return
        
        """CTRL + S -> Save graph to current file"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.key() == Qt.Key.Key_S
        ):
            self.save_graph()
            event.accept()
            return
        
        """CTRL + Shift + S -> Save graph to current file"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier and
            event.key() == Qt.Key.Key_S
        ):
            self.save_graph_dialog()
            event.accept()
            return
        
        
        """SHIFT + A"""
        if (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier and
            event.key() == Qt.Key.Key_A
        ):
            
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

    #region Copy nodes
    def _copy_nodes(self) -> None:
        selected_nodes = [node for node in self.nodes if node.isSelected()]
        selected_node_set = set(selected_nodes)

        copied_data = {
            "nodes": [],
            "connections": []
        }

        node_id_map = {node: idx for idx, node in enumerate(selected_nodes)}

        # Save selected nodes
        for node in selected_nodes:
            node_data = {
                "id": node_id_map[node],
                "class": node.__class__.__name__,
                "pos": [node.pos().x(), node.pos().y()],
                "parameters": {}
            }

            for param_id, param in node.parameters.items():
                try:
                    value = param.get_value()
                    node_data["parameters"][param_id] = value
                except Exception as e:
                    print(f"Warning: Could not copy param {param_id}: {e}")

            copied_data["nodes"].append(node_data)

        # Save internal connections
        for item in self.scene().items():
            if isinstance(item, Wire):
                output_node = item.output_port.parent_node
                input_node = item.input_port.parent_node

                if output_node in selected_node_set and input_node in selected_node_set:
                    copied_data["connections"].append({
                        "output_node_id": node_id_map[output_node],
                        "output_port_id": item.output_port.port_id,
                        "input_node_id": node_id_map[input_node],
                        "input_port_id": item.input_port.port_id
                    })

        self._copied_nodes = copied_data
        
        return
    
    
    #region Paste nodes
    def _paste_nodes(self) -> None:
        if not self._copied_nodes:
            return

        cursor_pos = QCursor.pos()
        scene_center = self.mapToScene(self.mapFromGlobal(cursor_pos))

        copied_data = self._copied_nodes
        node_id_map = {}  # copied id -> new node instance

        nodes = copied_data["nodes"]

        # Calculate group center
        bounding_rect = QRectF()
        first = True
        for node_data in nodes:
            pos = QPointF(*node_data["pos"])
            if first:
                bounding_rect = QRectF(pos, QSizeF(1, 1))
                first = False
            else:
                bounding_rect = bounding_rect.united(QRectF(pos, QSizeF(1, 1)))
        group_center = bounding_rect.center()

        # Create new nodes
        for node_data in nodes:
            cls_name = node_data["class"]
            cls = self._find_node_class_by_name(cls_name)
            if cls is None:
                print(f"Warning: Node class {cls_name} not found.")
                continue

            new_node = cls()
            new_node.node_editor = self

            # Position relative to group center
            original_pos = QPointF(*node_data["pos"])
            offset = original_pos - group_center
            new_node.setPos(scene_center + offset)

            # Restore parameters
            for param_id, value in node_data.get("parameters", {}).items():
                param = new_node.parameters.get(param_id)
                if param is None:
                    continue
                try:
                    if hasattr(param, "_value_widget") and param._value_widget:
                        if hasattr(param._value_widget, "setValue"):
                            param._value_widget.setValue(value)
                        elif isinstance(param._value_widget, QLineEdit):
                            param._value_widget.setText(value)
                        elif isinstance(param._value_widget, QComboBox):
                            param._value_widget.setCurrentText(value)
                        elif isinstance(param._value_widget, QCheckBox):
                            param._value_widget.setChecked(value)
                    elif isinstance(param, QLineEdit):
                        param.setText(value)
                    elif isinstance(param, QComboBox):
                        param.setCurrentText(value)
                    elif isinstance(param, QCheckBox):
                        param.setChecked(value)
                except Exception as e:
                    print(f"Warning: Could not paste param {param_id}: {e}")

            self.graphics_scene.addItem(new_node)
            self.nodes.append(new_node)
            node_id_map[node_data["id"]] = new_node

        # Now reconnect wires
        for conn in copied_data.get("connections", []):
            output_node = node_id_map.get(conn["output_node_id"])
            input_node = node_id_map.get(conn["input_node_id"])

            if not output_node or not input_node:
                continue

            output_param = output_node.outputs.get(conn["output_port_id"])
            input_param = input_node.parameters.get(conn["input_port_id"])

            if output_param and input_param:
                output_port = output_param.port
                input_port = input_param.port
                if output_port and input_port:
                    self.connect(output_port, input_port)

        self.scene().clearSelection()
        for node in node_id_map.values():
            node.setSelected(True)

        return
    
    
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
        self._update_cursor()
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
    
    #region Save graph
    def save_graph_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Node Graph", "", "JSON Files (*.json)")
        if path:
            if not path.endswith(".json"):
                path += ".json"
            self.save_graph(path)
    
    
    def save_graph(self, path: str = None) -> None:
        if path is None:
            path = self._graph_path

        if not path:
            self.save_graph_dialog()
            return

        data = {
            "nodes": []
        }
        node_id_map = {}

        for idx, node in enumerate(self.nodes):
            node_id_map[node] = idx

        for node in self.nodes:
            node_data = {
                "id": node_id_map[node],
                "class": node.__class__.__name__,
                "pos": [node.pos().x(), node.pos().y()],
                "parameters": {},
                "inputs": {}
            }

            for param_id, param in node.parameters.items():
                try:
                    value = param.get_value()
                    node_data["parameters"][param_id] = value
                except Exception as e:
                    print(f"Warning: Could not save param {param_id}: {e}")

                if hasattr(param, "port") and param.port and param.port.port_type == "input":
                    port = param.port
                    if port.accept_multiple_wires:
                        wires = port.connected_wires
                    else:
                        wires = [port.connected_wire] if port.connected_wire else []

                    node_data["inputs"][param_id] = []
                    for wire in wires:
                        if wire is None:
                            continue
                        source_node = wire.output_port.parent_node
                        source_port_id = wire.output_port.port_id
                        node_data["inputs"][param_id].append({
                            "source_node_id": node_id_map.get(source_node),
                            "source_port_id": source_port_id
                        })

            data["nodes"].append(node_data)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        self._graph_path = path
        self._unsaved_changes = False
        self._update_container_title()
        
        print(f"NodeEditor.save_graph() -> Saved graph to {path}")
        return
    
    
    def _autosave(self) -> None:
        if not self._unsaved_changes:
            return
        
        self.save_graph(self._autosave_path)
        return
    
    
    #region Load graph
    def open_graph_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Node Graph", "", "JSON Files (*.json)")
        if path:
            self.load_graph(path)
    
    def load_graph(self, path: str) -> None:
        with open(path, "r") as f:
            data = json.load(f)

        self._allow_graph_evaluation = False
        self.clear_scene()
        node_id_map = {}

        for node_data in data["nodes"]:
            cls_name = node_data["class"]
            cls = self._find_node_class_by_name(cls_name)
            if cls is None:
                print(f"Warning: Node class {cls_name} not found.")
                continue

            node = cls()
            self.add(node, QPointF(*node_data["pos"]))
            node_id_map[node_data["id"]] = node

            for param_id, value in node_data.get("parameters", {}).items():
                param = node.parameters.get(param_id)
                if param is None:
                    continue
                try:
                    if isinstance(param, NodeParameter):
                        widget = param._value_widget
                        if widget:
                            if hasattr(widget, "setValue"):
                                widget.setValue(value)
                            elif isinstance(widget, QLineEdit):
                                widget.setText(value)
                            elif isinstance(widget, QComboBox):
                                widget.setCurrentText(value)
                            elif isinstance(widget, QCheckBox):
                                widget.setChecked(value)
                    elif isinstance(param, QLineEdit):
                        param.setText(value)
                    elif isinstance(param, QComboBox):
                        param.setCurrentText(value)
                    elif isinstance(param, QCheckBox):
                        param.setChecked(value)
                except Exception as e:
                    print(f"Warning: Could not restore param {param_id}: {e}")


        for node_data in data["nodes"]:
            input_node = node_id_map.get(node_data["id"])
            if not input_node:
                continue

            for param_id, connections in node_data.get("inputs", {}).items():
                input_param = input_node.parameters.get(param_id)
                if not input_param:
                    continue
                input_port = input_param.port
                if not input_port:
                    continue

                for conn in connections:
                    source_node = node_id_map.get(conn["source_node_id"])
                    if not source_node:
                        continue
                    output_param = source_node.outputs.get(conn["source_port_id"])
                    if not output_param:
                        continue
                    output_port = output_param.port
                    if not output_port:
                        continue

                    self.connect(output_port, input_port)

        self._graph_path = path
        self._unsaved_changes = False
        self._update_container_title()
        
        self._allow_graph_evaluation = True
        self.trigger_evaluation()
        
        print(f"NodeEditor.load_graph() -> Loaded graph from {path}")
        return
    
    
    def _find_node_class_by_name(self, class_name: str):
        for class_list in self.node_class_map.values():
            for cls in class_list:
                if cls.__name__ == class_name:
                    return cls
        return None
    
    
    def clear_scene(self) -> None:
        for node in list(self.nodes):
            self.remove(node)

        self.nodes.clear()
        self.cache.clear()


        for item in self.scene().items():
            if isinstance(item, Wire):
                item.remove()

        self.scene().clearSelection()
        self.scene().update()
        return
    
    
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
        if not self._allow_graph_evaluation:
            return
        
        self.evaluate_graph()
        return


    def evaluate_graph(self):
        start = time.time()
        self._allow_graph_evaluation = False
        
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
        self._allow_graph_evaluation = True
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
