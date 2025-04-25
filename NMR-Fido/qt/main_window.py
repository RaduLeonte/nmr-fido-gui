import os
import numpy as np
from functools import partial
from copy import deepcopy
import nmrglue as ng
from inspect import Signature
import re
from collections import defaultdict

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import pyqtgraph as pg

from misc import set_css_attribute
from qt.node_editor.NodeEditor import *
from qt.node_editor.nodes import *


COLOR_PALETTE = {
    "--text-color": "#e0e0e0",
    "--bg-color1": "#121212",
    "--bg-color2": "#1e1e1e",
    "--bg-color3": "#252525",
    "--border-color": "#505050",
}


def start_app(args: list):
    """Start the application.

    Args:
        args (list): List of arguments passed through command line.
    """
    # Main application
    app: QApplication = QApplication(args)
    # Main window
    window: MainWindow = MainWindow(app)
    window.show()
    # Run app
    app.exec()


class MainWindow(QMainWindow):
    """Main window class
    """
    def __init__(self, app: QApplication) -> None:
        """Constructor.

        Args:
            app (QApplication): QApplication context.
        """
        # Parent constructor
        super().__init__()
        
        self.app = app
        
        self._create_menu()
        self._init_ui()
        
        pass
    
    
    #region Events
    def resizeEvent(self, e: QResizeEvent) -> None:
        """Main window resize event handler

        Args:
            e (QEvent): _description_
        """
        # Resize the overlay widget so it always fills the window
        self.overlay.resize(self.size())
        
        # Call base class resiz even
        super().resizeEvent(e)
        return
    
    
    #region FileIO
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        """Main window drag enter event handler.

        Args:
            e (QDragEnterEvent): Event passed when mouse enters the window.
        """
        
        # Check if user is dragging files
        if not e.mimeData().hasUrls():
            # No files in payload, ignore
            e.ignore()
        else:
            # Payload had files, check if there are files with accepted formats
            valid_files = [
                f.toLocalFile() for f in e.mimeData().urls()
                if any(f.toLocalFile().lower().endswith(ext) for ext in [".fid", ".ft2"])
            ]
            # Check if any valid files were found
            if len(valid_files) != 0:
                # There are valid files, accept the payload and turn on green overlay
                e.accept()
                set_css_attribute(self.overlay, "status", "valid")
                file_list_text = ''.join(f + '\n' for f in valid_files)
                self.overlay.setText(
                    f"Import files:\n{file_list_text}"
                )
            else:
                # There were no valid files, ignore payload and turn on red overlay
                e.ignore()
                self._set_css_attribute(self.overlay, "status", "invalid")
                self.overlay.setText(
                    f"Invalid file format."
                )
            # Make sure overlay is on top
            self.overlay.raise_()
            # Show overlay
            self.overlay.show()
        return
    
    
    def dragLeaveEvent(self, e: QDragLeaveEvent) -> None:
        """Main window drag leave event handler.

        Args:
            e (QDragLeaveEvent): Event passed when mouse leaves the window.
        """
        # Hide overlay on mouse leave
        self.overlay.hide()
        return
    
    
    def dropEvent(self, e: QDropEvent) -> None:
        """Main window drag leave event handler.

        Args:
            e (QDropEvent): Event passed when dropping files onto the window.
        """
        # Hide overlay
        self.overlay.hide()
        
        # Fish out files with accepted file formats from the payload
        valid_files = [
            f.toLocalFile() for f in e.mimeData().urls()
            if any(f.toLocalFile().lower().endswith(ext) for ext in [".fid", ".ft2"])
        ]
        
        # Send valid files to be imported
        self.import_spectra(valid_files)
        return
    #endregion FileIO
    #endregion Events
    
    #region Menu
    def _create_menu(self) -> None:
        menu = self.menuBar()
        return menu
        """File"""
        #region Menu: File
        file_menu = menu.addMenu("File")
        
        """File -> New project"""
        new_project_action = QAction("New project", self)
        new_project_action.setEnabled(False)
        file_menu.addAction(new_project_action)
        
        """File -> Open project"""
        open_project_action = QAction("Open project", self)
        open_project_action.setEnabled(False)
        file_menu.addAction(open_project_action)
        
        """File -> Open recent project >"""
        recent_projects = []
        recent_projects_submenu = file_menu.addMenu("Open recent project")
        
        """File -> Open recent project -> [Recent projects]"""
        if len(recent_projects) == 0:
            no_recent_projects_action = QAction("< no recent projects >", self)
            no_recent_projects_action.setEnabled(False)
            recent_projects_submenu.addAction(no_recent_projects_action)
        else:
            for recent_project in recent_projects:
                recent_projects_submenu.addAction(
                    QAction(recent_project, self)
                )

        recent_projects_submenu.addSeparator()
        
        """File -> Open recent project -> Clear recent projects"""
        clear_recent_projects = QAction("Clear recent projects", self)
        clear_recent_projects.setEnabled(False)
        recent_projects_submenu.addAction(clear_recent_projects)
        
        file_menu.addSeparator()

        """File -> Import file"""
        import_file_action = QAction("Import file", self)
        import_file_action.triggered.connect(lambda: self.import_spectrum_button_callback())
        file_menu.addAction(import_file_action)
        
        """File -> Import recent file >"""
        recent_files = []
        recent_files_submenu = file_menu.addMenu("Open recent file")
        
        """File -> Import recent file -> [Recent files]"""
        if len(recent_files) == 0:
            no_recent_files_action = QAction("< no recent files >", self)
            no_recent_files_action.setEnabled(False)
            recent_files_submenu.addAction(no_recent_files_action)
        else:
            for recent_file in recent_files:
                recent_files_submenu.addAction(
                    QAction(recent_file, self)
                )

        recent_files_submenu.addSeparator()
        
        """File -> Import recent file -> Clear recent files"""
        clear_recent_files = QAction("Clear recent files", self)
        clear_recent_files.setEnabled(False)
        recent_files_submenu.addAction(clear_recent_files)
        #endregion
        
        """Processing"""
        #region Menu: Processing
        processing_menu = menu.addMenu("Processing")
        
        display_spectrum_action = QAction("Display spectrum", self)
        display_spectrum_action.triggered.connect(lambda: self.display_spectrum())
        processing_menu.addAction(display_spectrum_action)
        
        """Processing -> Add processing module > """
        add_proc_module_submenu = processing_menu.addMenu("Add processing module")
        
        
        modules = self.processing_modules.modules
        modules_hierarchy = {k:modules[k]["rel_path"] for k in modules.keys()}
        sorted_modules = sorted(modules_hierarchy.items(), key=lambda x: len(x[1].split('.')), reverse=True)
        menu_hierarchy = defaultdict(lambda: None)
        print(modules_hierarchy)
        for action_name, path in sorted_modules:
            path_parts = path.split('.')
            
            current_menu = add_proc_module_submenu
            for part in path_parts:
                if menu_hierarchy[part] is None:
                    menu_hierarchy[part] = current_menu.addMenu(part)
                
                current_menu = menu_hierarchy[part]

            action = QAction(action_name, self)
            action.triggered.connect(lambda _, fnc=action_name: self.add_processing_module(fnc))
            current_menu.addAction(action)  
        
        add_default_processing = QAction("Add default processing (2D)", self)
        add_default_processing.triggered.connect(lambda: self.default_processing())
        add_proc_module_submenu.addAction(add_default_processing)
        
        return
    #endregion Menu
    
    
    #region UI
    def _init_ui(self) -> None:
        
        def load_stylesheet(app: QApplication, path: str, variables: dict) -> None:
            with open(path, "r") as f:
                stylesheet = f.read()

            # Replace custom CSS variables like var(--text-color)
            for key, value in variables.items():
                stylesheet = stylesheet.replace(f"var({key})", value)

            app.setStyleSheet(stylesheet)
            return
        
        self.app.setStyle("fusion")
        load_stylesheet(self.app, "qt/styles.css", COLOR_PALETTE)
        
        
        self.setWindowTitle("NMR Fido")
        #self.setWindowIcon(QIcon("icon.png"))
        self.setAcceptDrops(True)
        
        # Minimum size
        min_size = (820, 400)
        self.setMinimumSize(QSize(*min_size))
        
        # Set init size based on screen aspect ratio
        ratio = 0.8
        screen_size = QApplication.primaryScreen().availableSize()
        if screen_size.width() >= screen_size.height():
            app_width = int(screen_size.width()*ratio)
            app_size = QSize(app_width, int(app_width*(min_size[1]/min_size[0])))
        else:
            app_height = int(screen_size.height()*ratio)
            app_size = QSize(int(app_height*(min_size[0]/min_size[1])), app_height)
        self.resize(app_size)
        
        """
        Main container
        """
        app_layout = QHBoxLayout()
        
        splitter = QSplitter(Qt.Horizontal)
        app_layout.addWidget(splitter)
        
        splitter.addWidget(self._create_file_explorer())
        #splitter.addWidget(self._create_processing_controls())
        splitter.addWidget(self._create_node_editor())
        splitter.addWidget(self._create_plot())
        splitter.setSizes(
            [
                0.0*app_size.width(),
                1.0*app_size.width(),
                0.0*app_size.width()
            ]
        )
        
        
        self._create_overlay()
        
        self.setCentralWidget(QWidget(layout=app_layout))
        return
    
    
    def _create_file_explorer(self) -> QGroupBox:
        spectra_list_container = QGroupBox("Spectra List")
        spectra_list_container.setMinimumWidth(200)
        spectra_list_container_layout = QVBoxLayout()
        spectra_list_container_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.spectra_list = QListWidget()
        spectra_list_container_layout.addWidget(self.spectra_list)
        
        spectra_list_container_layout.addStretch()
        spectra_list_container.setLayout(spectra_list_container_layout)
        
        return spectra_list_container
    
    
    def _create_processing_controls(self) -> QGroupBox:
        controls_group_container = QGroupBox("Processing")
        controls_group_container.setMinimumWidth(300)
        controls_group_container_layout = QVBoxLayout()
        
        controls_group_scroll = QScrollArea()
        
        controls_group = QWidget()
        self.controls_group_layout = QVBoxLayout()
        self.controls_group_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_group_layout.setSpacing(0)
        self.controls_group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        controls_group.setLayout(self.controls_group_layout)
        
        controls_group_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        controls_group_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_group_scroll.setWidgetResizable(True)
        controls_group_scroll.setWidget(controls_group)
        
        controls_group_container_layout.addWidget(controls_group_scroll)
        controls_group_container.setLayout(controls_group_container_layout)
        
        return controls_group_container
    
    
    def _create_node_editor(self) -> QGroupBox:
        node_editor_container = QGroupBox("Node Editor")
        node_editor_container.setMinimumWidth(600)
        node_editor_container_layout = QVBoxLayout()
        node_editor_container.setLayout(node_editor_container_layout)
        
        
        self.node_editor = NodeEditor(scene_size=(10_000, 5_000), background_color=COLOR_PALETTE["--bg-color1"])
        node_editor_container_layout.addWidget(self.node_editor)

        # Testing nodes
        self.node_editor.add(TestNode(), QPointF(-900, -200))
        
        value_node_1 = ConstantIntNode()
        value_node_2 = ConstantFloatNode()
        math_node = MathNode()
        display_node = PrintDataNode()

        
        self.node_editor.add(value_node_1, QPointF(-500, -300))
        self.node_editor.add(value_node_2, QPointF(-500, -150))
        self.node_editor.add(math_node, QPointF(-200, -300))
        self.node_editor.add(display_node, QPointF(100, -300))
        
        self.node_editor.connect(value_node_1.outputs["output"].port, math_node.parameters["a"].port)
        #self.graph.connect(value_node_2.outputs["output"], math_node.parameters["b"])
        self.node_editor.connect(math_node.outputs["result"].port, display_node.parameters["input"].port)
        
        
        import_data_node = ImportDataNode(default_path="test.fid")
        self.node_editor.add(import_data_node, QPointF(-900, 200))
        
        sine_window_node = SineWindowNode()
        self.node_editor.add(sine_window_node, QPointF(-600, 0))
        
        extract_fid_node = ExtractFIDNode()
        self.node_editor.add(extract_fid_node, QPointF(-300, 100))
        
        delete_imaginaries_node = DeleteImaginariesNode()
        self.node_editor.add(delete_imaginaries_node, QPointF(0, 0))
        
        display_node2 = PrintDataNode()
        self.node_editor.add(display_node2, QPointF(0, 100))
        
        plot_data_node = PlotDataNode()
        self.node_editor.add(plot_data_node, QPointF(300, 0))
        
        self.node_editor.connect(import_data_node.outputs["output"].port, sine_window_node.parameters["data"].port)
        self.node_editor.connect(sine_window_node.outputs["result"].port, extract_fid_node.parameters["data"].port)
        self.node_editor.connect(extract_fid_node.outputs["output"].port, display_node2.parameters["input"].port)
        self.node_editor.connect(extract_fid_node.outputs["output"].port, delete_imaginaries_node.parameters["data"].port)
        self.node_editor.connect(delete_imaginaries_node.outputs["output"].port, plot_data_node.parameters["data"].port)
        
        
        self.node_editor.add(EvaluateGraphNode(self.node_editor.evaluate_graph), QPointF(500, -200))
        
        return node_editor_container
    
    
    def _create_plot(self) -> QGroupBox:
        spectrum_container = QGroupBox("Display")
        spectrum_container.setMinimumWidth(500)
        spectrum_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        spectrum_container_layout = QVBoxLayout()
        spectrum_container.setLayout(spectrum_container_layout)
        
        plot_container = QWidget()
        plot_container_layout = QGridLayout()
        plot_container_layout.setHorizontalSpacing(0)
        plot_container_layout.setVerticalSpacing(0)
        plot_container.setLayout(plot_container_layout)
        spectrum_container_layout.addWidget(plot_container)
        
        """Main plot"""
        self.plot = pg.PlotWidget()
        plot_layout = pg.GraphicsLayout()
        self.plot.setCentralItem(plot_layout)
        self.plot_ax = pg.PlotItem()
        self.plot_ax.showAxis("right")
        self.plot_ax.hideAxis("left")
        self.plot_ax.getAxis("bottom").setLabel("Dim 0 [ppm]")
        self.plot_ax.getAxis("bottom").setTextPen(COLOR_PALETTE["--text-color"])
        self.plot_ax.getAxis("right").setLabel("Dim 1\n[ppm]")
        self.plot_ax.getAxis("right").label.setRotation(0)
        self.plot_ax.getAxis("right").label.setTextWidth(60)
        self.plot_ax.getAxis("right").setTextPen(COLOR_PALETTE["--text-color"])
        self.plot_ax.getViewBox().setBackgroundColor(COLOR_PALETTE["--bg-color1"])
        self.plot.setBackground(QColor(0, 0, 0, 0))
        plot_layout.addItem(self.plot_ax)
        self.plot_contours = []
        self.plot_levels = []
        plot_container_layout.addWidget(self.plot, 1, 1)
        
        
        return spectrum_container
    
    
    def _create_overlay(self) -> None:
        self.overlay = QLabel("", self)
        self.overlay.setObjectName("Overlay")
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.overlay.hide()
        return
    #endregion UI
    
    
    def import_spectrum_button_callback(self) -> None:
        """Open a dialog for file browsing files.
        """
        files = QFileDialog.getOpenFileName(
            self,
            'Open file',
        )       
        self.import_spectra(files)
        
        
    def import_spectra(self, files: list[str]) -> None:
        """Handles import of files from specified paths.

        Args:
            files (list[str]): List of file paths to import.
        """
        # Send list of files to Session class to import
        self.session.import_spectra(files)
        
        # Update file list widget to be in sync with Session
        self.update_spectra_list()
        
        # If there is no currently active spectrum, select the first spectrum
        if self.session.get_active_spectrum_index() is None:
            self.select_spectrum(0)
        
        for _ in range(len(files)):
            self.controls_group_layout.addWidget(QWidget(layout=QVBoxLayout()))

        # Temporary hardcoded processing
        #self.add_processing_module("nmrglue_pipe_proc_ft", auto=True)
        ##self.add_processing_module(ng.pipe_proc.di)
        ##self.add_processing_module(ng.pipe_proc.tp)
        #self.add_processing_module("nmrglue_pipe_proc_ft", auto=True)
        #self.add_processing_module("nmrglue_pipe_proc_ft", auto=True)
        #self.add_processing_module("nmrglue_pipe_proc_ft", auto=True)
        #self.add_processing_module("nmrglue_pipe_proc_ft", auto=True)
        ##self.add_processing_module(ng.pipe_proc.tp)
        
        # Process active spectrum
        self.session.get_active_spectrum().process()
        
        # Display active spectrum
        #self.display_spectrum(self.session.get_active_spectrum())
    #endregion


    def update_spectra_list(self) -> None:
        """Sync spectra list widget with spectra list from Session class.
        """
        current_row = self.spectra_list.currentRow()
        for x in range(self.spectra_list.count()):
            self.spectra_list.takeItem(x)
        self.spectra_list.addItems(self.session.get_spectra_base_paths())
        self.spectra_list.setCurrentRow(current_row)
        
    
    def select_spectrum(self, index: int) -> None:
        """Make spectrum specified by index the currently active spectrum

        Args:
            index (int): Index of spectrum.
        """
        # Select appropriate row in the spectra list widget
        self.spectra_list.setCurrentRow(index)
        # Set the currently active spectrum in the session class
        self.session.set_active_spectrum_index(index)
        # Set the window title to reflect the currently active spectrum
        self.setWindowTitle(f"NMR Fido - {self.session.get_active_spectrum().base_path}")
        # Display the newly active spectrum
        #self.display_spectrum(self.session.get_active_spectrum()
    

    #endregion
    

