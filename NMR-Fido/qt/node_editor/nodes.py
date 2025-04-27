import numpy as np
import nmrglue as ng
import re
from skimage import measure
import os
import glob

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from qt.node_editor.Node import Node
from qt.node_editor.NodeParameter import NodeParameter
from qt.node_editor.NMRData import NMRData



class Plot1DDataNode(Node):
    title = "Plot 1D data"
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
            data_type="array",
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
        scale = inputs.get("scale", None)
        self.plot.clear()
        
        if scale is not None and scale.ndim != 1 or np.iscomplex(scale).any():
            scale = None
        
        color_cycle = ['c', 'm', 'y', 'r', 'g', 'b', 'w']
        for i, data in enumerate(data_inputs):
            if data is None or data.ndim != 1:
                continue
                
            
            color = color_cycle[i % len(color_cycle)]
            
            if isinstance(data, NMRData):
                scale = data.scales[data.ndim]
            
            if scale is None:
                local_scale = np.arange(data.shape[0])
            else:
                # If a scale was provided, resize it to match the data length
                if len(scale) == data.shape[0]:
                    local_scale = scale
                else:
                    local_scale = np.linspace(scale[0], scale[-1], num=data.shape[0])
            
            if local_scale[0] > local_scale[-1]:
                self.plot.getViewBox().invertX(True)
            
            self.plot.plot(local_scale, np.real(data), pen=color)

        return {}


class Plot2DDataNode(Node):
    title = "Plot 2D data"
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
            data_type="array",
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
        

        self.plot = pg.PlotWidget()
        layout.addWidget(self.plot)
        
        self.plot.setBackground(QColor("#1e1e1e"))
        self.plot.getAxis("bottom").setTextPen("w")
        self.plot.getAxis("left").setTextPen("w")

        self.node_body_layout.addLayout(layout)
        
    def _median_absolute_deviation(self, data, k=1.4826):
        """ Median Absolute Deviation: a "Robust" version of standard deviation.
            Indices variabililty of the sample.
            https://en.wikipedia.org/wiki/Median_absolute_deviation
        """
        data = np.ma.array(data).compressed()
        median = np.median(data)
        return k*np.median(np.abs(data - median))

    def compute(self, inputs):
        data_inputs = inputs["data"]
        self.plot.clear()
        
        
        color_cycle = ['c', 'm', 'y', 'r', 'g', 'b', 'w']
        
        for i, data in enumerate(data_inputs):
            if data is None or data.ndim != 2:
                continue

            data = np.real(data)
            color = color_cycle[i % len(color_cycle)]
            base_level = self._median_absolute_deviation(data, k=4)
            levels = [base_level*(1.1**j) for j in range(10)]

            path = QPainterPath()

            for level in levels:
                contours = measure.find_contours(data, level=level)
                for contour in contours:
                    if contour.shape[0] < 2:
                        continue  # Ignore tiny junk
                    path.moveTo(contour[0, 1], contour[0, 0])
                    for pt in contour[1:]:
                        path.lineTo(pt[1], pt[0])

            item = QGraphicsPathItem(path)
            item.setPen(pg.mkPen(color=color, width=1))
            item.setZValue(10 + i)
            self.plot.addItem(item)

        return {}


class ImportDataNode(Node):
    title = "Import data"
    header_color = "#121212"
    category = "File IO"

    def __init__(self, default_path: str=""):
        self.default_path = default_path
        super().__init__()

    def _build_custom_body(self) -> None:
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


        self.open_file_button = QPushButton("Open file")
        self.open_file_button.clicked.connect(self._open_file_dialog)
        self.node_body_layout.addWidget(self.open_file_button)
        
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.clicked.connect(self._open_folder_dialog)
        self.node_body_layout.addWidget(self.open_folder_button)
        
        
        self.file_path_input = QLineEdit()
        self.file_path_input.setText(self.default_path)
        self.parameters["path"] = self.file_path_input
        self.file_path_input.get_value = lambda: self.file_path_input.text()
        self.file_path_input.textChanged.connect(self._on_widget_changed)
        self.node_body_layout.addWidget(self.file_path_input)
        
        return


    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(caption="Select File")
        if file_path:
            self.file_path_input.setText(file_path)

    def _open_folder_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(caption="Select Folder")
        if folder_path:
            self.file_path_input.setText(folder_path)

    def compute(self, inputs):
        path = inputs["path"]
        
        if os.path.isfile(path):
            # It's a file -> read normally
            dic, data = ng.pipe.read(path)
            return {"data": NMRData(data, dic=dic)}
        
        elif os.path.isdir(path):
            # It's a folder -> find all .fid files
            fid_files = sorted(glob.glob(os.path.join(path, "*.fid")))
            planes = []
            
            for fid_file in fid_files:
                dic, plane_data = ng.pipe.read(fid_file)
                if plane_data.ndim != 2:
                    raise ValueError(f"Expected 2D data in {fid_file}, got shape {plane_data.shape}")
                planes.append(plane_data)
            
            if not planes:
                raise ValueError(f"No .fid files found in folder {path}")

            
            data = np.stack(planes, axis=0)

            return {"data": NMRData(data, dic=dic)}
        else:
            raise ValueError(f"Invalid path: {path}")
    

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
        return {"output": float(inputs.get("input_float", 0))}
    
    

