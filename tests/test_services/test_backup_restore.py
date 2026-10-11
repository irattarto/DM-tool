"""Backup/restore safety tests."""
import json
import zipfile

import pytest

from services.backup_service import BackupService


class _StubImages:
    def regenerate_thumbnails_for_module(self, module_id):
        return 0


@pytest.fixture
def svc(temp_db, tmp_path):
    s = BackupService(temp_db, _StubImages())
    s.base_path = tmp_path
    s.images_path = tmp_path / "rpg_images" / "modules"
    return s


def _make_module(db):
    mod = db.create_module("Mod", "d")
    db.create_document(mod, "npc", "Alice", "Original body")
    return mod


def test_failed_overwrite_restores_previous_data(svc, temp_db, tmp_path, monkeypatch):
    mod = _make_module(temp_db)
    zip_path = str(tmp_path / "b.zip")
    ok, _, _ = svc.backup_module(mod, zip_path)
    assert ok
    ok, meta, _ = svc.validate_backup(zip_path)
    assert ok

    real_import = svc._import_module_data
    calls = {"n": 0}

    def flaky_import(data, module_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "boom"
        return real_import(data, module_id)

    monkeypatch.setattr(svc, "_import_module_data", flaky_import)
    ok, _, msg = svc._restore_overwrite_module(zip_path, meta, mod)
    assert not ok and "restored" in msg
    titles = [d["title"] for d in temp_db.get_documents(mod)]
    assert titles == ["Alice"]


def test_zip_with_too_many_entries_is_rejected(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(BackupService, "MAX_ZIP_ENTRIES", 3)
    p = tmp_path / "bomb.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"module_name": "x", "backup_date": "d", "backup_version": "2.0"}))
        zf.writestr("module_data.json", "{}")
        for i in range(5):
            zf.writestr(f"images/{i}.png", b"x")
    ok, _, msg = svc.validate_backup(str(p))
    assert not ok and "too many" in msg


def test_non_image_entries_are_not_extracted(svc, tmp_path):
    p = tmp_path / "b.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("images/ok.png", b"x")
        zf.writestr("images/evil.exe", b"x")
        zf.writestr("images/..", b"x")
    with zipfile.ZipFile(p) as zf:
        assert svc._image_entries(zf) == [("images/ok.png", "ok.png")]
