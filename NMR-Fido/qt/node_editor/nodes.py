import numpy as np
import nmrglue as ng
import re

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from qt.node_editor.Node import Node
from qt.node_editor.NodeParameter import NodeParameter



class PlotDataNode(Node):
    title = "Plot data"
    header_color = "#121212"
    category = "Utilities"

    def __init__(self):
        super().__init__()
        
    def _build_custom_body(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        data_input_port = NodeParameter(
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
        data_input_port.setObjectName("data")
        data_input_port.parent_node = self
        data_input_port.port_id = "data"
        self.parameters["data"] = data_input_port
        self.node_body_layout.addWidget(data_input_port)
        
        scale_input_port = NodeParameter(
            param_type="array",
            label="Scale",
            data_type="array",
            input_port=True,
            output_port=False,
            proxy_ref=self,
            parent_node=self,
            port_id="scale",
            accept_multiple_wires=False,
        )
        scale_input_port.setObjectName("scale")
        scale_input_port.parent_node = self
        scale_input_port.port_id = "scale"
        self.parameters["scale"] = scale_input_port
        self.node_body_layout.addWidget(scale_input_port)

        self.plot = pg.PlotWidget()
        layout.addWidget(self.plot)
        
        self.plot.setBackground(QColor("#1e1e1e"))
        self.plot.getAxis("bottom").setTextPen("w")
        self.plot.getAxis("left").setTextPen("w")

        self.node_body_layout.addLayout(layout)

    def compute(self, inputs):
        data_inputs = inputs["data"]
        scale = inputs["scale"]
        #print("PlotDataNode got data:", data_inputs)
        self.plot.clear()
        
        color_cycle = ['c', 'm', 'y', 'r', 'g', 'b', 'w']
        for i, data in enumerate(data_inputs):
            if data is None:
                continue
            
            color = color_cycle[i % len(color_cycle)]
            
            if scale is None:
                scale = np.arange(data.shape[0])
                
            if scale[0] > scale[-1]:
                self.plot.getViewBox().invertX(True)
                
            self.plot.plot(scale, np.real(data), pen=color)

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
        
        output_port1 = NodeParameter(
            param_type="output",
            label="Data",
            data_type="array",
            input_port=False,
            output_port=True,
            proxy_ref=self,
            parent_node=self,
            port_id="data",
        )
        output_port1.setObjectName("data")
        output_port1.parent_node = self
        output_port1.port_id = "data"
        self.outputs["data"] = output_port1
        self.node_body_layout.addWidget(output_port1)
        
        output_port2 = NodeParameter(
            param_type="output",
            label="Dic",
            data_type="any",
            input_port=False,
            output_port=True,
            proxy_ref=self,
            parent_node=self,
            port_id="dic",
        )
        output_port2.setObjectName("dic")
        output_port2.parent_node = self
        output_port2.port_id = "dic"
        self.outputs["dic"] = output_port2
        self.node_body_layout.addWidget(output_port2)

        self.file_path_input = QLineEdit()
        self.file_path_input.setText(self.default_path)
        self.parameters["path"] = self.file_path_input
        self.file_path_input.get_value = lambda: self.file_path_input.text()
        self.file_path_input.textChanged.connect(self._on_widget_changed)
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
        #udic = ng.pipe.guess_udic(dic, data)
        return {"data": data, "dic": dic}
    

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
        #print("TestNode inputs:", inputs)
        return {"output": float(inputs.get("input_float", 0))}
    
    

class PrintDataNode(Node):
    title = "Display data"
    header_color = "#9c343e"
    category = "Utilities"
    
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
    category = "Math"

    def __init__(self, default_values=[None, None], default_mode=None):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "mode", "label": None, "data_type": "dropdown", "default_value": default_mode, "items": ["Add", "Subtract", "Multiply", "Divide"]},
                    {"id": "a", "label": "A", "data_type": "float", "default_value": default_values[0], "input": True},
                    {"id": "b", "label": "B", "data_type": "float", "default_value": default_values[1], "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Result", "data_type": "float"},
                ]
            }
        )

    def compute(self, inputs):
        #print("MathNode.compute() -> ", inputs)
        match inputs["mode"]:
            case "Add":
                return {"result": inputs["a"] + inputs["b"]}
            
            case "Subtract":
                return {"result": inputs["a"] - inputs["b"]}
            
            case "Multiply":
                return {"result": inputs["a"] * inputs["b"]}
            
            case "Divide":
                return {"result": inputs["a"] / inputs["b"]}
            
