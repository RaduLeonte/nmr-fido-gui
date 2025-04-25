import numpy as np
import nmrglue as ng
import re

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from qt.node_editor.Node import Node
from qt.node_editor.NodeParameter import NodeParameter


class EvaluateGraphNode(Node):
    title = "Evaluate graph"
    header_color = "#121212"
    category = "Misc"
    
    def __init__(self, eval_function, nodes_to_eval: Node | list[Node]):
        self.eval_function = eval_function
        self.nodes_to_eval = nodes_to_eval
        super().__init__()
    
    
    def _build_custom_body(self) -> None:
        button = QPushButton("Evaluate graph")
        button.clicked.connect(self._on_evaluate_clicked)
        self.node_body_layout.addWidget(button)
    
    
    def _on_evaluate_clicked(self):
        if isinstance(self.nodes_to_eval, (list, tuple)):
            for node in self.nodes_to_eval:
                self.eval_function(node)
        else:
            self.eval_function(self.nodes_to_eval)
    
    
    def compute(self, inputs):
        return {}


class PlotDataNode(Node):
    title = "Plot data"
    header_color = "#121212"
    category = "Misc"

    def __init__(self):
        super().__init__()
        
    def _build_custom_body(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        input_port = NodeParameter(
            param_type="any",
            label="Data",
            data_type="any",
            input_port=True,
            output_port=False,
            proxy_ref=self,
            parent_node=self,
            port_id="data",
            accept_multiple_wires=True,
        )
        input_port.setObjectName("data")
        input_port.parent_node = self
        input_port.port_id = "data"
        self.parameters["data"] = input_port
        self.node_body_layout.addWidget(input_port)

        self.plot = pg.PlotWidget()
        plot_layout = pg.GraphicsLayout()
        self.plot.setCentralItem(plot_layout)
        layout.addWidget(self.plot)
        
        self.plot_ax = pg.PlotItem()
        self.plot_ax.getAxis("bottom").setTextPen("w")
        self.plot_ax.getAxis("left").setTextPen("w")
        self.plot_ax.getViewBox().setBackgroundColor("#1e1e1e")
        self.plot.setBackground(QColor(0, 0, 0, 0))
        plot_layout.addItem(self.plot_ax)

        self.node_body_layout.addLayout(layout)

    def compute(self, inputs):
        data_inputs = inputs["data"]
        print("PlotDataNode got data:", data_inputs)
        self.plot_ax.clear()
        for data in data_inputs:
            self.plot_ax.plot(data, pen='c')
        return {}
    

class ImportDataNode(Node):
    title = "Import data"
    header_color = "#121212"
    category = "File IO"

    def __init__(self, default_path: str=""):
        self.default_path = default_path
        super().__init__()

    def _build_custom_body(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        output_port = NodeParameter(
            param_type="output",
            label="Data",
            data_type="array",
            input_port=False,
            output_port=True,
            proxy_ref=self,
            parent_node=self,
            port_id="output",
        )
        output_port.setObjectName("output")
        output_port.parent_node = self
        output_port.port_id = "output"
        self.outputs["output"] = output_port
        self.node_body_layout.addWidget(output_port)

        self.file_path_input = QLineEdit()
        self.file_path_input.setText(self.default_path)
        self.parameters["path"] = self.file_path_input
        self.file_path_input.get_value = lambda: self.file_path_input.text()
        layout.addWidget(self.file_path_input)

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self._open_file_dialog)
        layout.addWidget(self.open_button)

        self.node_body_layout.addLayout(layout)

    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(caption="Select File")
        if file_path:
            self.file_path_input.setText(file_path)

    def compute(self, inputs):
        path = inputs["path"]
        
        dic, data = ng.pipe.read(path)
        return {"output": data}
    

class TestNode(Node):
    title = "Test node"
    header_color = "#707171"

    def __init__(self):
        super().__init__(node_structure={
            "parameters": [
                {"id": "input_int", "label": "Input int", "data_type": "int", "input": True},
                {"id": "input_float", "label": "Input float", "data_type": "float", "input": True},
                {"id": "input_str", "label": "Input str", "data_type": "str", "input": True},
                {"id": "dropdown", "label": "Dropdown", "data_type": "dropdown", "items": ["Option 1", "Option 2", "Option 3"]},
                {"id": "checkbox", "label": "Checkbox!", "data_type": "checkbox"},
            ],
            "outputs": [
                {"id": "output", "label": "Output", "data_type": "float"},
            ]
        })

    def compute(self, inputs):
        print("TestNode inputs:", inputs)
        return {"output": float(inputs.get("input_float", 0))}
    
    

class PrintDataNode(Node):
    title = "Display data"
    header_color = "#9c343e"
    category = "Misc"
    
    def __init__(self):
        super().__init__()  # no node_structure passed

    def _build_custom_body(self) -> None:
        # Create input port manually
        input_widget = NodeParameter(
            param_type="any",
            label="Data",
            data_type="any",
            input_port=True,
            proxy_ref=self
        )
        input_widget.setObjectName("input")
        input_widget.parent_node = self
        input_widget.port_id = "input"
        self.parameters["input"] = input_widget
        self.node_body_layout.addWidget(input_widget)

        self.display_area = QTextEdit()
        self.display_area.setReadOnly(True)  # Prevent user editing
        self.display_area.setMinimumHeight(50)  # Set a reasonable min size
        self.display_area.setMaximumHeight(300)  # Allow growth but cap it
        self.display_area.setSizePolicy(
            self.display_area.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Expanding
        )

        self.node_body_layout.addWidget(self.display_area)

    def compute(self, inputs):
        #print("PrintDataNode.compute() -> ", inputs)
        value = inputs["input"]
        text = str(value) if value is not None else "None"
        self.display_area.setPlainText(text)
        return {}
    

class MathNode(Node):
    title = "Math"
    header_color = "#246283"
    category = "Misc"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "mode", "label": None, "data_type": "dropdown", "items": ["Add", "Subtract", "Multiply", "Divide"]},
                    {"id": "a", "label": "A", "data_type": "float", "input": True},
                    {"id": "b", "label": "B", "data_type": "float", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Result", "data_type": "float"},
                ]
            }
        )

    def compute(self, inputs):
        print("MathNode.compute() -> ", inputs)
        match inputs["mode"]:
            case "Add":
                return {"result": inputs["a"] + inputs["b"]}
            
            case "Subtract":
                return {"result": inputs["a"] - inputs["b"]}
            
            case "Multiply":
                return {"result": inputs["a"] * inputs["b"]}
            
            case "Divide":
                return {"result": inputs["a"] / inputs["b"]}
    
