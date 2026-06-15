import traceback
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, 
                             QWidget, QHBoxLayout, QStyle, QMenu, QLabel, QMessageBox)
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent
from PyQt6.QtCore import Qt

# Components
from components.styles import MAIN_THEME_DARK
from components.placeholder import PlaceholderWidget
from components.db_manager import DBManager
from components.dep_checker import DependencyChecker 

# Tools (Standard)
def launch_prompt_builder_tool():
    try:
        from tools.prompt_builder import PromptComposerTool
        widget = PromptComposerTool()
        return widget
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to launch Prompt Builder Tool:\n{str(e)}\n\n{traceback.format_exc()}")
    
def launch_db_editor_tool():
    try:
        from tools.db_editor import DatabaseEditorTool
        widget = DatabaseEditorTool()
        return widget
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to launch Database Editor Tool:\n{str(e)}\n\n{traceback.format_exc()}")
    
# def launch_audio_visualizer_tool():
#     try:
#         from tools.audio_viz import AudioVisualizerTool
#         widget = AudioVisualizerTool()
#         return widget
#     except Exception as e:
#         traceback.print_exc()
#         raise RuntimeError(f"Failed to launch Audio Visualizer Tool:\n{str(e)}\n\n{traceback.format_exc()}")

def launch_gallery_tool():
    try:
        from tools.ui_plus_gallery import GalleryPage
        widget = GalleryPage()
        return widget
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to launch Gallery Tool:\n{str(e)}\n\n{traceback.format_exc()}")

def launch_help_viewer_tool():
    try:
        from tools.help import HelpViewerTool
        widget = HelpViewerTool()
        return widget
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Failed to launch Help Viewer Tool:\n{str(e)}\n\n{traceback.format_exc()}")

class AppShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PROMPT BUILDER")
        self.resize(1200, 800)
        
        # Initialize DB
        try:
            DBManager.init_db()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to initialize database:\n{str(e)}")

        # Status Bar
        self.status_label = QLabel("SYSTEM READY.")
        self.statusBar().addWidget(self.status_label)

        # --- MENU ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu("FILE")
        
        save_action = QAction("Save Tab", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.trigger_save)
        file_menu.addAction(save_action)

        load_action = QAction("Load to Tab", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self.trigger_load)
        file_menu.addAction(load_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu("TOOLS")
        
        # Prompt Builder Tool
        act_prompts = QAction("Prompt Builder", self)
        act_prompts.triggered.connect(lambda: self.safe_launch_tool_fn(launch_prompt_builder_tool, "PROMPT BUILDER"))
        tools_menu.addAction(act_prompts)

        # DB Editor Tool
        act_db = QAction("Database Editor", self)
        act_db.triggered.connect(lambda: self.safe_launch_tool_fn(launch_db_editor_tool, "DB EDITOR"))
        tools_menu.addAction(act_db)

        tools_menu.addSeparator()

        act_other_menu = tools_menu.addMenu("Other Tools")

        # Audio Viz Tool
        # act_viz = QAction("Audio Visualizer", self)
        # We connect to a specific method instead of a lambda with the class directly
        # act_viz.triggered.connect(lambda: self.safe_launch_tool_fn(launch_audio_visualizer_tool, "AUDIO VISUALIZER")) 
        # act_other_menu.addAction(act_viz)

        # Gallery Tool
        act_gallery = QAction("UI + Gallery", self)
        act_gallery.triggered.connect(lambda: self.safe_launch_tool_fn(launch_gallery_tool, "GALLERY"))
        act_other_menu.addAction(act_gallery)

        tools_menu.addSeparator()
        help_action = QAction("Help / Documentation", self)
        help_action.triggered.connect(lambda: self.safe_launch_tool_fn(launch_help_viewer_tool, "HELP"))
        tools_menu.addAction(help_action)

        # --- CENTRAL ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)
        
        self.add_home_tab()

    def safe_launch_tool(self, tool_class, title):
        try:
            widget = tool_class()
            self.add_tab(widget, title)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Launch Error", f"Error with {title}:\n{str(e)}")

    def safe_launch_tool_fn(self, tool_fn, title):
        try:
            widget = tool_fn()
            self.add_tab(widget, title)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Launch Error", f"Error with {title}:\n{str(e)}")
        
    def add_tab(self, widget, title):
        try:
            index = self.tabs.addTab(widget, title)
            self.tabs.setCurrentIndex(index)
            
            # Save the base title to handle asterisks and renames dynamically
            widget._base_title = title 
            
            if hasattr(widget, 'statusMessage'):
                widget.statusMessage.connect(self.status_label.setText)
            if hasattr(widget, 'modificationChanged'):
                widget.modificationChanged.connect(lambda s, w=widget: self.update_tab_title(w, s))
            if hasattr(widget, 'titleChanged'):
                widget.titleChanged.connect(lambda t, w=widget: self.update_base_tab_title(w, t))
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Tab Error", f"Failed to add tab:\n{str(e)}")
            if widget:
                widget.deleteLater()

    def update_base_tab_title(self, widget, new_name):
        try:
            index = self.tabs.indexOf(widget)
            if index == -1: return
            widget._base_title = new_name
            is_mod = getattr(widget, 'is_modified', False)
            self.tabs.setTabText(index, f"{new_name} *" if is_mod else new_name)
        except Exception:
            pass

    def update_tab_title(self, widget, is_modified):
        try:
            index = self.tabs.indexOf(widget)
            if index == -1: return
            base_name = getattr(widget, '_base_title', self.tabs.tabText(index).replace(" *", ""))
            self.tabs.setTabText(index, f"{base_name} *" if is_modified else base_name)
        except Exception:
            pass 

    def trigger_save(self):
        try:
            current_widget = self.tabs.currentWidget()
            if not current_widget: return
            
            if hasattr(current_widget, 'save_content'):
                current_widget.save_content()
            else:
                self.status_label.setText("This tab cannot be saved.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving:\n{str(e)}")

    def trigger_load(self):
        try:
            current_widget = self.tabs.currentWidget()
            if not current_widget: return

            if hasattr(current_widget, 'load_content'):
                current_widget.load_content()
            else:
                self.status_label.setText("This tab cannot load data.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Load Error", f"An error occurred while loading:\n{str(e)}")

    def add_home_tab(self):
        try:
            home_widget = PlaceholderWidget()
            # Connect the signal from the dashboard to the handler
            home_widget.toolRequested.connect(self.handle_home_request)
            self.add_tab(home_widget, "HOME")
        except Exception:
            traceback.print_exc()

    def handle_home_request(self, tool_key):
        """Handles button clicks from the Home Dashboard"""
        if tool_key == "prompt":
            self.safe_launch_tool_fn(launch_prompt_builder_tool, "PROMPT BUILDER")
        elif tool_key == "db":
            self.safe_launch_tool_fn(launch_db_editor_tool, "DB EDITOR")
        elif tool_key == "help":
            self.safe_launch_tool_fn(launch_help_viewer_tool, "HELP")

    def close_tab(self, index): 
        try:
            widget = self.tabs.widget(index)
            if not widget: return

            if hasattr(widget, 'handle_unsaved_changes'):
                if not widget.handle_unsaved_changes():
                    return 

            conn_name_to_remove = None
            if hasattr(widget, 'cleanup'):
                widget.cleanup()
                if hasattr(widget, 'db_conn_name'):
                    conn_name_to_remove = widget.db_conn_name

            self.tabs.removeTab(index)
            widget.deleteLater()
            
            if conn_name_to_remove:
                from PyQt6.QtSql import QSqlDatabase
                QSqlDatabase.removeDatabase(conn_name_to_remove)

            if self.tabs.count() == 0:
                self.add_home_tab()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Close Error", f"An error occurred while closing the tab:\n{str(e)}")

    def closeEvent(self, event: QCloseEvent):
        try:
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                self.tabs.setCurrentIndex(i)
                
                if hasattr(widget, 'handle_unsaved_changes'):
                    if not widget.handle_unsaved_changes():
                        event.ignore()
                        return
            event.accept()
        except Exception as e:
            traceback.print_exc()
            reply = QMessageBox.question(self, "Error on Exit", 
                                         f"An error occurred while closing:\n{str(e)}\n\nForce close?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                event.accept()
            else:
                event.ignore()

if __name__ == "__main__":
    try:
        # 1. Initialize Application
        app = QApplication(sys.argv)
        app.setStyle("Fusion") 
        app.setStyleSheet(MAIN_THEME_DARK)

        # 2. Check Dependencies 
        # LOGIC CHANGE: We skip the check if we detect we are running in Pixi
        # Pixi sets the 'PIXI_PROJECT_MANIFEST' environment variable.
        import os
        if "PIXI_PROJECT_MANIFEST" not in os.environ:
            try:
                DependencyChecker.check(None, "requirements.txt")
            except Exception:
                pass
        else:
            print("Running in Pixi environment: Dependency check skipped.")

        # 3. Launch Window
        window = AppShell()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        traceback.print_exc()
        print("CRITICAL LAUNCH ERROR:", str(e))