"""Discord UI: send dialog (preview + confirm), settings tab, module channel dialog, hooks."""
import asyncio
import threading
import time

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication

from gui.dialogs.discord_send_dialog import DiscordSendDialog, SendItem
from gui.dialogs.discord_settings_widget import DiscordSettingsWidget
from gui.dialogs.module_discord_channel_dialog import ModuleDiscordChannelDialog
from models.database import DatabaseManager
from services.discord_service import DiscordClient
from services.discord_settings import DiscordSettings
from tests.test_discord_service import FakeDiscord, TOKEN
from tests.test_discord_settings import FakeSecure

from aiohttp import web


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_server():
    """A fake Discord API served from its own thread (the GUI workers call it from theirs)."""
    fake = FakeDiscord()
    state = {}
    started = threading.Event()

    def serve():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(fake.app())
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, '127.0.0.1', 0)
        loop.run_until_complete(site.start())
        state['port'] = site._server.sockets[0].getsockname()[1]
        state['loop'], state['runner'] = loop, runner
        started.set()
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())
        loop.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert started.wait(10)
    fake.base_url = f"http://127.0.0.1:{state['port']}/api/v10"
    fake.factory = lambda: DiscordClient(TOKEN, base_url=fake.base_url)
    yield fake
    state['loop'].call_soon_threadsafe(state['loop'].stop)
    thread.join(5)


@pytest.fixture
def configured_db(monkeypatch):
    import utils.crypto_utils as crypto
    monkeypatch.setattr(crypto, "get_secure_storage", lambda: FakeSecure())
    db = DatabaseManager(":memory:")
    db.initialize_database()
    settings = DiscordSettings(db, FakeSecure())
    settings.set_token(TOKEN)
    settings.set_guild("100000000000000010", "My Campaign")
    module_id = db.create_module("Campaign", "d")
    db.set_module_discord_channel(module_id, "100000000000000022", "rolls")
    return db, module_id


def wait(cond, app, timeout=10):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    return cond()


def _png(tmp_path, name="aria.png"):
    from PyQt6.QtGui import QImage, QColor
    path = tmp_path / name
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path))
    return str(path)


def test_send_dialog_preselects_module_channel_warns_and_sends_image_with_name(app, fake_server, configured_db, tmp_path):
    db, module_id = configured_db
    path = _png(tmp_path)
    dialog = DiscordSendDialog(db, module_id, [SendItem(kind='image', path=path, caption="Aria the Bold")],
                               client_factory=fake_server.factory)
    try:
        assert wait(lambda: dialog.channel_combo.count() > 0, app)
        assert dialog.channel_combo.currentText() == "#rolls" and dialog.channel_combo.currentData() == "100000000000000022"
        assert "publicly" in dialog.warning_label.text() and "#rolls" in dialog.warning_label.text()
        assert "My Campaign" in dialog.warning_label.text()
        assert dialog.send_btn.isEnabled()
        assert not fake_server.messages  # nothing is posted before the user confirms

        dialog.send_btn.click()
        assert wait(lambda: fake_server.messages, app)
        assert wait(lambda: dialog._worker is None, app)
        cid, payload, attachments = fake_server.messages[0]
        assert cid == "100000000000000022" and payload['content'] == "Aria the Bold"
        assert attachments[0][0] == "aria.png"
        assert "Sent 1 message" in dialog.status_label.text()
    finally:
        dialog.deleteLater()


def test_send_dialog_text_preview_and_split(app, fake_server, configured_db):
    db, module_id = configured_db
    text = "Paragraph. " * 400   # about 4400 characters -> 3 messages
    dialog = DiscordSendDialog(db, module_id, [SendItem(kind='text', text=text)], client_factory=fake_server.factory)
    try:
        assert wait(lambda: dialog.channel_combo.count() > 0, app)
        assert "3 messages" in dialog.send_btn.text()
        dialog.channel_combo.setCurrentIndex(dialog.channel_combo.findData("100000000000000021"))  # switch to #handouts
        dialog.send_btn.click()
        assert wait(lambda: len(fake_server.messages) == 3, app)
        assert {m[0] for m in fake_server.messages} == {"100000000000000021"}
    finally:
        assert wait(lambda: dialog._worker is None, app)
        dialog.deleteLater()


