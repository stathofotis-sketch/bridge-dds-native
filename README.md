# Bridge DDS Native Service

Minimal Render-compatible API for bridge double-dummy table calculation.

## Endpoints

- `GET /` — health/status
- `POST /dd` — JSON body: `{"dealstr":"N:..."}`

The service validates a full 52-card PBN-style deal, calls Bo Haglund DDS through
`endplay.calc_dd_table`, and returns an explicit 20-row declarer × denomination table.

The output is intentionally marked `COMPUTED / REQUIRES CALIBRATION` until it is
cross-checked against trusted PBN `OptimumResultTable` evidence.
