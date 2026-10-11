"""ImageService safety tests."""
import pytest
from PyQt6.QtGui import QImage, QColor

from services.image_service import ImageService


@pytest.fixture
def svc(tmp_path):
    return ImageService(tmp_path / "imgs")


def _png(path, w=8, h=8):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    assert img.save(str(path))
    return path


def test_save_and_delete_roundtrip(svc, tmp_path):
    meta = svc.save_image(str(_png(tmp_path / "a.png")), 1)
    assert meta and svc.get_image_path(1, meta["filename"])
    assert svc.delete_image(1, meta["filename"])


def test_path_traversal_is_neutralised(svc, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    assert not svc.delete_image(1, "../../../victim.txt") or victim.exists()
    assert victim.exists()
    assert svc.get_image_path(1, "../../../victim.txt") is None


def test_pixel_limit_rejected(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(ImageService, "MAX_IMAGE_PIXELS", 10)
    assert svc.save_image(str(_png(tmp_path / "big.png", 8, 8)), 1) is None


def test_bytes_path_validates_module_and_size(svc, monkeypatch):
    assert svc.save_image_from_bytes(b"x", 0, "a.png") is None
    monkeypatch.setattr("config.constants.IMAGE_MAX_SIZE_BYTES", 4)
    assert svc.save_image_from_bytes(b"x" * 10, 1, "a.png") is None
