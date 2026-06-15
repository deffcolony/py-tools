import json
import os
from PyQt6.QtWidgets import (QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QListWidgetItem, QTextEdit, QLabel,
                             QFileDialog, QSplitter, QMessageBox,
                             QAbstractItemView, QApplication, QDialog, QMenu, QComboBox, 
                             QDialogButtonBox, QLineEdit, QCheckBox)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QSettings, QDateTime
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent, QShortcut, QKeySequence

# --- IMPORTS ---
from components.prompt import PromptItemWidget, DroppableLineEdit
from components.prompt.settings import ProjectSettingsDialog
from components.prompt.generator import generate_tree_text
from components.db_manager import DBManager
from components.prompt_state_dialog import PromptStateDialog  # Restored!
from components.styles import apply_class, C_PRIMARY, C_BG_MAIN, C_DANGER, C_BG_SECONDARY, C_BORDER, C_TEXT_MAIN
from components.mime_parser import DragAndDropParser
from components.plugin_system import PluginManager
from components.plugins_core import register_core_plugins

# --- HELPERS ---
def find_git_ignore(start_path):
    current_path = os.path.abspath(start_path)
    while True:
        gitignore_path = os.path.join(current_path, '.gitignore')
        if os.path.isfile(gitignore_path):
            return gitignore_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path: break
        current_path = parent_path
    return None

def parse_gitignore_lines(file_path):
    patterns = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'): patterns.append(line)
    except: pass
    return patterns

class DropSelectionDialog(QDialog):
    def __init__(self, paths, plugin_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Files")
        self.setMinimumWidth(400)
        self.paths = paths
        self.pm = plugin_manager
        
        layout = QVBoxLayout(self)
        label_dropped_count = QLabel(f"Dropped {len(paths)} item(s):")
        label_dropped_count.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(label_dropped_count)
        
        self.list_w = QListWidget()
        self.list_w.addItems([os.path.basename(p) for p in paths])
        self.list_w.setStyleSheet(f"background: {C_BG_SECONDARY}; color: {C_TEXT_MAIN}; border: 1px solid {C_BORDER};")
        self.list_w.setMinimumHeight(100)
        layout.addWidget(self.list_w)
        
        has_files = any(os.path.isfile(p) for p in paths)
        has_folders = any(os.path.isdir(p) for p in paths)
        
        label_select = QLabel("Import as Block Type:")
        layout.addWidget(label_select)
        self.combo = QComboBox()
        self.combo.setStyleSheet(f"background: {C_BG_SECONDARY}; color: {C_TEXT_MAIN}; border: 1px solid {C_BORDER}; padding: 5px;")
        
        valid_count = 0
        all_plugins = self.pm.get_all_plugins()

        for plugin in all_plugins:
            supported = plugin.drag_types 
            if has_folders and "folder" not in supported: continue
            if has_files and "file" not in supported: continue
            
            self.combo.addItem(plugin.name, plugin.id)
            valid_count += 1

            if has_folders and plugin.id == "core.tree":
                self.combo.setCurrentIndex(valid_count - 1)
            elif not has_folders and has_files and plugin.id == "core.file":
                self.combo.setCurrentIndex(valid_count - 1)

        if valid_count == 0:
            self.combo.clear()
            self.combo.addItem("--- No matching plugins found (Showing All) ---", None)
            self.combo.model().item(0).setEnabled(False) 
            for plugin in all_plugins:
                self.combo.addItem(plugin.name, plugin.id)
            if self.combo.count() > 1: self.combo.setCurrentIndex(1)
                
        layout.addWidget(self.combo)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_selected_plugin_id(self):
        return self.combo.currentData()
        
class OverlayFileListWidget(QListWidget):
    filesDropped = pyqtSignal(list) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.overlay = QLabel("DROP FILES OR FOLDERS HERE", self)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet(f"""
            background-color: rgba(18, 13, 3, 0.9);
            color: {C_PRIMARY}; 
            font-size: 20px; 
            font-family: 'Consolas';
            font-weight: bold;
            border: 2px dashed {C_PRIMARY};
        """)
        self.overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect().adjusted(4, 4, -4, -4))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if DragAndDropParser.parse_paths(event.mimeData()):
            event.accept()
            self.overlay.show()
            self.overlay.raise_()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        if DragAndDropParser.parse_paths(event.mimeData()):
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.overlay.hide()
        paths = DragAndDropParser.parse_paths(event.mimeData())
        if paths:
            event.accept()
            self.filesDropped.emit(paths)
        else:
            super().dropEvent(event)

