"""Downloads the NVIDIA CUDA libraries for GPU transcription off the GUI thread."""

from PyQt6.QtCore import QThread, pyqtSignal

from utils.logger import get_logger


class CudaDownloadWorker(QThread):
    status = pyqtSignal(str)
    done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('cuda_download_worker')

    def run(self):
        from services import cuda_libs, local_stt
        try:
            cuda_libs.download(progress=self.status.emit, should_stop=self.isInterruptionRequested)
            local_stt.reset_gpu_state()
            self.done.emit()
        except cuda_libs.CudaDownloadError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.logger.error(f"CUDA library download failed: {e}", exc_info=True)
            self.error.emit(f"GPU library setup failed: {type(e).__name__}: {str(e)[:160]}")
