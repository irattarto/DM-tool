#!/usr/bin/env python3
"""Build a .deb package from the PyInstaller onedir output (dist/rpg-database-manager).

A .deb is an ar archive holding `debian-binary`, `control.tar.*` and `data.tar.*`. This script writes
all three with the standard library only, so it needs no dpkg and can be built and tested anywhere.
The release workflow then checks the result with the real `dpkg-deb`, installs it, starts it and removes it.

Usage (from the repository root):
    python packaging/linux/build_deb.py [--dist dist/rpg-database-manager] [--output .] [--version 1.7.2] [--arch amd64]

Installed layout:
    /opt/rpg-database-manager/            the program (the whole PyInstaller folder)
    /usr/bin/rpg-database-manager         link to the program
    /usr/share/applications/...desktop    menu entry
    /usr/share/icons/hicolor/512x512/...  icon
    /usr/share/doc/rpg-database-manager/copyright
"""

import argparse
import hashlib
import io
import os
import re
import stat
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = "rpg-database-manager"
INSTALL_DIR = f"opt/{PACKAGE}"
HOMEPAGE = "https://github.com/irattarto/DM-tool"
MAINTAINER = "RPG Database Manager Team <76449222+irattarto@users.noreply.github.com>"
SHORT_DESCRIPTION = "Campaign manager for tabletop RPG game masters"
LONG_DESCRIPTION = [
    "Organise the NPCs, factions, locations, items, quests and sessions of a tabletop",
    "RPG campaign in one place: pictures in every list, a Home page, quick search,",
    "pinned entries for tonight's session, speech-to-text session notes, backups,",
    "and import of HTML adventure modules.",
]
# The bundled Qt needs these system libraries (the AppImage build installs the same set)
DEPENDS = [
    "libc6 (>= 2.35)", "libegl1", "libgl1", "libglib2.0-0", "libfontconfig1", "libdbus-1-3",
    "libxkbcommon-x11-0", "libxcb-cursor0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1",
    "libxcb-randr0", "libxcb-render-util0", "libxcb-shape0", "libxcb-xinerama0", "libxcb-xkb1",
    "libasound2 | libasound2t64",
]


@dataclass
class Entry:
    """One thing the package installs (path without a leading "./")."""
    path: str
    kind: str                       # 'dir', 'file' or 'link'
    mode: int
    source: Optional[Path] = None   # a file on disk, or ...
    data: Optional[bytes] = None    # ... bytes held in memory
    link: Optional[str] = None      # target of a link

    def size(self) -> int:
        if self.kind != "file":
            return 0
        return self.source.stat().st_size if self.source is not None else len(self.data)

    def open(self) -> BinaryIO:
        return open(self.source, "rb") if self.source is not None else io.BytesIO(self.data)

    def md5(self) -> str:
        digest = hashlib.md5()
        with self.open() as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()


def deb_version(version: str) -> str:
    """1.7.2 stays 1.7.2; a pre-release such as 1.7.2-beta.1 becomes 1.7.2~beta.1 (it sorts before 1.7.2)."""
    if not re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", version):
        raise ValueError(f"not a version number: {version!r}")
    return version.replace("-", "~", 1)


