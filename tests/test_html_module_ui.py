"""UI-level checks for imported modules: Module column, viewer badge, connections, safe saves."""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication

from tests.test_services.test_html_module_import import MODULE_HTML


@pytest.fixture(scope="module")
def app():
    QStandardPaths.setTestModeEnabled(True)
    return QApplication.instance() or QApplication([])


@pytest.fixture
def imported(tmp_path):
    from models.database import DatabaseManager
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_file

    path = tmp_path / "Test_Pass_NED.html"
    path.write_text(MODULE_HTML, encoding="utf-8")
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("Campaign", "d")
    svc = HtmlModuleImportService(db)
    result = svc.apply(svc.build_plan(parse_file(path), campaign))
    assert result.errors == []
    return db, campaign, result


def _doc(db, campaign, source_id):
    for d in db.get_documents(campaign):
        if d['metadata'] and json.loads(d['metadata']).get('source_id') == source_id:
            return d


def test_relationships_for_document_both_directions(imported):
    db, campaign, result = imported
    boss = _doc(db, campaign, 'c-boss')
    rows = db.get_relationships_for_document(boss['id'])
    kinds = {(r['relationship_type'], r['direction'], r['other_title']) for r in rows}
    assert ('belongs_to_module', 'out', 'Test Pass') in kinds
    assert ('member_of', 'out', 'Iron Guild') in kinds
    assert ('appears_in_scene', 'out', '1. Arrival') in kinds
    assert ('references', 'in', 'Iron Guild') in kinds          # the faction card mentions the boss
    module_rows = db.get_relationships_for_document(result.module_doc_id)
    assert sum(1 for r in module_rows if r['direction'] == 'in') == 9   # every imported document


def test_main_window_shows_module_column_and_menu(app, imported):
    from config.settings import Settings
    from gui.main_window import MainWindow

    db, campaign, _ = imported
    settings = Settings()
    settings.set_last_module_id(campaign)
    window = MainWindow(settings, db)
    try:
        tree = window.entity_lists['npc']
        labels = [tree.headerItem().text(i) for i in range(tree.columnCount())]
        assert labels[-2] == 'Module' and labels[-1] == 'Last seen'
        titles = {tree.topLevelItem(i).text(0): tree.topLevelItem(i).text(labels.index('Module'))
                  for i in range(tree.topLevelItemCount())}
        assert titles['Big Boss'] == 'Test Pass'
        assert window.entity_lists['module'].topLevelItemCount() == 1
        assert window.import_html_module_action.text().startswith('&Import HTML Module')
    finally:
        window.deleteLater()


def test_viewer_shows_badge_connections_and_keeps_metadata_on_save(app, imported):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    db, campaign, result = imported
    boss = _doc(db, campaign, 'c-boss')
    before = json.loads(boss['metadata'])
    viewer = DocumentViewerWindow(Document.from_dict(dict(boss)), db)
    try:
        assert viewer.module_badge.text() == "Imported from: Test Pass"
        tabs = [viewer.tab_widget.tabText(i) for i in range(viewer.tab_widget.count())]
        assert "Connections" in tabs
        viewer._on_save()
        after = json.loads(db.get_document(boss['id'])['metadata'])
        for key in ('module_doc_id', 'source_id', 'imported_raw_hash', 'imported_final_hash', 'faction_id'):
            assert after[key] == before[key]
    finally:
        viewer._is_dirty = False
        viewer.deleteLater()


def test_viewer_save_keeps_session_import_metadata(app, imported):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    db, campaign, _ = imported
    session = _doc(db, campaign, 'session-main')
    viewer = DocumentViewerWindow(Document.from_dict(dict(session)), db)
    try:
        viewer._on_save()
        after = json.loads(db.get_document(session['id'])['metadata'])
        assert after['source_id'] == 'session-main' and after['module_doc_id'] == json.loads(session['metadata'])['module_doc_id']
        assert after['session_type'] == 'game_session'
    finally:
        viewer._is_dirty = False
        viewer.deleteLater()


def test_clearing_faction_in_viewer_really_clears_it(app, imported):
    from gui.dialogs.document_viewer import DocumentViewerWindow
    from models.document import Document

    db, campaign, _ = imported
    boss = _doc(db, campaign, 'c-boss')
    viewer = DocumentViewerWindow(Document.from_dict(dict(boss)), db)
    try:
        viewer.faction_combo.setCurrentIndex(0)           # "(None)"
        viewer._on_save()
        after = json.loads(db.get_document(boss['id'])['metadata'])
        assert 'faction_id' not in after and after['source_id'] == 'c-boss'
    finally:
        viewer._is_dirty = False
        viewer.deleteLater()


