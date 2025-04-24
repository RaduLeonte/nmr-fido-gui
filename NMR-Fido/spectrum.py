import nmrglue as ng
from copy import deepcopy
from functools import wraps
from time import time
import os.path


class Spectrum:

    def __init__(self, path: str):
        self.path = path
        self.base_path = os.path.basename(path)
        self.name = os.path.splitext(self.base_path)[0]
        self.extension = os.path.splitext(self.base_path)[-1]
        
        
        if self.extension == ".ft2":
            self.fid_dic, self.fid_data = None, None
            self.proc_dic, self.proc_data = ng.pipe.read(path)
            
        elif self.extension == ".fid":
            self.fid_dic, self.fid_data = ng.pipe.read(path)
            self.proc_dic, self.proc_data = None, None
            
            self.processor = None
            
            self.dim0_p0 = 0
            self.dim0_p1 = 0
            self.dim1_p0 = 0
            self.dim1_p1 = 0
            
            """
            Define processor operations.
            Using nmrglue -> on avg 0.142 s -> 7 Hz
            """
            self.processor = Processor()
            #self.processor.add_operation(ng.pipe_proc.sp, off=0.5, end=1.0, pow=2, c=1.0) # adjustable sine bell window
            ##self.processor.add_operation(processing.zero_fill)
            #self.processor.add_operation(ng.pipe_proc.zf, auto=True)
            ##self.processor.add_operation(processing.fourier_transform)
            #self.processor.add_operation(ng.pipe_proc.ft, auto=True)
            #self.processor.add_operation(
            #    ng.pipe_proc.ps,
            #    p0=lambda: self.dim0_p0,
            #    p1=lambda: self.dim0_p1
            #)
            #self.processor.add_operation(ng.pipe_proc.di) # delete imaginary part
            #
            ##self.processor.add_operation(processing.transpose)
            #self.processor.add_operation(ng.pipe_proc.tp)
            #
            #self.processor.add_operation(ng.pipe_proc.sp, off=0.5, end=1.0, pow=2, c=1.0) # adjustable sine bell window
            ##self.processor.add_operation(processing.zero_fill)
            #self.processor.add_operation(ng.pipe_proc.zf, auto=True)
            ##self.processor.add_operation(processing.fourier_transform)
            #self.processor.add_operation(ng.pipe_proc.ft, auto=True)
            #self.processor.add_operation(
            #    ng.pipe_proc.ps,
            #    p0=lambda: self.dim1_p0,
            #    p1=lambda: self.dim1_p1
            #)
            #self.processor.add_operation(ng.pipe_proc.di) # delete imaginary part
            #
            ##self.processor.add_operation(processing.transpose)
            #self.processor.add_operation(ng.pipe_proc.tp)
            
            self.process()
        
        
    def calcualate_ppm_scales(self) -> None:
        self.dim0_uc = ng.pipe.make_uc(self.dic, self.data, dim=0)
        self.dim0_ppm_scale = self.dim0_uc.ppm_scale()
        
        self.dim1_uc = ng.pipe.make_uc(self.dic, self.data, dim=1)
        self.dim1_ppm_scale = self.dim1_uc.ppm_scale()
        
        
        
    def process(self) -> None:
        if self.fid_data is not None:
            self.processor.run(self)
            self.calcualate_ppm_scales()
    
        
        
    def reset_phase(self) -> None:
        self.dim0_p0 = 0
        self.dim0_p1 = 0
        self.dim1_p0 = 0
        self.dim1_p1 = 0
        
        
    def phase(self, values) -> None:
        self.dim0_p0 = values[0]
        self.dim0_p1 = values[1]
        self.dim1_p0 = values[2]
        self.dim1_p1 = values[3]
        
        self.process()


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print('func:%r args:[%r, %r] took: %2.4f sec' % \
          (f.__name__, args, kw, te-ts))
        return result
    return wrap


class Processor:
    
    def __init__(self):
        self.operations = []
        
        
    def add_operation(self, func, *args, **kwargs) -> None:
        self.operations.append((func, args, kwargs))
    
    @timing
    def run(self, spectrum: Spectrum) -> None:
        dic = deepcopy(spectrum.fid_dic)
        data = deepcopy(spectrum.fid_data)
        for func, args, kwargs in self.operations:
            eval_args = [arg() if callable(arg) else arg for arg in args]
            eval_kwargs = {k: v() if callable(v) else v for k, v in kwargs.items()}
            print(f"Processor.run {func.__name__} -> args:{eval_args}; kwargs:{eval_kwargs}")
            #dicb4 = deepcopy(dic)
            dic, data = func(dic, data, *eval_args, **eval_kwargs)
            #print_dict_diff(dicb4, dic)
        
        spectrum.dic = dic
        spectrum.data = data


def print_dict_diff(dict1: dict, dict2: dict):
    '''
    Prints the differences between two dictionaries.

    Parameters
    ----------
    dict1 : dict
        First dictionary to compare.
    dict2 : dict
        Second dictionary to compare.

    Prints differences in keys and values between the two dictionaries.
    '''
    # Keys that are in dict1 but not in dict2
    diff1 = dict1.keys() - dict2.keys()
    if diff1:
        print(f"Keys in dict1 but not in dict2: {diff1}")
    
    # Keys that are in dict2 but not in dict1
    diff2 = dict2.keys() - dict1.keys()
    if diff2:
        print(f"Keys in dict2 but not in dict1: {diff2}")
    
    # Keys that are in both dictionaries but have different values
    common_keys = dict1.keys() & dict2.keys()
    for key in common_keys:
        if dict1[key] != dict2[key]:
            print(f"Difference in key '{key}': dict1 = {dict1[key]}, dict2 = {dict2[key]}")