# Oil daily PDF fixture

`oil_daily.pdf` is a real snapshot of the official Ministry of Economy, Trade and Industry / Agency for Natural Resources and Energy daily oil-stockpile PDF. It is used only for offline parser and end-to-end regression tests; it is not the production data source.

| Field | Value |
|---|---|
| Source URL | https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/pdf-oil-res/oil_daily.pdf |
| Retrieved | 2026-08-19 |
| SHA-256 | `997a639cfc192eb4c3dda90aa072e003002cac9140d77000f98e1529d8d17514` |
| Parsed range | 2026-03-14 to 2026-08-16 |
| Parsed snapshots | 155 |

When replacing the fixture, update this document and confirm that `python3 -m unittest scripts.test_fetch_pdf` still completes the offline dry-run test.
