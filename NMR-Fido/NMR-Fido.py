import os
import sys

from qt.main_window import start_app


if __name__ == "__main__":
    # Change working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Add path for relative imports
    sys.path.insert(0, script_dir)
    
    start_app(sys.argv)