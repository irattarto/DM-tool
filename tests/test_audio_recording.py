"""Microphone errors are explained in plain language; the build ships PyAudio."""
import pathlib
import sys
import types

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QCoreApplication

from utils import audio_recording as ar
from utils.audio_recording import AudioRecordingThread, friendly_microphone_error, microphone_support_status

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.mark.parametrize("error, expected", [
    (AttributeError("Could not find PyAudio; check installation"), ar.MSG_NO_PYAUDIO),
    (ImportError("No module named 'pyaudio'"), ar.MSG_NO_PYAUDIO),
    (OSError("No Default Input Device Available"), ar.MSG_NO_MICROPHONE),
    (OSError(-9996, "Invalid input device (no default output device)"), ar.MSG_NO_MICROPHONE),
    (OSError(10013, "An attempt was made to access a socket in a way forbidden by its access permissions"), ar.MSG_ACCESS_DENIED),
    (PermissionError("Permission denied"), ar.MSG_ACCESS_DENIED),
])
def test_known_errors_get_actionable_messages(error, expected):
    assert friendly_microphone_error(error) == expected


def test_unknown_error_keeps_the_technical_text():
    assert friendly_microphone_error(RuntimeError("boom")) == "Failed to initialize microphone: boom"


def _run_with_microphone_error(app, monkeypatch, error):
    class FakeSR(types.ModuleType):
        class Microphone:
            def __init__(self, *a, **k):
                raise error

    monkeypatch.setitem(sys.modules, "speech_recognition", FakeSR("speech_recognition"))
    thread = AudioRecordingThread()
    messages = []
    thread.recording_error.connect(messages.append)
    thread.run()  # synchronously: signals are delivered directly in the same thread
    return messages


def test_thread_reports_missing_pyaudio_in_plain_language(app, monkeypatch):
    messages = _run_with_microphone_error(app, monkeypatch, AttributeError("Could not find PyAudio; check installation"))
    assert messages == [ar.MSG_NO_PYAUDIO]


def test_thread_reports_missing_microphone_in_plain_language(app, monkeypatch):
    messages = _run_with_microphone_error(app, monkeypatch, OSError("No Default Input Device Available"))
    assert messages == [ar.MSG_NO_MICROPHONE]


def test_support_status_reflects_pyaudio_availability(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyaudio", None)  # makes `import pyaudio` fail
    ok, reason = microphone_support_status()
    assert not ok and reason == ar.MSG_NO_PYAUDIO


def test_pyaudio_is_a_declared_dependency_and_bundled():
    assert "pyaudio" in (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "requirements.txt" in (ROOT / "setup.py").read_text(encoding="utf-8")   # setup.py reads it
    assert "'pyaudio'" in (ROOT / "RPG_Database_Manager.spec").read_text(encoding="utf-8")
