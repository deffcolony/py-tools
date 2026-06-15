from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal

# Custom CheckBox Widget

class CheckBox(QWidget):
    toggled = pyqtSignal(bool)
    disabled = False

    def __init__(self, label, parent=None):
        super().__init__(parent)
        
        self.checkbox = QWidget(self)
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.setStyleSheet("""
            background-color: #333;
            border: 2px solid #555;
            border-radius: 4px;
        """)
        self.checkbox.mousePressEvent = self.toggle
        
        self.checkmark = QLabel("✓", self)
        self.checkmark.setStyleSheet("color: #fff; font-weight: bold;")
        self.checkmark.setVisible(False)
        
        self.label = QLabel(label, self)
        layout = QHBoxLayout(self)  
        layout.addWidget(self.checkbox)
        layout.addWidget(self.checkmark)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)

    def toggle(self, event):
        if self.disabled:
            return
        is_checked = self.checkbox.styleSheet().find("background-color: #E6B450;") != -1
        if is_checked:
            self.checkbox.setStyleSheet("""
                background-color: #333;
                border: 2px solid #555;
                border-radius: 4px;
            """)
        else:
            self.checkbox.setStyleSheet("""
                background-color: #E6B450;
                border: 2px solid #E6B450;
                border-radius: 4px;
            """)
        self.toggled.emit(not is_checked)
        self.checkmark.setVisible(not is_checked)

    def isChecked(self):
        return self.checkbox.isChecked()