# --- Main Tool Class ---
class PromptComposerTool(QWidget):
    statusMessage = pyqtSignal(str)
    modificationChanged = pyqtSignal(bool)
    titleChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        # 1. SETUP PLUGINS
        self.pm = PluginManager()
        
        # Prevent re-registering core plugins if we open multiple tabs
        if not self.pm.get_all_plugins():
            register_core_plugins()
            
            current_dir = os.path.dirname(os.path.abspath(__file__)) 
            root_dir = os.path.dirname(current_dir) 
            plugins_dir = os.path.join(root_dir, "plugins")
            if os.path.exists(plugins_dir):
                self.pm.load_from_folder(plugins_dir)

        self.is_modified = False
        self.current_save_name = None
        
        self.project_settings = {
            "include_tree": False,
            "global_ignore": ".git, __pycache__, node_modules, .idea, .vscode, .venv, dist, build"
        }

        # --- UI LAYOUT ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        
        # 1. Top Bar
        top_layout = QHBoxLayout()
        
        lbl_root = QLabel("PROJECT ROOT:")
        apply_class(lbl_root, "text-primary font-bold")
        
        self.ln_root = DroppableLineEdit()
        self.ln_root.setPlaceholderText("/path/to/project/root")
        self.ln_root.textChanged.connect(self.mark_as_modified)
        self.ln_root.textChanged.connect(self.refresh_all_paths)
        self.ln_root.fileDropped.connect(self.ln_root.setText)
        
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(40)
        btn_browse.clicked.connect(self.browse_root)

        btn_settings = QPushButton("SETTINGS")
        btn_settings.clicked.connect(self.open_settings_dialog)
        
        self.btn_add = QPushButton("+ BLOCK")
        apply_class(self.btn_add, "font-bold")
        self.btn_add.clicked.connect(lambda: self.add_item())
        
        self.btn_duplicate = QPushButton("DUPLICATE BLOCK")
        self.btn_duplicate.clicked.connect(self.duplicate_selected_block)
        
        self.btn_clear = QPushButton("CLEAR")
        self.btn_clear.clicked.connect(self.request_clear)

        top_layout.addWidget(lbl_root)
        top_layout.addWidget(self.ln_root)
        top_layout.addWidget(btn_browse)
        top_layout.addWidget(btn_settings)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_duplicate)
        top_layout.addWidget(self.btn_clear)
        
        main_layout.addLayout(top_layout)

        # 2. Main Splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.list_widget = OverlayFileListWidget()
        self.list_widget.model().rowsMoved.connect(lambda: self.mark_as_modified())
        self.list_widget.filesDropped.connect(self.handle_files_dropped)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        splitter.addWidget(self.list_widget)

        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)
        
        self.lbl_outdated = QLabel("⚠ PREVIEW OUTDATED - REGENERATE")
        self.lbl_outdated.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_outdated.setStyleSheet(f"color: {C_DANGER}; font-weight: bold; font-size: 11px;")
        self.lbl_outdated.setVisible(False)
        preview_layout.addWidget(self.lbl_outdated)

        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        preview_layout.addWidget(self.txt_result)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.btn_options = QPushButton(" OPTIONS ")
        self.options_menu = QMenu(self)
        self.options_menu.addAction("Import JSON").triggered.connect(self.import_from_json)
        self.options_menu.addAction("Export JSON").triggered.connect(self.export_to_json)
        self.options_menu.addAction("Export to Markdown").triggered.connect(self.export_to_markdown)
        self.options_menu.addSeparator()
        self.options_menu.addAction("Import .gitignore").triggered.connect(self.import_gitignore)
        self.btn_options.setMenu(self.options_menu)

        self.btn_generate_copy = QPushButton("GENERATE & COPY")
        self.btn_generate_copy.clicked.connect(self.generate_and_copy)
        self.btn_generate_copy.setStyleSheet(f"background-color: {C_PRIMARY}; color: {C_BG_MAIN}; font-weight: bold;")

        self.btn_generate = QPushButton("GENERATE")
        self.btn_generate.clicked.connect(self.generate_only)
        self.btn_copy = QPushButton("COPY")
        self.btn_copy.clicked.connect(self.copy_only)
        
        self.cb_autocopy = QCheckBox("Auto-Copy")
        self.cb_autocopy.setChecked(True)
        
        self.label_chr_info = QLabel("Chars: 0 | ~Tokens: 0")

        self.btn_actions = QWidget()
        actions_layout = QHBoxLayout(self.btn_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.btn_generate_copy)
        actions_layout.addWidget(self.btn_generate)
        actions_layout.addWidget(self.btn_copy)
        actions_layout.addSpacing(10)
        actions_layout.addWidget(self.cb_autocopy)
        actions_layout.addWidget(self.label_chr_info)

        bottom_bar.addWidget(self.btn_actions)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.btn_options)
        
        preview_layout.addLayout(bottom_bar)
        splitter.addWidget(preview_widget)
        splitter.setSizes([500, 200]) 
        main_layout.addWidget(splitter)
        
        self.add_item() 

        # KEYBOARD SHORTCUTS
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.quick_save)
        
        self.shortcut_gen = QShortcut(QKeySequence("Ctrl+G"), self)
        self.shortcut_gen.activated.connect(self.generate_only)

    def handle_files_dropped(self, paths):
        if not paths: return
        dlg = DropSelectionDialog(paths, self.pm, self)
        selected_plugin_id = None
        
        if dlg.combo.count() == 1:
            selected_plugin_id = dlg.get_selected_plugin_id()
            self.statusMessage.emit(f"Auto-importing using: {self.pm.get_plugin(selected_plugin_id).name}")
        else:
            if dlg.exec() == QDialog.DialogCode.Accepted:
                selected_plugin_id = dlg.get_selected_plugin_id()
            else:
                return 

        if selected_plugin_id:
            plugin_name = self.pm.get_plugin(selected_plugin_id).id
            for path in paths:
                data = {"path": path}
                self.add_item({"plugin_id": selected_plugin_id, "data": data})
            
            self.mark_as_modified()
            self.statusMessage.emit(f"Added {len(paths)} items.")

    def add_item(self, data=None):
        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(QSize(100, 80)) 
        widget = PromptItemWidget(item, self.list_widget, self.get_project_root)
        widget.contentChanged.connect(self.mark_as_modified)
        self.list_widget.setItemWidget(item, widget)
        if data: widget.set_state(data)
        else: self.mark_as_modified()

    def duplicate_selected_block(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "Info", "Select a block to duplicate first.")
            return
        
        w = self.list_widget.itemWidget(current_item)
        if w:
            data = w.get_state()
            self.add_item(data)
            self.statusMessage.emit("Block duplicated.")

    def open_settings_dialog(self):
        dlg = ProjectSettingsDialog(self, self.project_settings)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.project_settings = dlg.get_settings()
            self.mark_as_modified()
            self.statusMessage.emit("Settings updated.")

    def clear_all(self):
        self.list_widget.clear()
        self.txt_result.clear()
        self.lbl_outdated.hide()
        self.current_save_name = None
        self.titleChanged.emit("PROMPT BUILDER")
        self.mark_as_modified()

    def import_gitignore(self):
        root = self.get_project_root()
        if not root or not os.path.exists(root):
            QMessageBox.warning(self, "Path Error", "Select Project Root first.")
            return
        git_path = find_git_ignore(root)
        if not git_path:
            QMessageBox.information(self, "Not Found", "No .gitignore found.")
            return
        new_patterns = parse_gitignore_lines(git_path)
        if not new_patterns: return
        
        current_str = self.project_settings.get("global_ignore", "")
        current_list = [x.strip() for x in current_str.split(',') if x.strip()]
        added = 0
        for p in new_patterns:
            if p not in current_list:
                current_list.append(p)
                added += 1
        
        if added > 0:
            self.project_settings["global_ignore"] = ", ".join(current_list)
            self.mark_as_modified()
            QMessageBox.information(self, "Success", f"Imported {added} patterns.")

    def refresh_all_paths(self):
        pass

    def handle_unsaved_changes(self):
        if not self.is_modified: return True
        msg = QMessageBox(self)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText("Save unsaved changes?")
        msg.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        ret = msg.exec()
        if ret == QMessageBox.StandardButton.Save: return self.save_content()
        elif ret == QMessageBox.StandardButton.Discard: return True
        return False

    def save_content(self):
        data = self._gather_data()
        dlg = PromptStateDialog(self, mode="save", current_name=self.current_save_name)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_name = dlg.selected_name
            success, msg = DBManager.save_prompt(save_name, data)
            if success:
                self.current_save_name = save_name
                self.titleChanged.emit(save_name.upper())
                
                # Update QSettings Registry with the Date
                settings = QSettings("PyTools", "PromptBuilder")
                registry = settings.value("prompt_registry", {})
                if not isinstance(registry, dict): registry = {}
                registry[save_name] = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
                settings.setValue("prompt_registry", registry)
                
                self.statusMessage.emit(f"Saved: {save_name}")
                self.set_modified(False)
                return True
            else:
                QMessageBox.critical(self, "Error", msg)
        return False
    
    def quick_save(self):
        """Used by Ctrl+S shortcut"""
        if self.current_save_name:
            data = self._gather_data()
            success, msg = DBManager.save_prompt(self.current_save_name, data)
            if success:
                self.set_modified(False)
                self.statusMessage.emit(f"Quick saved: {self.current_save_name}")
                
                settings = QSettings("PyTools", "PromptBuilder")
                registry = settings.value("prompt_registry", {})
                if not isinstance(registry, dict): registry = {}
                registry[self.current_save_name] = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
                settings.setValue("prompt_registry", registry)
            else:
                QMessageBox.critical(self, "Error", msg)
        else:
            self.save_content()

    def load_content(self):
        if not self.handle_unsaved_changes(): return
        dlg = PromptStateDialog(self, mode="load")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            load_name = dlg.selected_name
            data = DBManager.load_prompt(load_name)
            if data:
                self._load_data(data)
                self.current_save_name = load_name
                self.titleChanged.emit(load_name.upper())
                
                # Update QSettings Registry Date when loaded
                settings = QSettings("PyTools", "PromptBuilder")
                registry = settings.value("prompt_registry", {})
                if not isinstance(registry, dict): registry = {}
                registry[load_name] = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
                settings.setValue("prompt_registry", registry)
                
                self.set_modified(False)
                self.statusMessage.emit(f"Loaded: {load_name}")

    def import_from_json(self):
        if not self.handle_unsaved_changes(): return
        fname, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if fname:
            try:
                with open(fname, 'r') as f: self._load_data(json.load(f))
                self.current_save_name = None
                self.titleChanged.emit("IMPORTED PROMPT")
                self.mark_as_modified()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Invalid JSON: {e}")

    def export_to_json(self):
        data = self._gather_data()
        fname, _ = QFileDialog.getSaveFileName(self, "Export", "", "JSON (*.json)")
        if fname:
            with open(fname, 'w') as f: json.dump(data, f, indent=2)

    def export_to_markdown(self):
        res = self.txt_result.toPlainText()
        if not res and self.list_widget.count() > 0: res = self.generate_only()
        if not res: return
        
        default_name = f"{self.current_save_name}.md" if self.current_save_name else "prompt_export.md"
        fname, _ = QFileDialog.getSaveFileName(self, "Export Markdown", default_name, "Markdown (*.md);;Text (*.txt)")
        if fname:
            try:
                with open(fname, 'w', encoding='utf-8') as f: f.write(res)
                self.statusMessage.emit(f"Exported to {fname}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def _gather_data(self):
        data = { "project_root": self.ln_root.text(), "settings": self.project_settings, "items": [] }
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w: data["items"].append(w.get_state())
        return data

    def _load_data(self, data):
        if isinstance(data, list):
            items = data
            root = ""
            settings = {}
        else:
            items = data.get("items", [])
            root = data.get("project_root", "")
            settings = data.get("settings", {})

        self.ln_root.setText(root)
        self.project_settings.update(settings)
        self.list_widget.clear()
        self.txt_result.clear()
        self.lbl_outdated.hide()
        for entry in items: self.add_item(entry)

    def generate_only(self):
        output = []
        global_ignores = self.project_settings.get("global_ignore", "")

        if self.project_settings.get("include_tree"):
            root = self.get_project_root()
            if root and os.path.exists(root):
                try:
                    tree = generate_tree_text(root, global_ignores)
                    output.append(f"PROJECT STRUCTURE:\n```\n{tree}\n```\n{'-'*30}")
                except Exception as e: output.append(f"[Error tree: {e}]")
        
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w:
                block = w.get_compiled_output(global_ignore=global_ignores)
                if block.strip(): output.append(block)

        res = "\n".join(output)
        self.txt_result.setText(res)
        self.lbl_outdated.setVisible(False)
        self.statusMessage.emit("Generated.")
        
        # Token Count Estimator 
        chars = len(res)
        tokens = chars // 4
        self.label_chr_info.setText(f"Chars: {chars} | ~Tokens: {tokens}")
        
        if self.cb_autocopy.isChecked():
            QApplication.clipboard().setText(res)
            self.statusMessage.emit("Generated & Copied.")
            
        return res
    
    def copy_only(self):
        res = self.txt_result.toPlainText()
        if not res and self.list_widget.count() > 0: res = self.generate_only()
        QApplication.clipboard().setText(res)
        self.statusMessage.emit("Copied.")

    def generate_and_copy(self):
        self.generate_only()
        self.copy_only()

    def set_modified(self, state=True):
        self.is_modified = state
        self.modificationChanged.emit(state)
    
    def mark_as_modified(self):
        if not self.is_modified: self.set_modified(True)
        if self.txt_result.toPlainText().strip(): self.lbl_outdated.setVisible(True)

    def get_project_root(self): return self.ln_root.text().strip()
    
    def browse_root(self):
        d = QFileDialog.getExistingDirectory(self, "Project Root")
        if d:
            self.ln_root.setText(d.replace("/", "\\") if os.name=='nt' else d)
            self.import_gitignore()

    def request_clear(self):
        if self.handle_unsaved_changes(): self.clear_all()