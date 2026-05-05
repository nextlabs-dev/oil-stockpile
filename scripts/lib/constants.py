"""Single Source of Truth loader for cross-language constants.

The canonical values live in src/constants.json. JS-side mirrors
(js/core/data.js) are kept in sync by build_site.py's verification step.
"""

from __future__ import annotations

from .io import read_json
from .paths import CONSTANTS_PATH

_constants = read_json(CONSTANTS_PATH)

PEAK_DAYS: int = int(_constants["peak_reference"]["days"])
PEAK_SOURCE: str = str(_constants["peak_reference"]["source"])
