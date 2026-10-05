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

# 公式 SNS（X）まわりの設定。JS 側ミラーは js/core/data.js の SOCIAL_CONFIG で、
# build_site.py が drift を検証する。UTM ルールは docs/utm.md。
# twitter_site: <meta name="twitter:site"> に入るハンドル。公式アカウント確定後に差し替える。
# official_handle: 共有文のメンション用（"@xxx" 形式）。未確定の間は空 = メンションなし。
_social = _constants["social"]
SOCIAL_TWITTER_SITE: str = str(_social["twitter_site"])
SOCIAL_OFFICIAL_HANDLE: str = str(_social["official_handle"])
SOCIAL_UTM_SOURCE: str = str(_social["utm_source"])
SOCIAL_UTM_MEDIUM: str = str(_social["utm_medium"])
SOCIAL_UTM_CAMPAIGN: str = str(_social["utm_campaign"])

# HubSpot トラッキングコード。ポータルID・リージョンは公開される値（トークンではない）。
# スクリプト URL は base.html に、配信元の許可は CSP に、同じ値から展開する（SSOT）。
_hubspot = _constants["hubspot"]
HUBSPOT_PORTAL_ID: str = str(_hubspot["portal_id"])
HUBSPOT_REGION: str = str(_hubspot["region"])
HUBSPOT_SCRIPT_SRC: str = f"https://js-{HUBSPOT_REGION}.hs-scripts.com/{HUBSPOT_PORTAL_ID}.js"
