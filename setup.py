#!/usr/bin/env python3
"""
RPG Database Manager - Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path
import sys

# Add the project root to path to import version
sys.path.insert(0, str(Path(__file__).parent))
from config.version import __version__

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file, "r", encoding="utf-8") as f:
        long_description = f.read()

# requirements.txt is the single source of truth for runtime dependencies
requirements_file = Path(__file__).parent / "requirements.txt"
install_requires = []
dev_requires = []
with open(requirements_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.split("#", 1)[0].strip()      # drop inline comments
        if not line:
            continue
        (dev_requires if line.lower().startswith("pytest") else install_requires).append(line)

extras_require = {"dev": dev_requires}

setup(
    name="rpg-database-manager",
    version=__version__,
    author="RPG Database Manager Team",
    author_email="",
    description="A comprehensive desktop application for managing tabletop RPG campaigns",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/irattarto/DM-tool",
    project_urls={
        "Source": "https://github.com/irattarto/DM-tool",
        "Tracker": "https://github.com/irattarto/DM-tool/issues",
    },
    packages=find_packages(exclude=["tests", "tests.*", "build", "dist"]),
    py_modules=["main"],  # the console scripts below import main:main
    include_package_data=True,
    package_data={
        "": [
            "data/**/*",
            "config/**/*.yaml",
            "config/**/*.yml",
            "config/**/*.json",
        ],
    },
    python_requires=">=3.10",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "rpg-db-manager=main:main",
        ],
        "gui_scripts": [
            "rpg-db-manager-gui=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment :: Role-Playing",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Environment :: X11 Applications :: Qt",
        "Natural Language :: English",
    ],
    keywords=[
        "rpg",
        "tabletop",
        "dungeon-master",
        "game-master",
        "campaign-management",
        "database",
        "pyqt6",
        "desktop-application",
    ],
    zip_safe=False,
)