def test_send_dialog_error_is_shown_and_user_can_retry(app, fake_server, configured_db):
    db, module_id = configured_db
    fake_server.fail_with["100000000000000022"] = 403
    dialog = DiscordSendDialog(db, module_id, [SendItem(kind='text', text="hello")], client_factory=fake_server.factory)
    try:
        assert wait(lambda: dialog.channel_combo.count() > 0, app)
        dialog.send_btn.click()
        assert wait(lambda: "not allowed" in dialog.status_label.text(), app)
        assert wait(lambda: dialog._worker is None, app)
        assert dialog.send_btn.isEnabled() and dialog.cancel_btn.isEnabled()
    finally:
        dialog.deleteLater()


def test_send_dialog_without_setup_cannot_send(app):
    db = DatabaseManager(":memory:")
    db.initialize_database()
    dialog = DiscordSendDialog(db, None, [SendItem(kind='text', text="x")])
    try:
        assert "not set up" in dialog.status_label.text()
        assert not dialog.send_btn.isEnabled()
    finally:
        dialog.deleteLater()


def test_send_dialog_cannot_be_closed_while_sending(app, fake_server, configured_db):
    db, module_id = configured_db
    slow = {'release': threading.Event()}

    class SlowFactory:
        def __call__(self):
            client = fake_server.factory()
            original = client.send_text

            async def slow_send(channel_id, text):
                while not slow['release'].is_set():
                    await asyncio.sleep(0.01)
                return await original(channel_id, text)
            client.send_text = slow_send
            return client

    dialog = DiscordSendDialog(db, module_id, [SendItem(kind='text', text="hi")], client_factory=SlowFactory())
    try:
        assert wait(lambda: dialog.channel_combo.count() > 0, app)
        dialog.send_btn.click()
        assert wait(dialog.is_busy, app)
        dialog.show()
        dialog.reject()
        assert dialog.isVisible()
        assert not dialog.cancel_btn.isEnabled()
    finally:
        slow['release'].set()
        assert wait(lambda: dialog._worker is None, app)
        dialog.deleteLater()


def test_settings_widget_connects_loads_servers_and_saves_encrypted(app, fake_server, monkeypatch):
    import utils.crypto_utils as crypto
    monkeypatch.setattr(crypto, "get_secure_storage", lambda: FakeSecure())
    db = DatabaseManager(":memory:")
    db.initialize_database()
    widget = DiscordSettingsWidget(db, client_builder=lambda token: DiscordClient(token, base_url=fake_server.base_url))
    try:
        widget.token_edit.setText(TOKEN)
        widget._mark_dirty()
        widget._on_connect()
        assert wait(lambda: widget.guild_combo.count() == 1, app)
        assert "Connected as RollBot" in widget.status_label.text()
        assert widget.apply() is True
        settings = DiscordSettings(db, FakeSecure())
        assert settings.get_token() == TOKEN and settings.get_guild() == ("100000000000000010", "My Campaign")
        assert TOKEN not in (db.get_app_meta('discord_bot_token') or "")
        assert widget.token_edit.text() == ""  # the token is not kept on screen

        widget._on_remove()
        assert not settings.has_token() and settings.get_guild() == (None, None)
    finally:
        assert wait(lambda: widget._worker is None, app)
        widget.deleteLater()


def test_settings_widget_rejects_bad_token_and_shows_wrong_token_error(app, fake_server):
    db = DatabaseManager(":memory:")
    db.initialize_database()
    widget = DiscordSettingsWidget(db, client_builder=lambda token: DiscordClient(token, base_url=fake_server.base_url))
    try:
        widget.token_edit.setText("nope")
        widget._mark_dirty()
        assert widget.apply() is False and "does not look like" in widget.status_label.text()

        widget.token_edit.setText("Y" * 60)
        widget._on_connect()
        assert wait(lambda: "rejected" in widget.status_label.text(), app)
    finally:
        assert wait(lambda: widget._worker is None, app)
        widget.deleteLater()


def test_module_channel_dialog_lists_channels_and_saves_link(app, fake_server, configured_db):
    db, module_id = configured_db
    module = db.get_module(module_id)
    dialog = ModuleDiscordChannelDialog(db, module, client_factory=fake_server.factory)
    try:
        assert wait(lambda: dialog.combo.count() > 3, app)
        assert dialog.combo.currentText() == "#rolls"  # current link stays selected
        dialog.combo.setCurrentIndex(dialog.combo.findData("100000000000000021"))
        dialog._on_save()
        assert db.get_module(module_id)['discord_channel_id'] == "100000000000000021"
        assert db.get_module(module_id)['discord_channel_name'] == "handouts"

        dialog2 = ModuleDiscordChannelDialog(db, db.get_module(module_id), client_factory=fake_server.factory)
        assert wait(lambda: dialog2.combo.count() > 3, app)
        dialog2.combo.setCurrentIndex(0)
        dialog2._on_save()
        assert db.get_module(module_id)['discord_channel_id'] is None
        dialog2.deleteLater()
    finally:
        assert wait(lambda: dialog._worker is None, app)
        dialog.deleteLater()


