"""The .deb builder (packaging/linux/build_deb.py) and its place in the release workflow."""
import hashlib
import importlib.util
import io
import os
import re
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_deb", ROOT / "packaging" / "linux" / "build_deb.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_deb = _load_builder()


def _fake_dist(tmp_path) -> Path:
    dist = tmp_path / "dist" / "rpg-database-manager"
    (dist / "_internal" / "lib").mkdir(parents=True)
    (dist / "rpg-database-manager").write_bytes(b"\x7fELF fake program")
    (dist / "_internal" / "lib" / "libx.so.1").write_bytes(b"x" * 1500)           # an odd size on purpose
    (dist / "_internal" / "data.txt").write_text("hello", encoding="utf-8")
    try:
        os.symlink("libx.so.1", dist / "_internal" / "lib" / "libx.so")
    except (OSError, NotImplementedError):
        pass                                                                       # links need extra rights on Windows
    return dist


def _read_ar(path: Path):
    """The members of an ar archive: [(name, data)], checking the header layout on the way."""
    raw = path.read_bytes()
    assert raw[:8] == b"!<arch>\n"
    members, position = [], 8
    while position < len(raw):
        header = raw[position:position + 60]
        assert len(header) == 60 and header[58:60] == b"`\n"
        name, size = header[:16].decode().strip(), int(header[48:58])
        data = raw[position + 60:position + 60 + size]
        assert len(data) == size
        members.append((name, data))
        position += 60 + size + (size % 2)
    assert position == len(raw)
    return members


def _build(tmp_path, version="1.7.2"):
    dist = _fake_dist(tmp_path)
    return build_deb.build_deb(dist, tmp_path / "out", version), dist


def test_deb_version_numbers():
    assert build_deb.deb_version("1.7.2") == "1.7.2"
    assert build_deb.deb_version("1.7.2-beta.1") == "1.7.2~beta.1"         # a pre-release sorts before the release
    with pytest.raises(ValueError):
        build_deb.deb_version("v1.7.2")
    with pytest.raises(ValueError):
        build_deb.deb_version("1.7")


def test_the_default_version_is_the_app_version():
    from config.version import __version__
    assert build_deb.app_version() == __version__


def test_the_package_is_a_well_formed_deb(tmp_path):
    deb, _dist = _build(tmp_path)
    assert deb.name == "rpg-database-manager_1.7.2_amd64.deb"
    members = _read_ar(deb)
    assert [name for name, _data in members] == ["debian-binary", "control.tar.gz", "data.tar.xz"]
    assert members[0][1] == b"2.0\n"

    control_tar = tarfile.open(fileobj=io.BytesIO(members[1][1]), mode="r:gz")
    assert sorted(control_tar.getnames()) == [".", "./control", "./md5sums"]       # Python shows "./" as "."
    control = control_tar.extractfile("./control").read().decode()
    fields = dict(line.split(": ", 1) for line in control.splitlines() if re.match(r"^[A-Za-z-]+: ", line))
    assert fields["Package"] == "rpg-database-manager" and fields["Version"] == "1.7.2"
    assert fields["Architecture"] == "amd64" and fields["Installed-Size"].isdigit()
    assert "libxcb-cursor0" in fields["Depends"] and "libasound2 | libasound2t64" in fields["Depends"]
    assert control.endswith("\n") and "\nDescription: " in control
    assert all(line.startswith(" ") for line in control.split("\nDescription: ", 1)[1].splitlines()[1:])


def test_the_data_holds_the_program_the_menu_entry_and_the_link(tmp_path):
    deb, dist = _build(tmp_path)
    members = dict(_read_ar(deb))
    data_tar = tarfile.open(fileobj=io.BytesIO(members["data.tar.xz"]), mode="r:xz")
    entries = {info.name: info for info in data_tar.getmembers()}

    program = entries["./opt/rpg-database-manager/rpg-database-manager"]
    assert program.mode == 0o755 and program.isfile()
    assert data_tar.extractfile(program).read() == b"\x7fELF fake program"
    assert entries["./opt/rpg-database-manager/_internal/data.txt"].mode == 0o644

    link = entries["./usr/bin/rpg-database-manager"]
    assert link.issym() and link.linkname == "../../opt/rpg-database-manager/rpg-database-manager"
    if "./opt/rpg-database-manager/_internal/lib/libx.so" in entries:             # links inside the program are kept
        assert entries["./opt/rpg-database-manager/_internal/lib/libx.so"].linkname == "libx.so.1"

    desktop = data_tar.extractfile(entries["./usr/share/applications/rpg-database-manager.desktop"]).read().decode()
    assert "Exec=rpg-database-manager" in desktop and "Icon=rpg-database-manager" in desktop
    assert "./usr/share/icons/hicolor/512x512/apps/rpg-database-manager.png" in entries
    assert b"MIT License" in data_tar.extractfile(entries["./usr/share/doc/rpg-database-manager/copyright"]).read()

    # every parent folder is listed, and everything belongs to root
    for folder in (".", "./opt", "./opt/rpg-database-manager", "./usr", "./usr/bin", "./usr/share", "./usr/share/doc"):
        assert folder in entries and entries[folder].isdir() and entries[folder].mode == 0o755
    assert all((i.uid, i.gid, i.uname, i.gname) == (0, 0, "root", "root") for i in entries.values())


def test_md5sums_match_the_installed_files(tmp_path):
    deb, _dist = _build(tmp_path)
    members = dict(_read_ar(deb))
    control_tar = tarfile.open(fileobj=io.BytesIO(members["control.tar.gz"]), mode="r:gz")
    sums = dict(reversed(line.split("  ", 1)) for line in control_tar.extractfile("./md5sums").read().decode().splitlines())
    data_tar = tarfile.open(fileobj=io.BytesIO(members["data.tar.xz"]), mode="r:xz")
    files = {i.name[2:]: i for i in data_tar.getmembers() if i.isfile()}
    assert set(sums) == set(files) and "opt/rpg-database-manager/_internal/lib/libx.so.1" in sums
    for path, info in files.items():
        assert sums[path] == hashlib.md5(data_tar.extractfile(info).read()).hexdigest()


def test_a_prerelease_gets_a_tilde_version_in_the_file_name_and_control(tmp_path):
    deb, _dist = _build(tmp_path, "1.8.0-beta.1")
    assert deb.name == "rpg-database-manager_1.8.0~beta.1_amd64.deb"
    control = tarfile.open(fileobj=io.BytesIO(dict(_read_ar(deb))["control.tar.gz"]), mode="r:gz").extractfile("./control").read()
    assert b"Version: 1.8.0~beta.1\n" in control


def test_building_without_the_program_fails_clearly(tmp_path):
    empty = tmp_path / "dist" / "rpg-database-manager"
    empty.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="run pyinstaller first"):
        build_deb.build_deb(empty, tmp_path / "out", "1.7.2")


def test_the_release_workflow_builds_checks_and_attaches_the_deb():
    workflow = (ROOT / ".github" / "workflows" / "build-executables.yml").read_text(encoding="utf-8")
    linux = workflow.split("  linux:", 1)[1]
    assert "python packaging/linux/build_deb.py" in linux
    assert "dpkg-deb --info" in linux and "apt-get install -y" in linux and "apt-get remove -y rpg-database-manager" in linux
    assert "rpg-database-manager_*_amd64.deb" in linux.split("Attach the files to the release", 1)[1]
    assert linux.count(".deb") >= 4                                                  # built, checked, attached, kept as artifact