"""
Constant value nodes
"""
#region Constants value nodes
class ConstantIntNode(Node):
    title = "Integer"
    header_color = "#9c343e"
    category = "Constant"

    def __init__(self):
        super().__init__(node_structure={
            "parameters": [
                {"id": "value", "label": None, "data_type": "int"},
            ],
            "outputs": [
                {"id": "output", "label": "Integer", "data_type": "int"},
            ]
        })

    def compute(self, inputs):
        print("ConstantIntNode.compute() -> ", inputs)
        return {"output": inputs["value"]}


class ConstantFloatNode(Node):
    title = "Float"
    header_color = "#9c343e"
    category = "Constant"

    def __init__(self):
        super().__init__(node_structure={
            "parameters": [
                {"id": "value", "label": None, "data_type": "float"},
            ],
            "outputs": [
                {"id": "output", "label": "Float", "data_type": "float"},
            ]
        })

    def compute(self, inputs):
        print("ConstantFloatNode.compute() -> ", inputs)
        return {"output": inputs["value"]}
#endregion Constants value nodes

"""
Processing
"""
class SineWindowNode(Node):
    title = "Sine window function"
    header_color = "#246283"
    category = "Apodization"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "offset", "label": "Offset", "data_type": "float", "default_value": 0.0, "input": True},
                    {"id": "end", "label": "End", "data_type": "float", "default_value": 1.0, "input": True},
                    {"id": "power", "label": "Power", "data_type": "int", "default_value": 1, "clamp": [0, 10], "input": True},
                    {"id": "c", "label": "Scale of first point", "data_type": "float", "default_value": 1.0, "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Data", "data_type": "array"},
                    {"id": "window", "label": "Window", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        """Adjustable sine-bell window function
        
        sp(x, i) = sin( pi*offset + pi*)

        Args:
            inputs (dict): Dictionary of node inputs

        Returns:
            dict: Output data
        """
        print("ApodizationNode.compute() -> ", inputs)
        
        data, off, end, power, c = (inputs[k] for k in ("data", "offset", "end", "power", "c"))
        
        window = np.power(
            data,
            power
        )
        
        result = data
        
        return {"result": result, "window": window}
    
    
class ExtractFIDNode(Node):
    title = "Extract FID"
    header_color = "#246283"
    category = "Misc"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "index", "label": "Index", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    {"id": "indices", "label": "Indices", "data_type": "str", "default_value": "", "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "output", "label": "FID", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        print("ExtractFID.compute() -> ", inputs)
        
        data, index, indices = (inputs[k] for k in ("data", "index", "indices"))

        if indices == "":
            return {"output": data[index]}
        else:
            cleaned_indices = indices.replace(" ", "")
            cleaned_indices = re.sub(r'[\[\]]+', ',', cleaned_indices)
            index_list = [int(i) for i in cleaned_indices.split(',') if i.strip().isdigit()]
            
            return {"output": data[tuple(index_list)]}
        
        
class DeleteImaginariesNode(Node):
    title = "Delete imaginaries"
    header_color = "#246283"
    category = "Misc"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "output", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):      
        data = inputs["data"]
        
        if np.iscomplexobj(data):
            return {"output": np.real(data)}

        return {"output": data}