def test_image_actions_use_the_entity_name_as_caption(app, tmp_path, monkeypatch):
    import gui.discord_actions as actions
    db = DatabaseManager(":memory:")
    db.initialize_database()
    module_id = db.create_module("M", "d")
    doc_id = db.create_document(module_id, "npc", "Aria the Bold", "body")
    captured = {}

    class Capture:
        def __init__(self, db, module_id, items, parent=None):
            captured['items'] = items

        def exec(self):
            return 0

    monkeypatch.setattr(actions, "DiscordSendDialog", Capture)
    path = _png(tmp_path)
    name = actions.entity_name_for(db, doc_id)
    actions.send_images_to_discord(None, db, module_id, [{'file_path': path, 'original_name': 'x.png'}], name)
    assert [(i.kind, i.caption) for i in captured['items']] == [('image', 'Aria the Bold')]
    assert actions.entity_name_for(db, None, "fallback") == "fallback"


def test_gallery_has_discord_entry_points(app, tmp_path):
    from gui.image_gallery_widget import ImageThumbnail
    thumb = ImageThumbnail({'file_path': _png(tmp_path), 'original_name': 'a.png'}, 0)
    seen = []
    thumb.discord_requested.connect(seen.append)
    thumb.discord_requested.emit(0)
    assert seen == [0]


# --- entity picker + embed cards ----------------------------------------------
def test_picker_sorts_by_name_skips_missing_images_and_filters(app, tmp_path):
    from gui.dialogs.discord_entity_picker import DiscordEntityPickerDialog, EntityChoice
    path = _png(tmp_path)
    choices = [EntityChoice(1, "zed", path), EntityChoice(2, "Bram", ""), EntityChoice(3, "aria", path),
               EntityChoice(4, "Cora", path)]
    dialog = DiscordEntityPickerDialog(choices, "NPCs", preselected_ids=[4])
    try:
        names = [dialog.list_widget.item(i).data(0x0100).name for i in range(4)]
        assert names == ["aria", "Bram", "Cora", "zed"]
        assert [c.id for c in dialog.selected_choices()] == [4]
        assert "1 skipped" in dialog.summary_label.text() and dialog.send_btn.isEnabled()
        dialog._set_visible_checked(True)
        assert [c.name for c in dialog.selected_choices()] == ["aria", "Cora", "zed"]   # Bram has no image
        dialog.search_edit.setText("or")
        dialog._set_visible_checked(False)
        assert [c.name for c in dialog.selected_choices()] == ["aria", "zed"]   # only the visible Cora was cleared
        dialog._set_visible_checked(False)
        dialog.search_edit.setText("")
        dialog._set_visible_checked(False)
        assert not dialog.selected_choices() and not dialog.send_btn.isEnabled()
    finally:
        dialog.deleteLater()


def test_entity_choices_use_the_primary_image_only(app, configured_db, tmp_path):
    from gui.discord_actions import entity_choices
    db, module_id = configured_db
    with_image = db.create_document(module_id, "npc", "Aria", "x")
    db.create_document(module_id, "npc", "Bram", "x")
    path = _png(tmp_path)
    image_id = db.save_image_record(module_id, with_image, "aria.png", "aria.png", path, 10, "image/png")
    db.set_primary_image(with_image, image_id)
    choices = {c.name: c for c in entity_choices(db, module_id, "npc")}
    assert choices["Aria"].path == path and choices["Bram"].path == ""


def test_send_dialog_posts_embed_cards_and_retry_skips_sent(app, fake_server, configured_db, tmp_path):
    db, module_id = configured_db
    path = _png(tmp_path)
    items = [SendItem(kind='embed', path=path, caption=f"NPC {i}") for i in range(12)]
    dialog = DiscordSendDialog(db, module_id, items, client_factory=fake_server.factory)
    try:
        assert wait(lambda: dialog.channel_combo.count() > 0, app)
        assert "12 cards in about 2 messages" in dialog.send_btn.text()
        dialog.send_btn.click()
        assert wait(lambda: len(fake_server.messages) == 2, app)
        assert wait(lambda: dialog._worker is None, app)
        assert [len(m[1]['embeds']) for m in fake_server.messages] == [10, 2]
        assert "Sent 12 cards" in dialog.status_label.text()
    finally:
        dialog.deleteLater()
