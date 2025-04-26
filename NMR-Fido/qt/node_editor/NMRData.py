import numpy as np

class NMRData(np.ndarray):
    def __new__(cls, input_array: np.ndarray, scales=None, scale_units=None, dic=None):
        obj = np.asarray(input_array).view(cls)
        
        if scales is None:
            obj.scales = [np.arange(size) for size in input_array.shape]
        else:
            obj.scales = scales
        
        obj.scale_units = scale_units if scale_units is not None else [None]*input_array.ndim
        obj.scale_limits = [(scale[0], scale[-1]) for scale in obj.scales]
        obj.dic = dic
        return obj
    
    def __array_finalize__(self, obj):
        if obj is None: return
        self.scales = getattr(obj, 'scales', None)
        self.scale_units = getattr(obj, 'scale_units', None)
        self.scale_limits = getattr(obj, 'scale_limits', None)
        self.dic = getattr(obj, 'dic', None)
    
    
    def __str__(self):
        data_preview = np.array2string(
            self,
            max_line_width=50, 
            precision=3,
            threshold=5, 
            edgeitems=2
        )

        scales_preview = "\n".join(
            f"{i} [Unit: {self.scale_units[i]}] [{self.scale_limits[i][0]:.3f}, {self.scale_limits[i][1]:.3f}]: {np.array2string(scale, max_line_width=80, threshold=5, edgeitems=2)}"
            for i, scale in enumerate(self.scales)
        )
        
        dic_preview = list(self.dic.keys())[:5] if hasattr(self, "dic") and self.dic is not None else "None"

        text = f"""Shape: {self.shape}\nData preview:\n{data_preview}\nScales preview:\n{scales_preview}\nDic:\n{dic_preview}"""

        return text
    
    __repr__ = __str__
