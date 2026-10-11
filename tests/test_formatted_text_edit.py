import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication

from gui.widgets.formatted_text_edit import FormattedTextEdit


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_remote_resources_are_not_loaded(app):
    w = FormattedTextEdit()
    assert w.loadResource(QTextDocument.ResourceType.ImageResource.value, QUrl("http://example.com/x.png")) is None


def test_network_share_resources_are_not_loaded(app):
    w = FormattedTextEdit()
    kind = QTextDocument.ResourceType.ImageResource.value
    for name in (r"\\attacker\share\x.png", "//attacker/share/x.png", "file://attacker/share/x.png",
                 "file:////attacker/share/x.png"):
        assert w.loadResource(kind, QUrl(name)) is None, name
