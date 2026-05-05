"""Shared filesystem paths for build / fetch scripts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SRC_DIR = REPO_ROOT / "src"
ASSETS_DIR = REPO_ROOT / "assets"

SNAPSHOTS_PATH = DATA_DIR / "snapshots.json"
TANKERS_PATH = DATA_DIR / "tankers.json"
CONSTANTS_PATH = SRC_DIR / "constants.json"
SITE_CONFIG_PATH = SRC_DIR / "site.json"
