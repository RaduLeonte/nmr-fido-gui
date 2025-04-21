import os
import numpy as np
from functools import partial
from copy import deepcopy
import nmrglue as ng
from inspect import Signature
import re
from collections import defaultdict

from PySide6.QtCore import (
    Qt,
    QThreadPool, QRunnable, Slot,
    QSize,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow,
    QGridLayout, QGroupBox, QHBoxLayout, QVBoxLayout,
    QWidget, QLabel, QLineEdit, QSlider, QPushButton, QSizePolicy,
    QFileDialog, QListWidget, QSplitter, QSpacerItem, QCheckBox,
    QScrollArea, QWidgetAction,
)
from PySide6.QtGui import (
    QAction,
    QResizeEvent, QDragEnterEvent, QDragLeaveEvent, QDropEvent,
    QPixmap, QColor,
    QTransform,
    QDoubleValidator,
)
import pyqtgraph as pg

from src.session import Session
from src.spectrum import Spectrum
from src.processing_modules import ProcessingModules


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
        
        # Set app
        self.app = app
        
        # Initialize classes
        self.session = Session()
        self.processing_modules = ProcessingModules()
        
        """
        Window config
        """
        #region Window config
        self.setWindowTitle("NMR Fido")
        #self.setWindowIcon(QIcon("icon.png"))
        self.setAcceptDrops(True)
        
        # Minimum size
        min_size = (820, 400)
        self.setMinimumSize(QSize(*min_size))
        
        # Set init size based on screen aspect ratio
        screen_size = QApplication.primaryScreen().availableSize()
        if screen_size.width() >= screen_size.height():
            app_width = int(screen_size.width()*(2/3))
            app_size = QSize(app_width, int(app_width*(min_size[1]/min_size[0])))
        else:
            app_height = int(screen_size.height()*(2/3))
            app_size = QSize(int(app_height*(min_size[0]/min_size[1])), app_height)
        self.resize(app_size)
        #endregion
        
        
        """Thread pool"""
        self.threadpool = QThreadPool()
        
        
        """
        Menu
        """
        #region Menu
        menu = self.menuBar()
        
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
        #endregion
        
        #endregion


        """
        Main container
        """
        layout = QHBoxLayout()
        splitter = QSplitter(Qt.Horizontal)
        
        '''
        Window Region: Spectra list
        '''
        #region Spectra list
        spectra_list_container = QGroupBox("Spectra List")
        spectra_list_container.setMinimumWidth(200)
        spectra_list_container_layout = QVBoxLayout()
        spectra_list_container_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.spectra_list = QListWidget()
        spectra_list_container_layout.addWidget(self.spectra_list)
        self.spectra_list.currentItemChanged.connect(self.update_processing_controls)
        
        spectra_list_container_layout.addStretch()
        spectra_list_container.setLayout(spectra_list_container_layout)
        #endregion
        
        '''
        Window Region: Processing controls
        '''
        #region Processing controls
        
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
        #endregion
        
        '''
        Window Region: Spectrum display
        '''
        #region Spectrum display
        spectrum_container = QGroupBox("Display")
        spectrum_container.setMinimumWidth(500)
        spectrum_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        spectrum_container_layout = QVBoxLayout()
        
        
        """Plot grid"""
        plot_container = QWidget()
        plot_container_layout = QGridLayout()
        plot_container_layout.setHorizontalSpacing(0)
        plot_container_layout.setVerticalSpacing(0)
        
        """Main plot"""
        self.plot = pg.PlotWidget()
        plot_layout = pg.GraphicsLayout()
        self.plot.setCentralItem(plot_layout)
        self.plot_ax = pg.PlotItem()
        self.plot_ax.showAxis("right")
        self.plot_ax.hideAxis("left")
        self.plot_ax.getAxis("bottom").setLabel("Dim 0 [ppm]")
        self.plot_ax.getAxis("bottom").setTextPen("black")
        self.plot_ax.getAxis("right").setLabel("Dim 1\n[ppm]")
        self.plot_ax.getAxis("right").label.setRotation(0)
        self.plot_ax.getAxis("right").label.setTextWidth(60)
        self.plot_ax.getAxis("right").setTextPen("black")
        self.plot_ax.getViewBox().setBackgroundColor("w")
        self.plot.setBackground(QColor(0, 0, 0, 0))
        plot_layout.addItem(self.plot_ax)
        self.plot_contours = []
        self.plot_levels = []
        plot_container_layout.addWidget(self.plot, 1, 1)
        
        """Horizontal trace"""
        #plot_container_layout.addWidget(self.create_horizontal_trace(), 2, 1)
        
        """Plot axes"""
        
        # Add plot grid container to main
        plot_container.setLayout(plot_container_layout)
        spectrum_container_layout.addWidget(plot_container)
        
        # Add spectrum window region to main window
        spectrum_container.setLayout(spectrum_container_layout)
        #endregion
        
        
        """
        Splitter
        """
        #region Splitter
        splitter.addWidget(spectra_list_container)
        splitter.addWidget(controls_group_container)
        splitter.addWidget(spectrum_container)
        splitter.setSizes(
            [
                0.2*app_size.width(),
                0.2*app_size.width(),
                0.6*app_size.width()
            ]
        )
        layout.addWidget(splitter)
        #endregion
        
        """
        Overlay
        """
        #region Overlay
        self.overlay = QLabel("", self)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setStyleSheet("""
            background-color: rgba(0, 0, 0, 100);
            font-weight: bold;
        """)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.overlay.hide()
        #endregion
        
        # Set main layout to be layout of central widget
        self.setCentralWidget(QWidget(layout=layout))
    
    
    #region Main window resize event
    def resizeEvent(self, e: QResizeEvent) -> None:
        """Main window resize event handler

        Args:
            e (QEvent): _description_
        """
        # Resize the overlay widget so it always fills the window
        self.overlay.resize(self.size())
        
        # Call base class resiz even
        super().resizeEvent(e)
    #endregion
    
    
    #region File IO
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
                self.overlay.setStyleSheet("""
                    background-color: rgba(0, 255, 0, 10);
                    font-weight: bold;
                """)
                file_list_text = ''.join(f + '\n' for f in valid_files)
                self.overlay.setText(
                    f"Import files:\n{file_list_text}"
                )
            else:
                # There were no valid files, ignore payload and turn on red overlay
                e.ignore()
                self.overlay.setStyleSheet("""
                    background-color: rgba(255, 0, 0, 10);
                    font-weight: bold;
                """)
                self.overlay.setText(
                    f"Invalid file format."
                )
            # Make sure overlay is on top
            self.overlay.raise_()
            # Show overlay
            self.overlay.show()
    
    
    def dragLeaveEvent(self, e: QDragLeaveEvent) -> None:
        """Main window drag leave event handler.

        Args:
            e (QDragLeaveEvent): Event passed when mouse leaves the window.
        """
        # Hide overlay on mouse leave
        self.overlay.hide()
    
    
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
        #self.display_spectrum(self.session.get_active_spectrum())
    
    #region Processing module
    def add_processing_module(self, module_name: str, *args, **kwargs) -> None:
        #print(f"MainWindow.add_processing_module -> {module_name=}")
        active_index = self.session.get_active_spectrum_index()
        parent_widget_layout = self.controls_group_layout.itemAt(active_index).widget().layout()
        # create widgets
        module = self.processing_modules.get_module(module_name)
        
        if module["widget_generator"]:
            parent_widget_layout.addWidget(module["widget_generator"]())
        else:
            # Auto-generate control widget using function args
            module_args = module["args"]
            #print(f"MainWindow.add_processing_module -> {module_args=}")
            
            collapsible_content = QWidget()
            collapsible_content.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum
            )
            collapsible_content_layout = QVBoxLayout()
            collapsible_content_layout.setContentsMargins(0, 0, 0, 0)
            collapsible_content_layout.setSpacing(0)
            collapsible_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            for arg in module_args.keys():
                if arg not in ["dic", "data"]:
                    #print(arg, module_args[arg])
                    
                    arg_widget = QWidget()
                    #arg_widget.setSizePolicy(
                    #    QSizePolicy.Policy.Minimum,
                    #    QSizePolicy.Policy.Minimum
                    #)
                    #arg_widget.setMaximumHeight(30)
                    arg_widget_layout = QHBoxLayout()
                    arg_widget_layout.addWidget(QLabel(arg))
                    match module_args[arg]["type"]:
                        case "bool":
                            arg_widget_layout.addWidget(QCheckBox())
                        case _:
                             arg_widget_layout.addWidget(QLineEdit())
                    arg_widget.setLayout(arg_widget_layout)
                    collapsible_content_layout.addWidget(arg_widget)
            
            collapsible_content.setLayout(collapsible_content_layout)
            collapsible = QCollapsible(module["function_name"], collapsible_content, expanded=False)
            parent_widget_layout.addWidget(collapsible)
        
        # add function to spectrum processor
        self.session.get_active_spectrum().processor.add_operation(module["operation"], *args, **kwargs)
    
    
    def default_processing(self):
        self.add_processing_module("nmrglue_pipe_proc_sp")
        self.add_processing_module("nmrglue_pipe_proc_zf", auto=True)
        self.add_processing_module("nmrglue_pipe_proc_ft")
        # ps
        self.add_processing_module("nmrglue_pipe_proc_di")
        
        self.add_processing_module("nmrglue_pipe_proc_tp")
        
        self.add_processing_module("nmrglue_pipe_proc_sp")
        self.add_processing_module("nmrglue_pipe_proc_zf", auto=True)
        self.add_processing_module("nmrglue_pipe_proc_ft")
        # ps
        self.add_processing_module("nmrglue_pipe_proc_di")
        
        self.add_processing_module("nmrglue_pipe_proc_tp")
    
    
    def update_processing_controls(self, current_item, previous_item) -> None:
        if not current_item:
            return
        
        current_row = self.spectra_list.currentRow()
        
        for i in range(self.controls_group_layout.count()):
            widget = self.controls_group_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(False)

        widget_to_show = self.controls_group_layout.itemAt(current_row).widget()
        if widget_to_show:
            widget_to_show.setVisible(True)
    #endregion
        
        
    def create_phasing_controls(self, dimension_index: int, spectrum: Spectrum) -> QGroupBox:
        controls = QGroupBox(f"Dimension {dimension_index}")
        controls_layout = QVBoxLayout()
        
        # p0, p1
        for j in [0, 1]:
            pj_group = QWidget()
            pj_group_layout = QHBoxLayout()
            
            pj_label = QLabel(f"p{j}")
            pj_group_layout.addWidget(pj_label)
            
            pj_input = QLineEdit("0.0")
            pj_input.setObjectName(f"dim{dimension_index}_p{j}_input")
            pj_input.setEnabled(False)
            double_validator = QDoubleValidator()
            pj_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pj_input.setValidator(double_validator)
            pj_input.setMaximumWidth(50)
            pj_group_layout.addWidget(pj_input)
            pj_input.textChanged.connect(
                partial(
                    self.threaded, self.phasing_input_callback, spectrum, f"dim{dimension_index}_p{j}"
                )
            )
        
            pj_slider = QSlider(Qt.Orientation.Horizontal)
            pj_slider.setObjectName(f"dim{dimension_index}_p{j}_slider")
            pj_slider.setEnabled(False)
            pj_slider.setMinimum(-360)
            pj_slider.setMaximum(360)
            pj_slider.setValue(0)
            pj_slider.valueChanged.connect(
                partial(
                    self.threaded, self.phasing_slider_callback, spectrum, f"dim{dimension_index}_p{j}"
                )
            )
            pj_group_layout.addWidget(pj_slider)
            
            pj_group.setLayout(pj_group_layout)
            controls_layout.addWidget(pj_group)

        controls.setLayout(controls_layout)
        return controls
    
    
    def create_horizontal_trace(self) -> pg.GraphicsLayoutWidget:
        plot_graph_glw = pg.GraphicsLayoutWidget()
        plot_graph_glw.setObjectName("horizontal_trace")
        plot_graph_glw.setVisible(False)
        plot_graph_glw.setFixedHeight(200)
        plot_graph_glw.setStyleSheet("background-color: rgba(0, 0, 0, 0)")
        plot_graph_glw.ci.layout.setContentsMargins(0,0,0,0)
        
        plot_graph = plot_graph_glw.addPlot()
        plot_graph.setMouseEnabled(x=False, y=False)
        plot_graph.hideButtons()
        plot_graph.setMenuEnabled(False)
        plot_graph.setContentsMargins(0,0,0,0)
        plot_graph.setDefaultPadding(0)
        background_color = QColor("FFFFFF")
        background_color.setAlpha(0)
        plot_graph_glw.setBackground(background_color)
        plot_graph.hideAxis("left")
        plot_graph.hideAxis("bottom")
        self.h_trace_line = plot_graph.plot()
        self.h_trace_line.setPen("black")
        return plot_graph_glw


    def display_spectrum(self, spectrum: Spectrum=None) -> None:
        if spectrum is None:
            spectrum = self.session.get_active_spectrum()
            
        spectrum.process()
        print(f"MainWindow.display_spectrum -> {spectrum=}")
        
        self.plot_ax.setLabels(bottom=f'{spectrum.dic["FDF2LABEL"]} [ppm]', right=f'{spectrum.dic["FDF1LABEL"]} [ppm]')
        
        limitsX = [70, 40]
        limitsY = [135, 100]
        
        print(f"MainWindow.display_spectrum -> Dim1 X {spectrum.dim1_ppm_scale[0]=} {spectrum.dim1_ppm_scale[-1]=}")
        print(f"MainWindow.display_spectrum -> Dim0 Y {spectrum.dim0_ppm_scale[0]=} {spectrum.dim0_ppm_scale[-1]=}")
        x_index_start = np.where(spectrum.dim1_ppm_scale == min(spectrum.dim1_ppm_scale, key=lambda x:abs(x-limitsX[0])))[0][0]
        x_index_end = np.where(spectrum.dim1_ppm_scale == min(spectrum.dim1_ppm_scale, key=lambda x:abs(x-limitsX[1])))[0][0]

        
        y_index_start = np.where(spectrum.dim0_ppm_scale == min(spectrum.dim0_ppm_scale, key=lambda x:abs(x-limitsY[0])))[0][0]
        y_index_end = np.where(spectrum.dim0_ppm_scale == min(spectrum.dim0_ppm_scale, key=lambda x:abs(x-limitsY[1])))[0][0]

        
        data = deepcopy(spectrum.data)

        
        print(f"MainWindow.display_spectrum -> {data.shape=}")
        #data = data[y_index_start:y_index_end, x_index_start:x_index_end]
        print(f"MainWindow.display_spectrum -> X limits {x_index_start=}; {x_index_end=}")
        print(f"MainWindow.display_spectrum -> Y limits {y_index_start=}; {y_index_end=}")
        
        data = data[180:350, 1900:2160]
        
        #data = np.flip(data, 0)
        
        if hasattr(self, "h_trace_line"):
            h_trace_line = self.h_trace_line
            y = data[15]
            x = np.arange(0, len(y))
            h_trace_line.setData(x, y)
        
        print(f"MainWindow.display_spectrum -> {data.shape=}")
        
        if len(data) == 0:
            return

        def _median_absolute_deviation(data, k=1.4826):
            """ Median Absolute Deviation: a "Robust" version of standard deviation.
                Indices variabililty of the sample.
                https://en.wikipedia.org/wiki/Median_absolute_deviation
            """
            data = np.ma.array(data).compressed()
            median = np.median(data)
            return k*np.median(np.abs(data - median))
        
        median_abs_value = _median_absolute_deviation(data)
        max_value = median_abs_value*20
        min_value = max_value*-1
        print(f"MainWindow.display_spectrum -> {min_value=} {max_value=}")
        

        data = data.transpose()
        data = np.flip(data, 1)
        data = np.flip(data, 0)
        base_level = median_abs_value*3
        nr_levels = 32
        multiplier = 1.2
        if len(self.plot_levels) == 0 :
            positive_levels = [base_level*np.power(multiplier, np.abs(x))*np.sign(x) for x in np.arange(1, nr_levels+1)]
            negative_levels = [x*-1 for x in positive_levels]
            self.plot_levels = positive_levels + negative_levels
            self.plot_levels.sort()
        
        x_range = (spectrum.dim1_ppm_scale[x_index_start], spectrum.dim1_ppm_scale[x_index_end])
        y_range = (spectrum.dim0_ppm_scale[y_index_start], spectrum.dim0_ppm_scale[y_index_end])
        print(f"MainWindow.display_spectrum -> {x_range=} {y_range=}")
        self.plot_ax.setXRange(*x_range)
        self.plot_ax.setYRange(*y_range)
        self.plot_ax.getViewBox().invertY(True)
        self.plot_ax.getViewBox().invertX(True)
        
        move_x = x_range[-1]
        move_y = y_range[-1]
        print(move_x, move_y)
        scale_x = (x_range[0] - x_range[-1]) / data.shape[0]
        scale_y = (y_range[0] - y_range[-1]) / data.shape[1]
        print(scale_x, scale_y)
        
        if len(self.plot_contours) == 0:
            for level in self.plot_levels:
                color = "#1f9c74" if level > 0 else "#fabd2e"

                #print(f"MainWindow.display_spectrum -> {level=}")
                c = pg.IsocurveItem(
                    data=data,
                    level=level,
                    pen=color
                )
                c.setPos(move_x, move_y)
                c.setTransform(QTransform.fromScale(scale_x, scale_y))
                #c.setZValue(10)
                self.plot_contours.append(c)
                self.plot_ax.addItem(c)
        else:
            for contour in self.plot_contours:
                contour.setData(data)
                
        
        print(f"MainWindow.display_spectrum -> done")
        self.app.processEvents()
    
    
    def threaded(self, *args):
        """Run a function (args[0]) with arguments (args[1:]) on a different thread.
        """
        self.threadpool.start(Worker(*args))
    
    
    def phasing_input_callback(self, spectrum: Spectrum, identifier: str, phasing_input_text: str) -> None:
        """Callback for phasing float inputs. On change, update the slider and rephase spectrum.

        Args:
            spectrum (Spectrum): Main spectrum class.
            identifier (str): Identifier of callee input.
            phasing_input_text (str): Current text content of the input.
        """
        print(f"MainWindow.phasing_input_callback -> {phasing_input_text}")
        # Select callee
        phasing_input = self.findChild(QLineEdit, f"{identifier}_input")
        # Immediately return if callee cannot be found
        if phasing_input == None:
            return
        
        # If the the input text content is not a valid float, return immediately.
        try:
            int(float(phasing_input_text))
        except ValueError:
            return
        
        # Find the float input's corresponding slider and set it to the input value.
        self.findChild(
            QSlider, f"{identifier}_slider"
        ).setValue(
            int(float(
                phasing_input_text
            ))
        )
        
        # Update the plot with new phasing values
        self.update_plot(spectrum)
    
    
    def phasing_slider_callback(self, spectrum: Spectrum, identifier: str, phasing_slider_value: int) -> None:
        """Callback for phasing slider. On change, update the float input and rephase spectrum.

        Args:
            spectrum (Spectrum): Main spectrum class.
            identifier (str): Identifier of callee slider.
            phasing_slider_value (int): Current slider value.
        """
        print(f"MainWindow.phasing_slider_callback -> {phasing_slider_value}")
        # Immediately return if callee slider cannot be found
        if self.findChild(QLineEdit, f"{identifier}_input") == None:
            return

        # Find the slider's corresponding float input and set its text content to the slider value.
        self.findChild(
            QLineEdit, f"{identifier}_input"
        ).setText(
            str(
                self.findChild(QSlider, f"{identifier}_slider").value()
                )
        )
        
        # Update the plot with new phasing values
        self.update_plot(spectrum)
    
    
    def update_plot(self, spectrum: Spectrum) -> None:
        """Update the spectrum's phasing values and reprocess it before displaying it.

        Args:
            spectrum (Spectrum): Main spectrum class.
        """
        # Get all phasing values from the inputs.
        phasing_values = [
            self.findChild(QLineEdit, "dim0_p0_input").text(),
            self.findChild(QLineEdit, "dim0_p1_input").text(),
            self.findChild(QLineEdit, "dim1_p0_input").text(),
            self.findChild(QLineEdit, "dim1_p1_input").text()
        ]
        
        # Set phasing values in the spectrum class
        spectrum.phase([float(p) if p != "" else 0.0 for p in phasing_values])
        
        # Display phased spectrum
        #self.display_spectrum(spectrum)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        self.fn(*self.args, **self.kwargs)

