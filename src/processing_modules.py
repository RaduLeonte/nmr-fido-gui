import os
import importlib
import sys
import inspect
import re


class ProcessingModules:
    def __init__(self):
        print(f"ProcessingModules.__init__ -> Start")
        self.modules = {}

        base_folder = "src/processing_modules"
        sys.path.append(os.path.abspath(base_folder))  # Add base folder to sys.path

        for root, _, files in os.walk(base_folder):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":  # Exclude __init__.py files
                    module_name = os.path.splitext(file)[0]  # Get the file name without extension
                    # Build the module path relative to the base folder
                    relative_path = os.path.relpath(root, base_folder).replace(os.sep, ".")
                    module_path = f"{relative_path}.{module_name}" if relative_path else module_name
                    try:
                        # Dynamically import the module
                        module = importlib.import_module(module_path)
                        
                        # Retrieve the required functions from the module
                        widget_function = getattr(module, f"{module_name}_widget", None)
                        operation_function = getattr(module, f"{module_name}_operation", None)
                        
                        operation_function_args = {}
                        # Get default arg values from function signature
                        operation_function_signature = inspect.signature(operation_function)
                        #print(operation_function_signature)
                        for arg in operation_function_signature.parameters:
                            arg_anno = str(operation_function_signature.parameters[str(arg)])
                            #print(arg, arg_anno)
                            match = re.match(r"([a-zA-Z_]\w*)\s*(?::\s*([\w\[\]]+))?\s*(?:=\s*(.+))?", arg_anno)
                            arg_type_hint = match.group(2)
                            arg_default_value = match.group(3)
                            arg_dict = {
                                "type": arg_type_hint,
                                "default": arg_default_value,
                            }
                            operation_function_args[str(arg)] = arg_dict
                        
                        # Get name, arg type, and arg description from docstring
                        operation_function_docstring = operation_function.__doc__
                        function_name = operation_function_docstring.splitlines()[0].strip()
                        #print(function_name)
                        match = re.search(r"Args:\s*\n([\S|\s]*)\n\n", operation_function_docstring)
                        args_docstring_lines = [l.strip() for l in match.group(1).splitlines()]
                        for l in args_docstring_lines:
                            match = re.search(r"^([\w_]*).*\((.*)\):\s(.*)", l)
                            arg_name = match.group(1)
                            operation_function_args[arg_name]["type"] = match.group(2)
                            operation_function_args[arg_name]["description"] = match.group(3)
                        
                        #print(operation_function_args)
                        if operation_function:
                            self.modules[module_name] = {
                                "rel_path": relative_path,
                                "function_name": function_name,
                                "operation": operation_function,
                                "widget_generator": widget_function,
                                "args": operation_function_args,
                            }
                            print(f"ProcessingModules.__init__ -> Loaded module: {module_name}")
                    except Exception as e:
                        print(f"ProcessingModules.__init__ -> Error loading: {module_name}: {e}")

    def get_module(self, module_name):
        """Retrieve a loaded module by name."""
        return self.modules.get(module_name, None)
