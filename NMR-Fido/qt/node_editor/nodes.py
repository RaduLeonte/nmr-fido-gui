from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

from qt.node_editor.Node import Node
from qt.node_editor.NodeParameter import NodeParameter


class EvaluateGraphNode(Node):
    title = "Evaluate graph"
    header_color = "#121212"
    
    def __init__(self, eval_function, node_to_eval: Node):
        self.eval_function = eval_function
        self.node_to_eval = node_to_eval
        super().__init__()
    
    
    def _build_custom_body(self) -> None:
        button = QPushButton("Evaluate graph")
        button.clicked.connect(lambda: self.eval_function(self.node_to_eval))
        self.node_body_layout.addWidget(button)
    
    
    def compute(self, inputs):
        return {}


class PlotDataNode(Node):
    title = "Plot data"
    header_color = "#121212"

    def __init__(self):
        super().__init__(node_structure={
            "parameters": [
                {"id": "data", "label": "Data", "data_type": "array", "input": True},
            ]
        })

    def compute(self, inputs):
        data = inputs["data"]
        print("PlotDataNode got data:", data)
        return {}
    

class ImportDataNode(Node):
    title = "Import data"
    header_color = "#121212"

    def __init__(self):
        super().__init__()

    def _build_custom_body(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        output_port = NodeParameter(
            param_type="output",
            label="Data",
            data_type="any",
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
        path = self.file_path_input.text()
        return {"output": inputs["path"]}
    

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

        # Display label for showing the result
        self.display_label = QLabel()
        self.node_body_layout.addWidget(self.display_label)

    def compute(self, inputs):
        print("PrintDataNode.compute() -> ", inputs)
        value = inputs["input"]
        self.display_label.setText(str(value) if value is not None else "None")
        return {}
    
    
class MathNode(Node):
    title = "Math"
    header_color = "#246283"

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
    
    

class ConstantIntNode(Node):
    title = "Integer"
    header_color = "#9c343e"

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