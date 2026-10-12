"""The HTML module guide: its content matches the importer, and the in-app window reads and saves it."""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QMessageBox

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "html_module_guide.md"
TEMPLATE = ROOT / "tools" / "html_module" / "module_template.html"


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)  # keep config/data out of the real profile
    return QApplication.instance() or QApplication([])


def test_the_guide_names_every_id_prefix_the_importer_knows():
    from services.html_module_parser import PREFIX_MAP, SESSION_PREFIX

    text = GUIDE.read_text(encoding="utf-8")
    for prefix in list(PREFIX_MAP) + [SESSION_PREFIX]:
        assert f"`{prefix}-`" in text, f"the guide does not explain the id prefix {prefix}-"
    for state in ("none", "unknown", "undecided"):                 # the data-faction values
        assert f"`{state}`" in text


def test_the_example_module_parses_cleanly_and_has_the_entries_the_guide_shows():
    from services.html_module_parser import parse_file

    module = parse_file(TEMPLATE)
    assert module.warnings == []
    assert {e.source_id for e in module.entities} >= {"c-boss", "f-guild", "l-yard", "item-key"}


def test_the_installer_bundles_the_guide_and_the_example():
    spec = (ROOT / "RPG_Database_Manager.spec").read_text(encoding="utf-8")
    assert "html_module_guide.md" in spec and "module_template.html" in spec
    assert GUIDE.is_file() and TEMPLATE.is_file()


def test_the_no_entities_warning_points_to_the_in_app_guide(tmp_path):
    from services.html_module_parser import parse_file

    page = tmp_path / "empty.html"
    page.write_text("<html><body><h1>Nothing</h1><p>text</p></body></html>", encoding="utf-8")
    assert any("Help > Guides" in w for w in parse_file(page).warnings)


def test_the_guide_window_lists_the_sections_and_finds_text(app):
    from gui.dialogs.html_module_guide import HtmlModuleGuideDialog

    dialog = HtmlModuleGuideDialog()
    try:
        titles = [dialog.contents.item(i).text() for i in range(dialog.contents.count())]
        assert titles[0].startswith("1. Quick start") and any("What the import warnings mean" in t for t in titles)
        assert len(titles) == 14 and titles[-1].startswith("For developers")    # 13 numbered sections and the developer notes
        dialog.contents.setCurrentRow(len(titles) - 1)                     # jump to the last section
        assert dialog.browser.textCursor().position() == dialog._headings[-1][1]
        dialog.find_edit.setText("faction table")
        assert dialog.find_next() is True
        assert "faction table" in dialog.browser.textCursor().selectedText().lower()
        dialog.find_edit.setText("zzzz-not-in-the-guide")
        assert dialog.find_next() is False
    finally:
        dialog.deleteLater()


def test_the_guide_window_saves_copies(app, tmp_path, monkeypatch):
    from gui.dialogs.html_module_guide import HtmlModuleGuideDialog

    dialog = HtmlModuleGuideDialog()
    try:
        target = tmp_path / "guide copy.md"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
        assert dialog.save_guide() == target
        assert target.read_text(encoding="utf-8") == GUIDE.read_text(encoding="utf-8")

        example = tmp_path / "my module.html"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(example), ""))
        assert dialog.save_example() == example and "c-boss" in example.read_text(encoding="utf-8")

        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))   # the user cancels
        assert dialog.save_guide() is None
    finally:
        dialog.deleteLater()


def test_the_guide_window_copes_with_a_missing_file(app, tmp_path, monkeypatch):
    from gui.dialogs.html_module_guide import HtmlModuleGuideDialog

    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    dialog = HtmlModuleGuideDialog(guide_path=tmp_path / "nope.md", template_path=tmp_path / "nope.html")
    try:
        assert "not found" in dialog.browser.toPlainText() and not dialog.save_guide_button.isEnabled()
        assert dialog.save_example() is None and shown and "not found" in shown[0]
    finally:
        dialog.deleteLater()


def test_help_menu_and_import_window_open_the_guide(app, tmp_path):
    from config.settings import Settings
    from gui.dialogs.html_module_import_dialog import HtmlModuleImportDialog
    from gui.main_window import MainWindow
    from models.database import DatabaseManager
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_file

    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("Guide", "d")
    settings = Settings()
    settings.set_last_module_id(module_id)
    window = MainWindow(settings, db)
    try:
        help_actions = {a.text(): a for a in window.menuBar().actions()[-1].menu().actions()}
        assert help_actions["&Guides (HTML module, entity file)..."].shortcut().toString() == "F1"

        dialog = HtmlModuleImportDialog(HtmlModuleImportService(db), parse_file(TEMPLATE), module_id, "Guide")
        try:
            assert dialog.guide_button.text() == "Format guide..."
            button_box = dialog.findChildren(QDialogButtonBox)[-1]
            assert dialog.guide_button in button_box.buttons()
        finally:
            dialog.deleteLater()
    finally:
        window.deleteLater()
