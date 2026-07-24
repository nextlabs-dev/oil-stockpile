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

# 有事終息予想(/forecast/)の設定。JS 側ミラーは js/core/forecast.js の
# FORECAST_CONFIG で、build_site.py が drift を検証する。
# api_origin は Workers のデプロイ後に実値を入れる（空 = 投票 UI は準備中表示）。
_forecast = _constants["forecast"]
FORECAST_API_ORIGIN: str = str(_forecast["api_origin"])
FORECAST_TURNSTILE_SITE_KEY: str = str(_forecast["turnstile_site_key"])
FORECAST_QUESTION_ID: str = str(_forecast["question_id"])
FORECAST_MIN_VOTES_FOR_PERCENT: int = int(_forecast["min_votes_for_percent"])
