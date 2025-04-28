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
        self.register_port(data_input_port, "data", "parameters")
        
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
        self.register_port(scale_input_port, "scale", "parameters")

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
            if data is None:
                continue
            
            color = color_cycle[i % len(color_cycle)]
            
            if isinstance(data, (int, float, np.number)):
                hline = pg.InfiniteLine(pos=data, angle=0, pen=color)
                self.plot.addItem(hline)
                continue
            
            
            if data.ndim != 1:
                continue
            
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
        self.register_port(data_input_port, "data", "parameters")
        
        base_level_port = NodeParameter(
            param_type="any",
            label="Base level",
            data_type="float",
            input_port=True,
            output_port=False,
            proxy_ref=self,
            parent_node=self,
            port_id="base_level",
            accept_multiple_wires=False,
        )
        self.register_port(base_level_port, "base_level", "parameters")
        
        level_multiplier_port = NodeParameter(
            param_type="any",
            label="Level multiplier",
            data_type="float",
            input_port=True,
            output_port=False,
            proxy_ref=self,
            parent_node=self,
            port_id="level_multiplier",
            accept_multiple_wires=False,
        )
        self.register_port(level_multiplier_port, "level_multiplier", "parameters")
        
        
        nr_levels = NodeParameter(
            param_type="any",
            label="Number of levels",
            data_type="int",
            input_port=True,
            output_port=False,
            proxy_ref=self,
            parent_node=self,
            port_id="nr_levels",
            accept_multiple_wires=False,
        )
        self.register_port(nr_levels, "nr_levels", "parameters")
        

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
        data_inputs, base_level, level_multiplier, nr_levels = (
            inputs.get(k, None) for k in ("data", "base_level", "level_multiplier", "nr_levels")
        )
        
        self.plot.clear()
        
        if level_multiplier is None:
            level_multiplier = 1.1
        if nr_levels is None:
            nr_levels = 12
        
        
        global_xmin, global_xmax = None, None
        global_ymin, global_ymax = None, None
        
        color_cycle = ['c', 'm', 'y', 'r', 'g', 'b', 'w']
        
        for i, data in enumerate(data_inputs):
            if data is None or data.ndim != 2:
                continue

            data = np.real(data)
            color = color_cycle[i % len(color_cycle)]
            
            if base_level is None:
                base_level = self._median_absolute_deviation(data, k=4)
            
            levels_positive = [base_level * (level_multiplier ** j) for j in range(nr_levels)]
            levels_negative = [-l for l in levels_positive]
            
            if isinstance(data, NMRData) and len(data.scales) >= 2:
                y_scale = data.scales[-2]
                x_scale = data.scales[-1]

                y_size, x_size = data.shape

                x_pixel_to_scale = lambda xi: np.interp(xi, [0, x_size-1], [x_scale[0], x_scale[-1]])
                y_pixel_to_scale = lambda yi: np.interp(yi, [0, y_size-1], [y_scale[0], y_scale[-1]])

                invert_x = x_scale[0] > x_scale[-1]
                invert_y = y_scale[0] > y_scale[-1]

            else:
                # fallback: pixels = scales
                x_pixel_to_scale = lambda xi: xi
                y_pixel_to_scale = lambda yi: yi
                invert_x = False
                invert_y = False

            def draw_contours(levels, pen_color):
                path = QPainterPath()
                for level in levels:
                    contours = measure.find_contours(data, level=level)
                    for contour in contours:
                        if contour.shape[0] < 2:
                            continue
                        x0 = x_pixel_to_scale(contour[0, 1])
                        y0 = y_pixel_to_scale(contour[0, 0])
                        path.moveTo(x0, y0)
                        for pt in contour[1:]:
                            x = x_pixel_to_scale(pt[1])
                            y = y_pixel_to_scale(pt[0])
                            path.lineTo(x, y)
                item = QGraphicsPathItem(path)
                item.setPen(pg.mkPen(color=pen_color, width=1))
                item.setZValue(10 + i)
                self.plot.addItem(item)

            draw_contours(levels_positive, color)

            # Draw negative levels with inverted color
            inverted_qcolor = QColor(color)
            inverted_qcolor = QColor(255 - inverted_qcolor.red(), 255 - inverted_qcolor.green(), 255 - inverted_qcolor.blue())
            draw_contours(levels_negative, inverted_qcolor)
                
            
            if isinstance(data, NMRData):
                if global_xmin is None:
                    global_xmin, global_xmax = x_scale[0], x_scale[-1]
                    global_ymin, global_ymax = y_scale[0], y_scale[-1]
                else:
                    global_xmin = min(global_xmin, x_scale[0])
                    global_xmax = max(global_xmax, x_scale[-1])
                    global_ymin = min(global_ymin, y_scale[0])
                    global_ymax = max(global_ymax, y_scale[-1])
            else:
                h, w = data.shape
                if global_xmin is None:
                    global_xmin, global_xmax = 0, w
                    global_ymin, global_ymax = 0, h
                else:
                    global_xmax = max(global_xmax, w)
                    global_ymax = max(global_ymax, h)


        if global_xmin is not None and global_xmax is not None:
            self.plot.setXRange(global_xmin, global_xmax, padding=0)
            if invert_x:
                self.plot.getViewBox().invertX(True)
            else:
                self.plot.getViewBox().invertX(False)

        if global_ymin is not None and global_ymax is not None:
            self.plot.setYRange(global_ymin, global_ymax, padding=0)
            if invert_y:
                self.plot.getViewBox().invertY(True)
            else:
                self.plot.getViewBox().invertY(False)


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
        self.register_port(output_port1, "data", "output")


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
        self.register_port(input_widget, "input", "parameters")

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
        
        if a is None or b is None:
            return {"data": None}
        
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
        
        if data is None:
            return {"data": None}
        
        
        if isinstance(data, np.ndarray):
            flat_data = np.ravel(data)
        else:
            flat_data = data 

        
        if mode == "Min":
            result = np.min(flat_data)
        else:
            result = np.max(flat_data)
            
        return {"data": float(np.real(result))}
    
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
            result = NMRData(result, copy_from=data)
        
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
            
            result = NMRData(result, copy_from=data)
            result.scales = scales
            
        
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
            dimension_code = data.nuclei_indices[-1] # Get dimension index of last axis
            dim = f"FDF{dimension_code}" # Get dimension code
            sw_Hz, obs_MHz, orig = (data.dic[k] for k in [dim + v for v in ["SW", "OBS", "ORIG"]]) # Hz, MHz, Hz

            size = result.shape[-1]
            points = np.arange(size)
            
            o1_Hz = orig + sw_Hz/2 - sw_Hz / size
            ppm = (o1_Hz - sw_Hz * (points/size - 0.5)) / obs_MHz
            
            scales = data.scales.copy()
            scales[-1] = ppm
            
            scale_units = data.scale_units[:-1] + ["ppm"]
            
            result = NMRData(result, copy_from=data)
            result.scales = scales
            result.scale_units = scale_units
        
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
    
    
    def reorder_metadata(self, input_list: list, target_index: int):
        size = len(input_list)
        axes = list(range(size))
        to_move = axes.pop(target_index)
        axes.insert(size, to_move)
        return [input_list[i] for i in axes]


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
            print(list(range(data.ndim)))
            new_axes = list(reversed(range(data.ndim)))
            print(new_axes)
            result = np.transpose(data)
            
            if isinstance(result, NMRData):
                result.nuclei_indices = [data.nuclei_indices[i] for i in new_axes]
                result.scales = [data.scales[i] for i in new_axes]
                result.scale_units = [data.scale_units[i] for i in new_axes]
            
        else:
            # Move selected dimension to the last
            if dim < data.ndim:
                result = np.moveaxis(data, source=dim-1, destination=-1)
                
                if isinstance(result, NMRData):
                    result.nuclei_indices = self.reorder_metadata(data.nuclei_indices, target_index=dim-1)
                    result.scales = self.reorder_metadata(data.scales, target_index=dim-1)
                    result.scale_units = self.reorder_metadata(data.scale_units, target_index=dim-1)
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
    
    
    def find_index_of_nearest(self, data: list|np.ndarray, target: int|float) -> int:
        return min(range(len(data)), key=lambda i: abs(data[i] - target))


    def compute(self, inputs: dict):      
        data, start_ppm, end_ppm = (inputs[k] for k in ("data", "start_ppm", "end_ppm"))
        
        self._set_input_label()
        self._set_output_label()
        
        if data is None or not isinstance(data, NMRData):
            return {"data": None}
        
        self._set_input_label(data.shape)
        
        if start_ppm <= end_ppm or data.scale_units[-1] != "ppm":
            self._set_output_label(data.shape)
            return {"data": data}
        else:
                        
            scales = data.scales.copy()
            scale = scales[-1]
            
            start_index = self.find_index_of_nearest(scale, start_ppm)
            end_index = self.find_index_of_nearest(scale, end_ppm)
            
            slices = [slice(None)] * (data.ndim - 1) + [slice(start_index, end_index)]
            
            # crop data
            cropped = data[tuple(slices)] 
            
            # crop scale
            scales[-1] = scale[start_index: end_index] 
            cropped.scales = scales
                        
            self._set_output_label(cropped.shape)
            return {"data": cropped}