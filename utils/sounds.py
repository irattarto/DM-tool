"""Short notification sounds."""

from config.paths import resource_path
from utils.logger import get_logger

_effect = None


def _load():
    global _effect
    if _effect is None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect
        _effect = QSoundEffect()
        _effect.setSource(QUrl.fromLocalFile(str(resource_path("data/sounds/recording_stopped.wav"))))
        _effect.setVolume(1.0)
    return _effect


def prepare_recording_stopped() -> None:
    """Load the sound ahead of time so it plays without delay when it is needed."""
    try:
        _load()
    except Exception as e:
        get_logger('sounds').debug(f"Sound effect unavailable: {e}")


def play_recording_stopped() -> None:
    """Two soft tones: the recording was stopped by the time limit, not by the user.

    Falls back to the system beep when the sound cannot be played.
    """
    try:
        _load().play()
    except Exception as e:
        get_logger('sounds').debug(f"Sound effect unavailable, using the system beep: {e}")
        from PyQt6.QtWidgets import QApplication
        QApplication.beep()