def test_import_dialog_preview_selection_and_import(app, tmp_path):
    from PyQt6.QtCore import Qt
    from gui.dialogs.html_module_import_dialog import HtmlModuleImportDialog
    from models.database import DatabaseManager
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_file

    path = tmp_path / "Test_Pass_NED.html"
    path.write_text(MODULE_HTML, encoding="utf-8")
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("Campaign", "d")
    dialog = HtmlModuleImportDialog(HtmlModuleImportService(db), parse_file(path), campaign, "Campaign")
    try:
        groups = [dialog.tree.topLevelItem(i).text(0) for i in range(dialog.tree.topLevelItemCount())]
        assert groups[:2] == ['Modules', 'Sessions'] and 'NPCs' in groups
        assert "7 new" not in dialog.summary.text() and "new" in dialog.summary.text()

        # deselect the location row; it must survive an options rebuild and not be imported
        locations = next(dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())
                         if dialog.tree.topLevelItem(i).text(0) == 'Locations')
        locations.child(0).setCheckState(0, Qt.CheckState.Unchecked)
        dialog.prompts_check.setChecked(False)
        locations = next(dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())
                         if dialog.tree.topLevelItem(i).text(0) == 'Locations')
        assert locations.child(0).checkState(0) == Qt.CheckState.Unchecked

        dialog._do_import()
        assert dialog.import_result is not None and dialog.import_result.errors == []
        assert db.get_documents(campaign, 'location') == []
        assert len(db.get_documents(campaign, 'npc')) == 3
        assert 'Image prompt' not in db.get_documents(campaign, 'npc')[0]['content']
    finally:
        dialog.deleteLater()


def test_import_dialog_faction_table_and_automatic_factions(app, tmp_path):
    from gui.dialogs.html_module_import_dialog import HtmlModuleImportDialog
    from models.database import DatabaseManager
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_file

    path = tmp_path / "Test_Pass_NED.html"
    path.write_text(MODULE_HTML, encoding="utf-8")
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("Campaign", "d")
    dialog = HtmlModuleImportDialog(HtmlModuleImportService(db), parse_file(path), campaign, "Campaign")
    try:
        assert dialog.faction_table.rowCount() == 2                    # Lone Wolf and the minor clerk; Big Boss has a faction
        assert dialog.faction_table.item(0, 0).text() == "Lone Wolf"
        combo = dialog.faction_table.cellWidget(0, 1)
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "(no faction)", "Unknown faction", "Undecided yet", "Iron Guild", "+ New faction..."]

        combo.setCurrentIndex(combo.findData('f-guild'))               # the user picks a faction
        app.processEvents()
        assert dialog.faction_table.cellWidget(0, 1).currentData() == 'f-guild'   # survives the rebuild
        assert dialog._plan.unlinked == ['Dusty Clerk']                # the minor NPC is asked too, but still unlinked

        dialog.auto_factions_check.setChecked(True)                    # automatic factions join the options
        combo = dialog.faction_table.cellWidget(0, 1)
        assert combo.count() == 7 and combo.currentData() == 'f-guild'
        assert any(i.source_id == 'f-auto-monsters' for i in dialog._plan.items) is False   # nobody uses it

        dialog._do_import()
        assert dialog.import_result.errors == []
        loner = _doc(db, campaign, 'c-loner')
        guild = _doc(db, campaign, 'f-guild')
        assert json.loads(loner['metadata'])['faction_id'] == guild['id']
    finally:
        dialog.deleteLater()


TWO_LONERS = """<html lang="en"><body><h1>Loners</h1><section id="s">
<div class="card" id="f-guild"><h4>Iron Guild</h4><p>x</p></div>
<details class="npc-card" id="c-one"><summary><div class="npc-name">Ann</div></summary>
<div class="card-body"><p>A <b>smuggler</b> &lt;b&gt; who works the docks.</p></div></details>
<details class="npc-card" id="c-two"><summary><div class="npc-name">Ben</div></summary>
<div class="card-body"><p>Ann's brother.</p></div></details></section></body></html>"""


