"""Things the main window does by itself: the link graph, "last seen", the automation switches in the Tools menu.

These methods belong to MainWindow; they live here so the main window file stays readable.
"""

from typing import Optional

from PyQt6.QtGui import QAction

from services.link_service import LinkGraph, build_link_graph

AUTOMATION_SWITCHES = (
    ('auto_name_suggestions', "Name suggestions while typing (Tab)", True,
     "Grey text completes the name of an entry while you type; Tab makes it a link"),
    ('auto_new_names', "Offer new entries for names found in a text", True,
     "After saving, names that match no entry are offered as new entries"),
    ('auto_health_card', "Show 'Needs attention' and 'Not used for a while' on Home", True,
     "Home lists missing factions or pictures, duplicates, and entries not used for a while"),
    ('auto_backup_on_close', "Backup of the campaign when closing the program", True,
     "Keeps the last 7 backups next to the database"),
)


class AutomationMixin:
    """Methods of MainWindow for the link graph and the automation switches."""

    def _init_automation(self):
        self._link_graph: Optional[LinkGraph] = None

    # --- the link graph ----------------------------------------------------------------------------------

    def _get_link_graph(self) -> LinkGraph:
        """Who links to whom in the open campaign (built when first needed, forgotten when entries change)."""
        if self._link_graph is None:
            self._link_graph = build_link_graph(self.db, self.current_module_id) if self.current_module_id else LinkGraph()
        return self._link_graph

    def _invalidate_link_graph(self):
        self._link_graph = None

    def _last_seen_text(self, doc_id: int) -> str:
        seen = self._get_link_graph().last_seen(doc_id)
        if not seen:
            return ''
        date, title = seen
        return date or title

    def _last_seen_detail(self, doc_id: int) -> str:
        seen = self._get_link_graph().last_seen(doc_id)
        if not seen:
            return ''
        date, title = seen
        return f"{title} ({date})" if date else title

    # --- switches in Tools > Automation -------------------------------------------------------------------

    def automation_enabled(self, key: str) -> bool:
        default = next((d for k, _t, d, _tip in AUTOMATION_SWITCHES if k == key), True)
        return bool(self.settings.get_custom_setting(key, default))

    def _create_automation_menu(self, tools_menu):
        menu = tools_menu.addMenu("&Automation")
        self.automation_actions = {}
        for key, text, default, tip in AUTOMATION_SWITCHES:
            action = QAction(text, self)
            action.setCheckable(True)
            action.setChecked(bool(self.settings.get_custom_setting(key, default)))
            action.setStatusTip(tip)
            action.toggled.connect(lambda checked, k=key: self._on_automation_toggled(k, checked))
            menu.addAction(action)
            self.automation_actions[key] = action

    def _on_automation_toggled(self, key: str, checked: bool):
        self.settings.set_custom_setting(key, checked)
        self.settings.save_settings()

    # --- health check --------------------------------------------------------------------------------------

    def _health_issues(self):
        """The health check without what is waiting for Undo and what the scope hides."""
        from services.health_service import HealthIssue, check_campaign
        issues = []
        for issue in check_campaign(self.db, self.current_module_id, self._get_link_graph()):
            documents = [d for d in issue.documents
                         if d['id'] not in self._pending_deletes and self._in_scope(d['id'], d['entity_type'])]
            if issue.kind == 'duplicate':
                if len(documents) == 2:
                    issues.append(issue)
            elif documents:
                issues.append(HealthIssue(issue.kind, issue.label, documents))
        return issues

    def _on_health_check(self):
        """Tools > Health check: what needs attention in the open campaign."""
        from gui.dialogs.health_dialogs import HealthCheckDialog
        from utils.ui_helpers import show_info
        if not self.current_module_id:
            show_info(self, "No Campaign", "Create or open a campaign first.")
            return
        self._flush_pending_deletes()
        self._invalidate_link_graph()
        dialog = HealthCheckDialog(self._health_issues(), self)
        dialog.open_requested.connect(self._open_entry_by_id)
        dialog.merge_requested.connect(lambda keep, drop, d=dialog: self._merge_entries(keep, drop, d))
        dialog.exec()

    def _open_entry_by_id(self, doc_id: int):
        document = self.db.get_document(doc_id)
        if document:
            self._open_palette_entry(document)

    def _merge_entries(self, keep_id: int, drop_id: int, dialog=None):
        from services.health_service import merge_documents
        if drop_id in self._pins:
            self._pins = [keep_id if p == drop_id else p for p in self._pins]
            self._pins = list(dict.fromkeys(self._pins))
            self._save_pins()
        if merge_documents(self.db, keep_id, drop_id):
            self.status_bar.showMessage("Entries merged")
            self._load_documents()
            if dialog is not None:
                dialog.set_issues(self._health_issues())
        else:
            self.status_bar.showMessage("The entries could not be merged")

    # --- quick capture (Ctrl+Space) ------------------------------------------------------------------------

    def _capture_session(self) -> Optional[dict]:
        """The session a captured line goes to: the active one, else the latest by game date."""
        import json
        sessions = [d for d in self.db.get_documents(self.current_module_id, 'session')
                    if d['id'] not in self._pending_deletes]
        if not sessions:
            return None

        def meta(doc):
            try:
                return json.loads(doc['metadata']) if doc.get('metadata') else {}
            except (TypeError, ValueError):
                return {}
        active = [d for d in sessions if meta(d).get('status') == 'active']
        pool = active or sessions
        return max(pool, key=lambda d: (str(meta(d).get('session_date') or ''), d['id']))

    def _name_entries_for_capture(self):
        from config.entity_types import get_registry
        from utils.name_matching import NameEntry
        allowed = set(get_registry().keys_for('context')) - {'module'}
        return [NameEntry(d['title'], d['entity_type'], d['id'])
                for d in self.db.get_document_summaries(self.current_module_id)
                if d['entity_type'] in allowed and d['title'] and d['id'] not in self._pending_deletes]

    def _on_quick_capture(self):
        """Ctrl+Space: type one line, it is added to the current session with the time, names linked."""
        from datetime import date, datetime
        from PyQt6.QtWidgets import QDialog
        from gui.dialogs.quick_capture import QuickCaptureDialog
        from utils.name_matching import link_known_names
        from utils.ui_helpers import show_info
        if not self.current_module_id:
            show_info(self, "No Campaign", "Create or open a campaign first.")
            return
        session = self._capture_session()
        if session is None:
            session_id = self.session_service.create_session(self.current_module_id, date.today(),
                                                             f"Session {date.today()}", status='active')
            session = self.db.get_document(session_id) if session_id else None
            if session is None:
                return
        entries = self._name_entries_for_capture()

        def preview(text: str) -> str:
            linked = link_known_names(text, entries)
            names = [e.title for e in entries if f"({e.url})" in linked]
            return "Linked: " + ", ".join(names) if names else "No names of entries found in this line."

        dialog = QuickCaptureDialog(session['title'], preview, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.text():
            return
        line = f"- {datetime.now():%H:%M} {link_known_names(dialog.text(), entries)}"
        self._append_to_document(session, line)
        self.status_bar.showMessage(f"Added to {session['title']}")

    def _append_to_document(self, session: dict, line: str):
        """Add a line at the end of a document: through its open editor window if there is one, else in the database."""
        from gui.dialogs.document_viewer import DocumentViewerWindow
        viewer = DocumentViewerWindow.find_open(session['id'])
        if viewer is not None:
            viewer.append_note(line)
            return
        fresh = self.db.get_document(session['id'])
        content = (fresh.get('content') or '').rstrip()
        self.db.update_document(session['id'], fresh['title'], f"{content}\n{line}" if content else line, fresh.get('metadata'))
        self._on_document_saved('session')

    # --- relationship map ----------------------------------------------------------------------------------

    def _show_relationship_map(self, doc_id: int):
        from gui.dialogs.relationship_map import RelationshipMapDialog
        self._invalidate_link_graph()
        dialog = RelationshipMapDialog(self._get_link_graph(), doc_id, self)
        dialog.open_requested.connect(self._open_entry_by_id)
        dialog.exec()

    # --- automatic backup when closing --------------------------------------------------------------------

    AUTO_BACKUPS_KEPT = 7
    AUTO_BACKUP_MIN_MINUTES = 30

    def _auto_backup_on_close(self):
        """A backup of the open campaign next to the database; the last few are kept. Never blocks closing."""
        import re
        import time
        from config.paths import get_data_dir
        from services.backup_service import BackupService
        if not self.current_module_id or not self.automation_enabled('auto_backup_on_close'):
            return
        try:
            campaign = self.db.get_module(self.current_module_id) or {}
            slug = re.sub(r'[^\w\-]+', '_', campaign.get('name', 'campaign')).strip('_') or 'campaign'
            folder = get_data_dir() / "auto_backups"
            folder.mkdir(parents=True, exist_ok=True)
            existing = sorted(folder.glob(f"{slug}-*.zip"), key=lambda p: p.stat().st_mtime)
            if existing and time.time() - existing[-1].stat().st_mtime < self.AUTO_BACKUP_MIN_MINUTES * 60:
                return                              # closed and reopened a moment ago: the last backup is still fresh
            target = folder / f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
            ok, message, _missing = BackupService(self.db, self.image_service).backup_module(self.current_module_id, str(target))
            if not ok:
                self.logger.warning(f"Automatic backup failed: {message}")
                return
            for old in sorted(folder.glob(f"{slug}-*.zip"), key=lambda p: p.stat().st_mtime)[:-self.AUTO_BACKUPS_KEPT]:
                old.unlink(missing_ok=True)
        except Exception as e:
            self.logger.warning(f"Automatic backup failed: {e}")
