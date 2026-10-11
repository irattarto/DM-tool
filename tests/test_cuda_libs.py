"""CUDA library download helpers (no network)."""
import io
import zipfile

import pytest

from services import cuda_libs


def make_wheel(path, names):
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            zf.writestr(name, b"dll")
        zf.writestr("nvidia/cudnn/include/readme.txt", b"x")


def test_extract_takes_only_dlls_from_bin_and_flattens(tmp_path):
    wheel = tmp_path / "w.whl"
    make_wheel(wheel, ["nvidia/cudnn/bin/cudnn64_9.dll", "nvidia/cublas/bin/cublas64_12.dll",
                       "../../evil/bin/escape.dll"])
    out = tmp_path / "out"
    out.mkdir()
    names = cuda_libs._extract_dlls(wheel, out)
    assert sorted(names) == ["cublas64_12.dll", "cudnn64_9.dll", "escape.dll"]
    assert sorted(p.name for p in out.iterdir()) == sorted(names)  # nothing written outside the folder
    assert not (tmp_path / "evil").exists()


def test_checksum_mismatch_is_rejected(tmp_path):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"not the real file"

    class FakeRequests:
        @staticmethod
        def get(url, stream, timeout):
            return Response()

    wheel = {"filename": "nvidia_x-1-win_amd64.whl", "url": "https://x", "size": 17,
             "digests": {"sha256": "0" * 64}}
    with pytest.raises(cuda_libs.CudaDownloadError, match="checksum"):
        cuda_libs._download_file(FakeRequests, wheel, tmp_path / "f.part", lambda m: None, None)
