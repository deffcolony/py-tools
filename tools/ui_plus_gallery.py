from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.CheckBox import CheckBox

class GalleryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gallery of Custom Blocks"))
        # Add more UI elements to showcase custom blocks
        # Example: A custom block with a checkbox
        block = QWidget(self)
        block_layout = QVBoxLayout(block)
        block_layout.addWidget(QLabel("Example Custom Block"))
        block_layout.addWidget(CheckBox("Enable Feature"))
        layout.addWidget(block)
        layout.addStretch()