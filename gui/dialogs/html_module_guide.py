"""Help > HTML Module Guide: reads the guide for writing importable HTML modules, and saves copies of it."""

import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTextBrowser, QVBoxLayout,
)

from config.paths import resource_path

GUIDE_FILE = "docs/html_module_guide.md"
TEMPLATE_FILE = "tools/html_module/module_template.html"


class HtmlModuleGuideDialog(QDialog):
    """The guide with a contents list, a find box, and buttons to save the guide and the example module."""

    def __init__(self, parent=None, guide_path: Optional[Path] = None, template_path: Optional[Path] = None):
        super().__init__(parent)
        self.guide_path = Path(guide_path) if guide_path else resource_path(GUIDE_FILE)
        self.template_path = Path(template_path) if template_path else resource_path(TEMPLATE_FILE)
        self.setWindowTitle("HTML Module Guide")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Find in the guide:"))
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Type and press Enter")
        self.find_edit.returnPressed.connect(self.find_next)
        find_row.addWidget(self.find_edit, 1)
        self.find_button = QPushButton("Find next")
        self.find_button.clicked.connect(self.find_next)
        find_row.addWidget(self.find_button)
        layout.addLayout(find_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.contents = QListWidget()
        self.contents.setMinimumWidth(240)
        self.contents.setMaximumWidth(340)
        self.contents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.contents.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.contents.currentRowChanged.connect(self._go_to_heading)
        splitter.addWidget(self.contents)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        splitter.addWidget(self.browser)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, 730])
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.save_guide_button = QPushButton("Save the guide as...")
        self.save_guide_button.setToolTip("Save a copy of this guide (Markdown) for yourself, a writer or a generator script")
        self.save_guide_button.clicked.connect(self.save_guide)
        buttons.addWidget(self.save_guide_button)
        self.save_example_button = QPushButton("Save the example module as...")
        self.save_example_button.setToolTip("Save a minimal, valid module HTML file to start from")
        self.save_example_button.clicked.connect(self.save_example)
        buttons.addWidget(self.save_example_button)
        buttons.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self._headings: List[Tuple[str, int]] = []   # (title, position in the document)
        self._load_guide()

    # --- reading -------------------------------------------------------------------------------------

    def _load_guide(self) -> None:
        try:
            text = self.guide_path.read_text(encoding="utf-8")
        except OSError:
            self.browser.setPlainText(
                "The guide file was not found in this installation.\n\n"
                f"Expected: {self.guide_path}\n\nReinstalling the program restores it.")
            self.save_guide_button.setEnabled(False)
            return
        self.browser.setMarkdown(text)
        self._headings = self._collect_headings()
        for title, _position in self._headings:
            self.contents.addItem(QListWidgetItem(title))

    def _collect_headings(self) -> List[Tuple[str, int]]:
        """The level-2 headings (the numbered sections), with where they are in the document."""
        headings = []
        block = self.browser.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() == 2:
                headings.append((block.text().strip(), block.position()))
            block = block.next()
        return headings

    def _go_to_heading(self, row: int) -> None:
        if 0 <= row < len(self._headings):
            cursor = QTextCursor(self.browser.document())
            cursor.setPosition(self._headings[row][1])
            self.browser.setTextCursor(cursor)
            # put the heading at the top of the view
            bar = self.browser.verticalScrollBar()
            bar.setValue(bar.maximum())
            self.browser.ensureCursorVisible()

    def find_next(self) -> bool:
        """Select the next match of the find box (wrapping to the top); True when found."""
        needle = self.find_edit.text().strip()
        if not needle:
            return False
        if self.browser.find(needle):
            return True
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)  # wrap around
        return self.browser.find(needle)

    # --- saving copies -------------------------------------------------------------------------------

    def save_guide(self) -> Optional[Path]:
        return self._save_copy(self.guide_path, "Save the guide", "HTML Module Guide.md", "Markdown (*.md);;All files (*)")

    def save_example(self) -> Optional[Path]:
        return self._save_copy(self.template_path, "Save the example module", "module_template.html",
                               "HTML (*.html);;All files (*)")

    def _save_copy(self, source: Path, title: str, default_name: str, file_filter: str) -> Optional[Path]:
        if not source.is_file():
            QMessageBox.warning(self, title, f"The file was not found in this installation:\n{source}")
            return None
        target, _chosen = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not target:
            return None
        try:
            shutil.copyfile(source, target)
        except OSError as e:
            QMessageBox.warning(self, title, f"The file could not be saved:\n{e}")
            return None
        return Path(target)


def open_html_module_guide(parent=None) -> None:
    """Show the guide window (used by Help > HTML Module Guide and the import dialog)."""
    dialog = HtmlModuleGuideDialog(parent)
    dialog.exec()
