from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

from qt.node_editor.Node import *


class EvaluateGraphNode(Node):
    title = "Evaluate graph"
    header_color = "#121212"
    
    def __init__(self, graph_ref):
        self.graph_ref = graph_ref
        super().__init__()
    
    
    def _build_custom_body(self) -> None:
        button = QPushButton("Evaluate graph")
        display_node = next((obj for obj in self.graph_ref.nodes if isinstance(obj, PrintDataNode)), None)
        button.clicked.connect(lambda: self.graph_ref.evaluate(display_node))
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
        super().__init__(node_structure={
            "outputs": [
                {"id": "data", "label": "Data", "data_type": "array"},
            ]
        })

    def _build_custom_body(self) -> None:
        super()._build_custom_body()  # optional if you want to add default structure
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        self.file_path_input = QLineEdit()
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
        try:
            with open(path) as f:
                data = f.read()
            return {"data": data}
        except Exception as e:
            print("Failed to read file:", e)
            return {"data": None}
    

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
        input_widget = NodeParameterWidget(
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
        return {"result": inputs["a"] + inputs["b"]}
    
    

class ConstantIntNode(Node):
    title = "Constant integer"
    header_color = "#9c343e"

    def __init__(self):
        super().__init__(node_structure={
            "parameters": [
                {"id": "value", "label": "Value", "data_type": "int"},
            ],
            "outputs": [
                {"id": "output", "label": "Integer", "data_type": "int"},
            ]
        })

    def compute(self, inputs):
        print("ConstantIntNode.compute() -> ", inputs)
        return {"output": inputs["value"]}