def test_import_dialog_new_faction_is_selectable_for_other_npcs_and_npc_tooltips(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog
    from gui.dialogs.html_module_import_dialog import _NEW_FACTION_CHOICE, HtmlModuleImportDialog
    from models.database import DatabaseManager
    from services.html_module_import_service import HtmlModuleImportService
    from services.html_module_parser import parse_file

    path = tmp_path / "Loners_NED.html"
    path.write_text(TWO_LONERS, encoding="utf-8")
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("Campaign", "d")
    dialog = HtmlModuleImportDialog(HtmlModuleImportService(db), parse_file(path), campaign, "Campaign")
    try:
        table = dialog.faction_table
        assert table.rowCount() == 2
        assert "A smuggler &lt;b&gt; who works the docks." in table.item(0, 0).toolTip()   # description to decide by, escaped
        assert "Ann's brother." in table.cellWidget(1, 1).toolTip().replace('&#x27;', "'")
        combo = table.cellWidget(0, 1)
        assert combo.itemData(combo.count() - 1) == _NEW_FACTION_CHOICE

        # cancelling puts the drop-down back
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
        combo.setCurrentIndex(combo.count() - 1)
        app.processEvents()
        assert table.cellWidget(0, 1).currentData() == ''

        # a typed name creates a faction that both NPCs can then use
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Dock Rats", True)))
        table.cellWidget(0, 1).setCurrentIndex(table.cellWidget(0, 1).count() - 1)
        app.processEvents()
        assert table.cellWidget(0, 1).currentText() == "Dock Rats (new)"
        second = table.cellWidget(1, 1)
        assert second.findData('f-new-dock-rats') >= 0 and second.currentData() == ''
        second.setCurrentIndex(second.findData('f-new-dock-rats'))
        app.processEvents()

        # typing an existing name reuses that faction instead of making a second one
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("iron guild", True)))
        table.cellWidget(1, 1).setCurrentIndex(table.cellWidget(1, 1).count() - 1)
        app.processEvents()
        assert table.cellWidget(1, 1).currentData() == 'f-guild'
        table.cellWidget(1, 1).setCurrentIndex(table.cellWidget(1, 1).findData('f-new-dock-rats'))
        app.processEvents()

        dialog._do_import()
        assert dialog.import_result.errors == []
        rats = _doc(db, campaign, 'f-new-dock-rats')
        assert rats['title'] == "Dock Rats"
        for source_id in ('c-one', 'c-two'):
            assert json.loads(_doc(db, campaign, source_id)['metadata'])['faction_id'] == rats['id']
        assert len(db.get_documents(campaign, 'faction')) == 2                       # Iron Guild + Dock Rats
    finally:
        dialog.deleteLater()


def test_import_dialog_offers_existing_entries_with_a_choice(app, tmp_path):
    from PyQt6.QtCore import Qt
    from gui.dialogs.html_module_import_dialog import HtmlModuleImportDialog
    from models.database import DatabaseManager
    from services.html_module_import_service import ACTION_OVERWRITE, HtmlModuleImportService
    from services.html_module_parser import parse_file

    path = tmp_path / "Test_Pass_NED.html"
    path.write_text(MODULE_HTML.replace('<div class="npc-name">Lone Wolf</div>', '<div class="npc-name">Big Boss</div>'),
                    encoding="utf-8")
    db = DatabaseManager(":memory:")
    db.initialize_database()
    campaign = db.create_module("Campaign", "d")
    boss = db.create_document(campaign, "npc", "Big Boss", "My own notes.")
    dialog = HtmlModuleImportDialog(HtmlModuleImportService(db), parse_file(path), campaign, "Campaign")
    try:
        def boss_row():
            npcs = next(dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())
                        if dialog.tree.topLevelItem(i).text(0) == 'NPCs')
            return next(npcs.child(i) for i in range(npcs.childCount())
                        if npcs.child(i).data(0, Qt.ItemDataRole.UserRole) == 'c-boss')

        combo = dialog.tree.itemWidget(boss_row(), 1)
        assert [combo.itemText(i) for i in range(combo.count())] == ["Use existing", "Overwrite existing", "Create new"]
        assert combo.currentText() == "Use existing" and "existing: Big Boss" in boss_row().text(2)
        assert "use an entry the campaign already has" in dialog.summary.text()
        assert "c-loner" in dialog.summary.text()                   # the second "Big Boss" card is warned about
        combo.setCurrentIndex(combo.findData('overwrite'))
        app.processEvents()
        assert next(i for i in dialog._plan.items if i.source_id == 'c-boss').action == ACTION_OVERWRITE
        assert dialog.tree.itemWidget(boss_row(), 1).currentText() == "Overwrite existing"   # survives the rebuild
        dialog._do_import()
        assert dialog.import_result.errors == []
        assert "My own notes." not in db.get_document(boss)['content']
    finally:
        dialog.deleteLater()
