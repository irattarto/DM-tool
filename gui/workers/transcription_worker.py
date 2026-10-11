"""Speech-to-text off the GUI thread (Google needs the network, Whisper loads and runs a model)."""

import os
import tempfile
import time

from PyQt6.QtCore import QThread, pyqtSignal

from utils.logger import get_logger


class TranscriptionWorker(QThread):
    """Transcribe one recording; emits the text or a readable error."""

    status = pyqtSignal(str)
    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio_data, provider: str, language: str, whisper_model: str = "base",
                 whisper_device: str = "auto", parent=None):
        super().__init__(parent)
        self.audio_data = audio_data
        self.provider = provider
        self.language = language
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.logger = get_logger('transcription_worker')

    def run(self):
        try:
            if self.provider == "whisper":
                text = self._whisper()
            else:
                text = self._google()
            self.result_ready.emit(text)
        except _UserMessage as e:
            self.error.emit(str(e))
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}", exc_info=True)
            self.error.emit(f"Transcription failed: {_describe(e)}")

    def _google(self) -> str:
        try:
            import speech_recognition as sr
        except ImportError:
            raise _UserMessage("Speech recognition not available - check dependencies")
        self.status.emit(f"Transcribing with Google ({self.language})...")
        try:
            return sr.Recognizer().recognize_google(self.audio_data, language=self.language)
        except sr.UnknownValueError:
            raise _UserMessage("Could not understand audio")
        except sr.RequestError as e:
            raise _UserMessage(f"API error: {e}")

    def _whisper(self) -> str:
        """Local, offline transcription (GPU when usable, otherwise CPU)."""
        from services import local_stt
        wav_data = self.audio_data.get_wav_data()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(wav_data)
            temp_path = temp_file.name
        try:
            plan = local_stt.resolve_plan(self.whisper_model, self.whisper_device)
            self.status.emit(f"Transcribing locally with {plan.describe()}...")
            started = time.monotonic()
            self.logger.info(f"Local transcription started: plan={plan.model}/{plan.device}/{plan.compute_type}, "
                             f"{len(wav_data) // 32000} s of audio")
            segments, used = local_stt.transcribe_file(
                temp_path, plan, language=self.language, status=self.status.emit)
            elapsed = time.monotonic() - started
            self.logger.info(f"Local transcription finished in {elapsed:.1f} s on {used.device}")
            if used.device != plan.device:
                self.status.emit(f"Transcribed on the CPU in {elapsed:.0f} s (the GPU could not be used).")
            else:
                self.status.emit(f"Transcribed on the {'GPU' if used.device == 'cuda' else 'CPU'} in {elapsed:.0f} s.")
            return " ".join(seg.text for seg in segments).strip()
        except RuntimeError as e:
            raise _UserMessage(str(e))
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

class _UserMessage(Exception):
    """An error whose text can be shown to the user as is."""


def _describe(error: Exception) -> str:
    """A short, actionable reason (the full traceback is in the log file)."""
    text = f"{type(error).__name__}: {error}".strip()
    lowered = text.lower()
    if any(w in lowered for w in ("connection", "resolve", "timed out", "offline", "huggingface", "ssl", "proxy")):
        return (f"the speech model could not be downloaded ({text[:160]}). Check the internet connection "
                "(only needed once), or choose Google in Preferences.")
    if any(w in lowered for w in ("cuda", "cublas", "cudnn", "out of memory")):
        return f"the graphics card could not be used ({text[:160]}). Set the compute device to CPU in Preferences."
    return text[:240]