class MinMaxNode(Node):
    title = "Get min/max"
    header_color = "#246283"
    category = "Math"

    def __init__(self, default_values=[None, None], default_mode=None):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "mode", "label": None, "data_type": "dropdown", "default_value": default_mode, "items": ["Min", "Max"]},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Result", "data_type": "float"},
                ]
            }
        )

    def compute(self, inputs):
        data, mode = (inputs[k] for k in ("data", "mode"))
        
        
        if mode == "Min":
            return {"result": min(data)}
        else:
            return {"result": max(data)}
    
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
        #print("ConstantIntNode.compute() -> ", inputs)
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
        #print("ConstantFloatNode.compute() -> ", inputs)
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
                    {"id": "offset", "label": "Offset", "data_type": "float", "default_value": 0.5, "input": True},
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
        
        data, off, end, power, c = (inputs[k] for k in ("data", "offset", "end", "power", "c"))
        
        size = data.shape[-1]
        
        window = np.power(
            np.sin(np.pi*off + np.pi*(end - off)*np.arange(size) / (size - 1)).astype(data.dtype),
            power
        ).astype(data.dtype)
        
        result = data * window
        
        result[..., 0] = result[..., 0] * c
        
        return {"result": result, "window": window}
    

class ZeroFillingNode(Node):
    title = "Zero filling"
    header_color = "#246283"
    category = "Processing"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "double_count", "label": "Double count", "data_type": "int", "default_value": 1, "clamp": [0, 100], "input": True},
                    {"id": "pad", "label": "Pad", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    {"id": "final_size", "label": "Final size", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        data, double_count, pad, final_size = (inputs[k] for k in ("data", "double_count", "pad", "final_size"))
        
        current_size = data.shape[-1]
        pad_config = [(0, 0)] * data.ndim
        zeroes_to_add = 0
        
        if double_count != 0:
            zeroes_to_add = current_size*(2**double_count) - current_size
        elif pad != 0:
            zeroes_to_add = pad
        elif final_size != 0:
            zeroes_to_add = final_size - current_size
            
        if zeroes_to_add > 0:
            pad_config[-1] = (0, zeroes_to_add)

            if np.iscomplexobj(data):
                pad_value = 0 + 0j
            else:
                pad_value = 0

            result = np.pad(data, pad_config, mode='constant', constant_values=pad_value)
        else:
            result = data  # no padding

        return {"result": result}
    
    
class PhaseNode(Node):
    title = "Phase"
    header_color = "#246283"
    category = "Processing"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "p1", "label": "P1", "data_type": "float", "default_value": 0.0, "input": True},
                    {"id": "p2", "label": "P2", "data_type": "float", "default_value": 0.0, "input": True},
                    {"id": "pivot", "label": "Pivot", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        data, p1, p2, pivot = (inputs[k] for k in ("data", "p1", "p2", "pivot"))
        
        if data is None or not isinstance(data, (list, np.ndarray)):
            return {"result": None}
        
        
        size = data.shape[-1]
        x = np.arange(size) - pivot
        phase = np.deg2rad(p1 + p2*(x/size))
        phase_correction = np.exp(1j * phase)
        
        result = data * phase_correction
        
        return {"result": result}



class FourierTransformNode(Node):
    title = "Fourier transform"
    header_color = "#246283"
    category = "Processing"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "inverse", "label": "Inverse", "data_type": "checkbox", "default_value": False, "input": True},
                    {"id": "sign_alternation", "label": "Use sign alternation", "data_type": "checkbox", "default_value": False, "input": True},
                    {"id": "negate_imaginaries", "label": "Negate imaginaries", "data_type": "checkbox", "default_value": False, "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "result", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        data, inverse, sign_alternation, negate_imaginaries = (
            inputs[k] for k in ("data", "inverse", "sign_alternation", "negate_imaginaries")
        )
        
        result = data
        
        if inverse:
            result = np.fft.ifft(result, axis=-1)
        else:
            result = np.fft.fftshift(np.fft.fft(result, axis=-1).astype(data.dtype), -1)
            
        if sign_alternation:
            n = result.shape[-1]
            alternator = np.power(-1, np.arange(n))
            result = result * alternator
            
        if negate_imaginaries and np.iscomplexobj(result):
            result = result.real - 1j * result.imag
        
        return {"result": result}


class ExtractFIDNode(Node):
    title = "Extract FID"
    header_color = "#246283"
    category = "Utilities"

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
        #print("ExtractFID.compute() -> ", inputs)
        
        data, index, indices = (inputs[k] for k in ("data", "index", "indices"))
        
        if data is None:
            return {"output": None}

        try:
            if indices == "" and index is not None and type(index) is int:
                size = data.shape[0]
                print(size, size - 1)
                return {"output": data[min(max(index, 0), size - 1)]}
            else:
                cleaned_indices = indices.replace(" ", "")
                cleaned_indices = re.sub(r'[\[\]]+', ',', cleaned_indices)
                index_list = [int(i) for i in cleaned_indices.split(',') if i.strip().isdigit()]
                
                return {"output": data[tuple(index_list)]}
        except IndexError:
            return {"output": data}
        
        
class DeleteImaginariesNode(Node):
    title = "Delete imaginaries"
    header_color = "#246283"
    category = "Processing"

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


class GetPPMScale(Node):
    title = "Get PPM scale"
    header_color = "#246283"
    category = "Utilities"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "dim", "label": "Dimension", "data_type": "int", "clamp": [0, np.inf], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                    {"id": "dic", "label": "Dic", "data_type": "any", "input": True},
                ],
                "outputs": [
                    {"id": "output", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        dim = inputs["dim"]
        data = inputs["data"]      
        dic = inputs["dic"]
        
        if dim is None or data is None or dic is None:
            return {"output": None}
        
        udic = ng.pipe.make_uc(dic, data, dim=dim)
        scale_limits = udic.ppm_limits()
        scale = np.linspace(scale_limits[0], scale_limits[1], data.shape[dim])
        
        print("scale", len(scale))

        return {"output": scale}
    

class CropDataPointsNode(Node):
    title = "Crop data (points)"
    header_color = "#246283"
    category = "Utilities"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "start_index", "label": "Start index", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    {"id": "end_index", "label": "End index", "data_type": "int", "default_value": 0, "clamp": [0, np.inf], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "output", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):      
        data, start_index, end_index = (inputs[k] for k in ("data", "start_index", "end_index"))
        
        if data is None:
            return {"output": None}
        
        if start_index >= end_index:
            return {"output": data}
        else:
            return {"output": data[start_index: end_index]}
        
        
class CropDataFractionNode(Node):
    title = "Crop data (fraction)"
    header_color = "#246283"
    category = "Utilities"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "start_fraction", "label": "Start fraction", "data_type": "float", "default_value": 0.0, "clamp": [0,1.0], "input": True},
                    {"id": "end_fraction", "label": "End fraction", "data_type": "float", "default_value": 1.0, "clamp": [0, 1.0], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "output", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):      
        data, start_fraction, end_fraction = (inputs[k] for k in ("data", "start_fraction", "end_fraction"))
        
        if data is None:
            return {"output": None}
        
        if start_fraction >= end_fraction:
            return {"output": data}
        else:
            size = data.shape[-1]
            start_index = int(size*start_fraction)
            end_index = int(size*end_fraction)
            return {"output": data[start_index: end_index]}