class PrintDataNode(Node):
    title = "Print data"
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
        value = inputs["input"]
        if value is None:
            text = "None"
        else:
            text = str(type(value)) + "\n" + str(value)
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
                    {"id": "data", "label": "Result", "data_type": "float"},
                ]
            }
        )

    def compute(self, inputs):
        mode, a, b = (inputs[k] for k in ("mode", "a", "b"))
        
        match mode:
            case "Add":
                return {"data": a + b}
            
            case "Subtract":
                return {"data": a - b}
            
            case "Multiply":
                return {"data": a * b}
            
            case "Divide":
                return {"data": a / b}


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
                    {"id": "data", "label": "Result", "data_type": "float"},
                ]
            }
        )

    def compute(self, inputs):
        data, mode = (inputs[k] for k in ("data", "mode"))
        
        if mode == "Min":
            return {"data": min(data)}
        else:
            return {"data": max(data)}
    
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
        return {"output": inputs["value"]}
#endregion Constants value nodes

"""
Processing
"""
class SineWindowNode(Node):
    title = "Sine window function"
    header_color = "#1d725e"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
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
        
        
        if data is None:
            return {"data": None, "window": None}
        
        size = data.shape[-1]
        
        window = np.power(
            np.sin(np.pi*off + np.pi*(end - off)*np.arange(size) / (size - 1)).astype(data.dtype),
            power
        ).astype(data.dtype)
        
        
        result = data * window
        
        result[..., 0] = result[..., 0] * c
        
        if isinstance(data, NMRData):
            result = NMRData(result, scales=data.scales, dic=data.dic)
        
        return {"data": result, "window": window}
    

class ZeroFillingNode(Node):
    title = "Zero filling"
    header_color = "#1d725e"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
    
    
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")


    def compute(self, inputs: dict):
        data, double_count, pad, final_size = (inputs[k] for k in ("data", "double_count", "pad", "final_size"))
        
        self._set_input_label()
        self._set_output_label()
        
        if data is None:
            return {"data": None}
        self._set_input_label(data.shape)
        
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

        
        if isinstance(data, NMRData):
            scales = data.scales.copy()
            scales[-1] = np.arange(0, result.shape[-1])
            
            result = NMRData(result, scales=scales, scale_units=data.scale_units, dic=data.dic)
            
        
        self._set_output_label(result.shape)
        return {"data": result}
    
    
class PhaseNode(Node):
    title = "Phase"
    header_color = "#1d725e"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        data, p1, p2, pivot = (inputs[k] for k in ("data", "p1", "p2", "pivot"))
        
        if data is None:
            return {"data": None}
        
        
        size = data.shape[-1]
        x = np.arange(size) - pivot
        phase = np.deg2rad(p1 + p2*(x/size))
        phase_correction = np.exp(1j * phase)
        
        result = data * phase_correction
        
        return {"data": result}



class FourierTransformNode(Node):
    title = "Fourier transform"
    header_color = "#1d725e"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )

    def compute(self, inputs: dict):
        data, inverse, sign_alternation, negate_imaginaries = (
            inputs[k] for k in ("data", "inverse", "sign_alternation", "negate_imaginaries")
        )
        
        if data is None:
            return {"data": None}
        
        result = data
        
        if inverse:
            result = np.fft.ifft(result, axis=-1)
        else:
            result = np.fft.fftshift(np.fft.fft(result, axis=-1).astype(result.dtype), -1)
            
        if sign_alternation:
            n = result.shape[-1]
            alternator = np.power(-1, np.arange(n))
            result = result * alternator
            
        if negate_imaginaries and np.iscomplexobj(result):
            result = result.real - 1j * result.imag
            
            
        if isinstance(data, NMRData):
            dim = f"FDF{data.ndim}"
            sw_Hz, obs_MHz, orig = (data.dic[k] for k in [dim + v for v in ["SW", "OBS", "ORIG"]]) # Hz, MHz, Hz

            size = len(result)
            points = np.arange(size)
            
            o1_Hz = orig + sw_Hz/2 - sw_Hz / size
            ppm = (o1_Hz - sw_Hz * (points/size - 0.5)) / obs_MHz
            
            scales = data.scales.copy()
            scales[-1] = ppm
            
            scale_units = data.scale_units[:-1] + ["ppm"]
            dic = data.dic
            
            result = NMRData(result, scales=scales, scale_units=scale_units, dic=dic)
        
        return {"data": result}


