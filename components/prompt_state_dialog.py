import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QLabel, QLineEdit, QListWidgetItem,
                             QSplitter, QDialogButtonBox, QMessageBox, QWidget,
                             QSizePolicy, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt, QSize, QSettings, QDateTime

from components.db_manager import DBManager
from components.prompt import PromptItemWidget
from components.db_selector import DBSelector 
from components.styles import apply_class, C_PRIMARY

class PromptStateDialog(QDialog):
    def __init__(self, parent=None, mode="load", current_name=None):
        super().__init__(parent)
        self.mode = mode
        self.selected_name = None
        
        title = "LOAD PROMPT" if mode == "load" else "SAVE PROMPT"
        self.setWindowTitle(f"{title}")
        self.resize(1100, 700) # Made slightly wider to fit table and preview
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- 1. Header ---
        self.db_selector = DBSelector()
        self.db_selector.db_changed.connect(self.on_db_changed)
        self.db_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.db_selector)

        # --- 2. Central Area ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Search & Names Table
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0,0,0,0)
        
        list_layout.addWidget(QLabel("EXISTING PROMPTS:"))
        
        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search prompts by name...")
        self.search_bar.textChanged.connect(self.filter_prompts)
        self.search_bar.setFixedHeight(30)
        list_layout.addWidget(self.search_bar)
        
        # Table Widget (Replaces QListWidget)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Prompt Name", "Last Activity Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_selection_change)
        self.table.itemDoubleClicked.connect(self.handle_double_click)
        list_layout.addWidget(self.table)
        
        # Right: Visual Preview (Using Read-Only Prompt Items)
        preview_container = QWidget()
        prev_layout = QVBoxLayout(preview_container)
        prev_layout.setContentsMargins(0,0,0,0)
        
        lbl_preview = QLabel("VISUAL PREVIEW (READ ONLY):")
        prev_layout.addWidget(lbl_preview)
        
        self.preview_list = QListWidget()
        self.preview_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        prev_layout.addWidget(self.preview_list)

        splitter.addWidget(list_container)
        splitter.addWidget(preview_container)
        splitter.setSizes([450, 650])
        layout.addWidget(splitter)

        # --- 3. Footer ---
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(5)
        
        # Save Name Input
        self.ln_name = QLineEdit()
        self.ln_name.setPlaceholderText("ENTER PROMPT NAME...")
        self.ln_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ln_name.setFixedHeight(30) 

        if current_name:
            self.ln_name.setText(current_name)
            
        if mode == "save":
            lbl_input = QLabel("SAVE AS:")
            apply_class(lbl_input, "text-primary font-bold")
            lbl_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            footer_layout.addWidget(lbl_input)
            footer_layout.addWidget(self.ln_name)
        else:
            self.ln_name.hide()

        # Dialog Buttons
        btns = QDialogButtonBox()
        self.btn_action = btns.addButton("LOAD" if mode == "load" else "SAVE", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        
        self.btn_action.setStyleSheet(f"background-color: {C_PRIMARY}; color: #120d03; font-weight: bold;")
        
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        
        footer_layout.addWidget(btns)
        layout.addLayout(footer_layout)

        self.refresh_list()

    def on_db_changed(self, new_path):
        """Called when DBSelector changes the database"""
        self.refresh_list()
        self.preview_list.clear()

    def filter_prompts(self, text):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                match = text.lower() in item.text().lower()
                self.table.setRowHidden(row, not match)

    def refresh_list(self):
        settings = QSettings("PyTools", "PromptBuilder")
        registry = settings.value("prompt_registry", {})
        if not isinstance(registry, dict): registry = {}
        
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False) # Disable sorting while loading to prevent UI stutters
        
        try:
            prompts = DBManager.get_all_prompts()
            db_names = []
            
            # Extract names safely from sqlite3.Row or dictionaries
            for row in prompts:
                try:
                    if hasattr(row, 'keys') or isinstance(row, dict):
                        if 'name' in row.keys(): db_names.append(str(row['name']))
                        else: db_names.append(str(row[1] if len(row) > 1 else row[0]))
                    elif isinstance(row, (tuple, list)):
                        db_names.append(str(row[1] if len(row) > 1 else row[0]))
                    else:
                        db_names.append(str(row))
                except: pass

            all_names = set(registry.keys()).union(set(db_names))
            self.table.setRowCount(len(all_names))
            
            for row_idx, name in enumerate(all_names):
                name_str = str(name)
                date_str = str(registry.get(name_str, "Legacy Save (Unknown)"))
                
                item_name = QTableWidgetItem(name_str)
                item_date = QTableWidgetItem(date_str)
                
                item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item_date.setFlags(item_date.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                self.table.setItem(row_idx, 0, item_name)
                self.table.setItem(row_idx, 1, item_date)
                
            self.table.setSortingEnabled(True)
            self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
            
        except Exception as e:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Error reading DB"))
            print(e)

    def on_selection_change(self):
        selected = self.table.selectedItems()
        if not selected:
            self.preview_list.clear()
            return
            
        row = selected[0].row()
        name = self.table.item(row, 0).text()
        
        if name == "Error reading DB": return

        if self.mode == "save":
            self.ln_name.setText(name)
            
        # Load data and populate the preview list
        data = DBManager.load_prompt(name)
        self.populate_preview(data)

    def populate_preview(self, data):
        self.preview_list.clear()
        if not data: return
        
        root_path = data.get("project_root", "")
        items = data.get("items", [])
        
        if root_path:
            lbl = QLabel(f"PROJECT ROOT: {root_path}")
            lbl.setStyleSheet("color: #7c5826; font-style: italic; padding: 5px;")
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 30))
            self.preview_list.addItem(item)
            self.preview_list.setItemWidget(item, lbl)

        for item_data in items:
            list_item = QListWidgetItem(self.preview_list)
            # Default height is updated dynamically by set_state
            list_item.setSizeHint(QSize(100, 105))
            
            widget = PromptItemWidget(
                parent_item=list_item, 
                list_widget=self.preview_list, 
                root_getter=lambda: root_path,
                read_only=True
            )
            widget.set_state(item_data)
            
            self.preview_list.addItem(list_item)
            self.preview_list.setItemWidget(list_item, widget)

    def handle_double_click(self, item):
        row = item.row()
        name = self.table.item(row, 0).text()
        if self.mode == "save":
            self.ln_name.setText(name)
        self.validate_and_accept()

    def validate_and_accept(self):
        if self.mode == "load":
            selected = self.table.selectedItems()
            if not selected:
                QMessageBox.warning(self, "Selection Required", "Please select a valid prompt to load.")
                return
            
            name = self.table.item(selected[0].row(), 0).text()
            if name == "Error reading DB": return
            
            self.selected_name = name
            self.accept()

        elif self.mode == "save":
            name = self.ln_name.text().strip()
            if not name:
                QMessageBox.warning(self, "Name Required", "Please enter a name for the prompt.")
                return
            
            existing_items = [self.table.item(i, 0).text() for i in range(self.table.rowCount())]
            if name in existing_items:
                reply = QMessageBox.question(
                    self, "Confirm Overwrite", 
                    f"'{name}' already exists.\nOverwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            self.selected_name = name
            self.accept()