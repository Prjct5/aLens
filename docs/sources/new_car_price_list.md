# D1 – Source verification: New-car price list (reference)

| Field | Value |
|---|---|
| Purpose | Seed the canonical make/model dictionary with clean spellings (handbook 8.5, R8) |
| Refresh | Weekly |
| Status in this build | **not supplied** – the dictionary was mined from observed used-car listings instead |
| Consequence | `model_id` values are stable and versioned in `data_reference/models.csv`, but the canonical vocabulary is data-driven rather than official. Re-run the seed from an official price list when one is available; aliases remain valid. |
| Fallback | Alias mining from `make_raw`/`model_raw` frequencies (implemented) |