class TransposeNode(Node):
    title = "Transpose data"
    header_color = "#1d725e"
    category = "Processing"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "dim", "label": "Dimension", "data_type": "int", "default_value": 1, "clamp": [0, np.inf], "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
     
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")
        return

    def compute(self, inputs: dict):
        data, dim = (inputs.get(k, None) for k in ("data", "dim"))
        
        if data is None:
            self._set_input_label()
            self._set_output_label()
            return {"data": None}
        
        if hasattr(data, "shape"):
            self._set_input_label(data.shape)
            
        
        if dim == 0:
            # No specific dimension selected → transpose all
            result = np.transpose(data)
        else:
            # Move selected dimension to the last
            if dim < data.ndim:
                result = np.moveaxis(data, source=dim-1, destination=-1)
            else:
                # Invalid dim
                result = data  # no change
        
        self._set_output_label(result.shape)
        return {"data": result}


class ExtractRow(Node):
    title = "Extract row"
    header_color = "#83314a"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
    
    
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")
        return
    

    def compute(self, inputs: dict):
        
        data, index, indices = (inputs[k] for k in ("data", "index", "indices"))
        
        self._set_input_label("Data")
        
        if data is None:
            return {"data": None}
        
        self._set_input_label(data.shape)

        try:
            if indices == "" and index is not None and type(index) is int:
                size = data.shape[0]
                
                result = data[min(max(index, 0), size - 1)]
                self._set_output_label(result.shape)
                return {"data": result}
            else:
                cleaned_indices = indices.replace(" ", "")
                cleaned_indices = re.sub(r'[\[\]]+', ',', cleaned_indices)
                index_list = [int(i) for i in cleaned_indices.split(',') if i.strip().isdigit()]
                
                result = data[tuple(index_list)]
                self._set_output_label(result.shape)
                return {"data": result}
        except IndexError:
            return {"data": data}
        
        
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

        return {"output": scale}
    

class CropDataPointsNode(Node):
    title = "Crop data (points)"
    header_color = "#83314a"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
    
    
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")
        return

    def compute(self, inputs: dict):      
        data, start_index, end_index = (inputs[k] for k in ("data", "start_index", "end_index"))
        
        self._set_input_label()
        self._set_output_label()
        
        if data is None:
            return {"data": None}
        
        self._set_input_label(data.shape)
        
        if start_index >= end_index:
            return {"data": data}
        
        
        slices = [slice(None)] * (data.ndim - 1) + [slice(start_index, end_index)]
        cropped = data[tuple(slices)]
        self._set_output_label(cropped.shape)
        return {"data": cropped}
        
        
class CropDataFractionNode(Node):
    title = "Crop data (fraction)"
    header_color = "#83314a"
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
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
    
    
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")
        return

    def compute(self, inputs: dict):      
        data, start_fraction, end_fraction = (inputs[k] for k in ("data", "start_fraction", "end_fraction"))
        
        self._set_input_label()
        self._set_output_label()
        
        if data is None:
            return {"data": None}
        
        self._set_input_label(data.shape)
        
        if start_fraction >= end_fraction:
            self._set_output_label(data.shape)
            return {"data": data}
        else:
            size = data.shape[-1]
            start_index = int(size*start_fraction)
            end_index = int(size*end_fraction)
            
            slices = [slice(None)] * (data.ndim - 1) + [slice(start_index, end_index)]
            cropped = data[tuple(slices)]
            self._set_output_label(cropped.shape)
            return {"data": cropped}


class CropDataPPMNode(Node):
    title = "Crop data (ppm)"
    header_color = "#83314a"
    category = "Utilities"

    def __init__(self):
        super().__init__(
            node_structure={
                "parameters": [
                    {"id": "start_ppm", "label": "Start ppm", "data_type": "float", "default_value": 0.0, "input": True},
                    {"id": "end_ppm", "label": "End ppm", "data_type": "float", "default_value": 0.0, "input": True},
                    
                    {"id": "data", "label": "Data", "data_type": "array", "input": True},
                ],
                "outputs": [
                    {"id": "data", "label": "Data", "data_type": "array"},
                ]
            }
        )
        
    def _set_input_label(self, shape=""):
        label = self.parameters["data"].parameter_label
        label.setText(f"Data {shape}")
        return
    
    
    def _set_output_label(self, shape=""):
        label = self.outputs["data"].parameter_label
        label.setText(f"{shape} Data")
        return

    def compute(self, inputs: dict):      
        data, start_ppm, end_ppm = (inputs[k] for k in ("data", "start_ppm", "end_ppm"))
        
        self._set_input_label()
        self._set_output_label()
        
        if data is None:
            return {"data": None}
        
        self._set_input_label(data.shape)
        
        if start_ppm >= end_ppm:
            self._set_output_label(data.shape)
            return {"data": data}
        else:
            #size = data.shape[-1]
            #start_index = int(size*start_ppm)
            #end_index = int(size*end_ppm)
            #
            #slices = [slice(None)] * (data.ndim - 1) + [slice(start_index, end_index)]
            #cropped = data[tuple(slices)]
            self._set_output_label(data.shape)
            return {"data": data}