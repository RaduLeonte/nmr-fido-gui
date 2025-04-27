import numpy as np
import copy


class NMRData(np.ndarray):
    def __new__(cls, input_array: np.ndarray, nuclei_indices=None, scales=None, scale_units=None, dic=None, copy_from=None):
        obj = np.asarray(input_array).view(cls)
        
        if copy_from is not None:
            obj.scales = copy.deepcopy(copy_from.scales) if copy_from.scales is not None else None
            obj.scale_units = copy.deepcopy(copy_from.scale_units) if copy_from.scale_units is not None else None
            obj.dic = copy.deepcopy(copy_from.dic) if copy_from.dic is not None else None
            obj.nuclei_indices = copy.deepcopy(copy_from.nuclei_indices) if copy_from.nuclei_indices is not None else None
        else:
            obj.scales = scales if scales is not None else [np.arange(size) for size in input_array.shape]
            obj.scale_units = scale_units if scale_units is not None else [None] * input_array.ndim
            obj.dic = copy.deepcopy(dic) if dic is not None else {}
            obj.nuclei_indices = nuclei_indices if nuclei_indices is not None else list(range(1, input_array.ndim + 1))
        
        return obj
    
    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.scales = getattr(obj, 'scales', None)
        self.scale_units = getattr(obj, 'scale_units', None)
        self.dic = getattr(obj, 'dic', None)
        self.nuclei_indices = getattr(obj, 'nuclei_indices', None)
    
    
    def __str__(self):
        data_preview = np.array2string(
            self,
            max_line_width=50, 
            precision=3,
            threshold=5, 
            edgeitems=2
        )

        scales_preview = "\n".join(
            f"{i} [{self.scale_units[i]}]: [{scale[0]} ... {scale[-1]}] {scale.shape}"
            for i, scale in enumerate(self.scales)
        )
        
        dic_preview = list(self.dic.keys())[:5] if hasattr(self, "dic") and self.dic is not None else "None"


        lines = [
            f"Shape: {self.shape}",
            f"Nuclei indices: {self.nuclei_indices}",
            f"Data preview:",
            f"{data_preview}",
            f"Scales preview:",
            f"{scales_preview}",
            f"Dic preview:",
            f"{dic_preview}",
        ]

        return "\n".join(lines)
    
    __repr__ = __str__