#region QCollapsible
class QCollapsible(QWidget):
    """Custom collapsible PySide6 widget.
    """
    def __init__(self, title: str, content: QWidget, expanded: bool = True):
        """Constructor.

        Args:
            title (str): Title in the header of the collapsible widget.
            content (QWidget): Child widget that is collapsed/expanded.
            expanded (bool, optional): Specify if the widget should be expanded when created.
        """
        # Parent class constructor
        super().__init__()
        
        # Set widget width to be 100% of parent and of variable but minimal height
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum
        )
        
        # Create layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)
        
        # Header
        self.expand_button = QPushButton()
        self.expand_button.setMinimumHeight(30)
        # Header layout
        self.expand_button_layout = QHBoxLayout()
        self.expand_button_layout.setContentsMargins(10, 5, 10, 5)
        self.expand_button_layout.setSpacing(5)
        
        # Header title
        self.expand_button_layout.addWidget(QLabel(title))
        # Spacer
        self.expand_button_layout.addSpacerItem(
            QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        # Header triangle icon
        self.expand_button_icon = QLabel()
        self.expand_button_layout.addWidget(self.expand_button_icon)
        
        # Set layout and add button
        self.expand_button.setLayout(self.expand_button_layout)
        self.main_layout.addWidget(self.expand_button)
        
        # Add child content
        self.content = content
        self.main_layout.addWidget(self.content)
        
        self.has_children = True if self.content.layout().count() != 0 else False
        
        self.icon_pixmap_expanded = QPixmap("src/qt_gui/assets/icon_expanded.png").scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon_pixmap_collapsed = QPixmap("src/qt_gui/assets/icon_collapsed.png").scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.expanded = expanded
        if self.has_children:
            self.expand_button.clicked.connect(self.toggle)
            
            # Create pixmaps and set it to the button icon
            self.expand_button_icon.setPixmap(self.icon_pixmap_expanded if self.expanded else self.icon_pixmap_collapsed)
            
            # Widget is expanded upon creation, collapse it if it shouldn't be
            if not self.expanded:
                self.collapse()
        
        
    def toggle(self) -> None:
        """Expand/collapse widget
        """
        # Check current state
        if self.expanded:
            # If widget is expanded -> collapse it and change the icon
            self.collapse()
        else:
            # If widget is collapse -> expand it and change the icon
            self.expand()
        # Toggle state variable
        self.expanded = not self.expanded
        
    
    def collapse(self) -> None:
        self.content.setMaximumHeight(0)
        self.expand_button_icon.setPixmap(self.icon_pixmap_collapsed)
        
    
    def expand(self) -> None:
        self.content.setMaximumHeight(999999)
        self.expand_button_icon.setPixmap(self.icon_pixmap_expanded)