def app_version() -> str:
    text = (ROOT / "config" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "(.+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("config/version.py has no __version__")
    return match.group(1)


def collect_entries(dist: Path, desktop_file: Path, icon: Path, license_file: Path) -> List[Entry]:
    """Everything the package installs. Parent folders are added as directories; the list is sorted by path."""
    entries: Dict[str, Entry] = {}

    def add(entry: Entry) -> None:
        parts = entry.path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            folder = "/".join(parts[:i])
            entries.setdefault(folder, Entry(folder, "dir", 0o755))
        entries[entry.path] = entry

    # The program: the whole PyInstaller folder, keeping links and the executable bits
    for current, dirnames, filenames in os.walk(dist):
        dirnames.sort()
        relative = Path(current).relative_to(dist).as_posix()
        base = INSTALL_DIR if relative == "." else f"{INSTALL_DIR}/{relative}"
        add(Entry(base, "dir", 0o755))
        for name in sorted(dirnames + filenames):
            source = Path(current) / name
            if source.is_symlink():
                add(Entry(f"{base}/{name}", "link", 0o777, link=os.readlink(source)))
            elif source.is_file():
                # the program itself is always executable (a build on a system without exec bits must not break it)
                executable = bool(source.stat().st_mode & stat.S_IXUSR) or f"{base}/{name}" == f"{INSTALL_DIR}/{PACKAGE}"
                add(Entry(f"{base}/{name}", "file", 0o755 if executable else 0o644, source=source))

    add(Entry(f"usr/bin/{PACKAGE}", "link", 0o777, link=f"../../{INSTALL_DIR}/{PACKAGE}"))
    add(Entry(f"usr/share/applications/{PACKAGE}.desktop", "file", 0o644, source=desktop_file))
    add(Entry(f"usr/share/icons/hicolor/512x512/apps/{PACKAGE}.png", "file", 0o644, source=icon))
    add(Entry(f"usr/share/doc/{PACKAGE}/copyright", "file", 0o644, source=license_file))
    return [entries[path] for path in sorted(entries)]


def make_tar(entries: List[Entry], mtime: int, compression: str) -> bytes:
    """A tar archive of the entries, all owned by root, compressed with 'gz' or 'xz'."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=f"w:{compression}", format=tarfile.GNU_FORMAT) as tar:
        for entry in [Entry("", "dir", 0o755)] + entries:
            info = tarfile.TarInfo("./" + entry.path + ("/" if entry.kind == "dir" and entry.path else ""))
            info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode = mtime, 0, 0, "root", "root", entry.mode
            if entry.kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif entry.kind == "link":
                info.type, info.linkname = tarfile.SYMTYPE, entry.link
                tar.addfile(info)
            else:
                info.size = entry.size()
                with entry.open() as handle:
                    tar.addfile(info, handle)
    return buffer.getvalue()


def control_file(version: str, installed_kib: int, arch: str) -> str:
    description = [f"Description: {SHORT_DESCRIPTION}"] + [f" {line}" for line in LONG_DESCRIPTION]
    return "\n".join([
        f"Package: {PACKAGE}",
        f"Version: {version}",
        "Section: games",
        "Priority: optional",
        f"Architecture: {arch}",
        f"Maintainer: {MAINTAINER}",
        f"Installed-Size: {installed_kib}",
        f"Depends: {', '.join(DEPENDS)}",
        f"Homepage: {HOMEPAGE}",
        *description,
    ]) + "\n"


def ar_member(name: str, data: bytes, mtime: int) -> bytes:
    """One member of an ar archive: a 60-byte header, the data, and a padding byte when the size is odd."""
    header = f"{name:<16}{mtime:<12d}{0:<6d}{0:<6d}{'100644':<8}{len(data):<10d}`\n".encode("ascii")
    assert len(header) == 60
    return header + data + (b"\n" if len(data) % 2 else b"")


def build_deb(dist: Path, output_dir: Path, version: str, arch: str = "amd64",
              desktop_file: Optional[Path] = None, icon: Optional[Path] = None,
              license_file: Optional[Path] = None) -> Path:
    """Write <output_dir>/rpg-database-manager_<version>_<arch>.deb and return its path."""
    dist = Path(dist)
    if not (dist / PACKAGE).is_file():
        raise FileNotFoundError(f"{dist / PACKAGE} not found: run pyinstaller first")
    deb_ver = deb_version(version)
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))

    entries = collect_entries(
        dist,
        desktop_file or ROOT / "packaging" / "linux" / f"{PACKAGE}.desktop",
        icon or ROOT / "data" / "icons" / "app_icon.png",
        license_file or ROOT / "LICENSE")
    installed_kib = max(1, sum(entry.size() for entry in entries) // 1024)
    md5sums = "".join(f"{entry.md5()}  {entry.path}\n" for entry in entries if entry.kind == "file")

    control_entries = [Entry("control", "file", 0o644, data=control_file(deb_ver, installed_kib, arch).encode("utf-8")),
                       Entry("md5sums", "file", 0o644, data=md5sums.encode("utf-8"))]
    archive = (b"!<arch>\n"
               + ar_member("debian-binary", b"2.0\n", mtime)
               + ar_member("control.tar.gz", make_tar(control_entries, mtime, "gz"), mtime)
               + ar_member("data.tar.xz", make_tar(entries, mtime, "xz"), mtime))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{PACKAGE}_{deb_ver}_{arch}.deb"
    target.write_bytes(archive)
    return target


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dist", default=str(ROOT / "dist" / PACKAGE), help="the PyInstaller folder")
    parser.add_argument("--output", default=".", help="folder for the .deb")
    parser.add_argument("--version", default=None, help="default: __version__ of config/version.py")
    parser.add_argument("--arch", default="amd64")
    args = parser.parse_args(argv)
    target = build_deb(Path(args.dist), Path(args.output), args.version or app_version(), args.arch)
    print(f"{target} ({target.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
