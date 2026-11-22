# D1 – Source verification: Hatla2ee

| Field | Value |
|---|---|
| URL pattern | `https://eg.hatla2ee.com/en/car/<make>/<model>/<source_listing_id>` |
| Content available | Make, model, year, mileage, price, transmission, fuel, body, description (supplementary archive) |
| Fields **not** collected | Seller name, phone, contact details (privacy rule 16.9) |
| Volume in supplied archive | 10,633 listings |
| Request budget (live plan) | ≤1 req/s, concurrency ≤2, 01:00–06:00 Cairo, identifiable UA, honour robots.txt |
| Verdict | **allowed with limits** – public listing pages only; if robots.txt or terms forbid automated access in Week 1, replace with an alternative source |
| Fallback | ContactCars archive (same schema family) |
| Evidence | URL structure and field availability verified from `data/Egypt_Used_Cars_clean.csv`. Live `robots.txt`/terms verification is a Week-1 day-1 task for the team (offline environment here). |

The archive adapter is `src/autolens/scrapers/archive.py::ArchiveSource('hatla2ee', ...)`.
`parse()` is a pure function over saved bytes; re-parsing raw reproduces staging exactly (R3).
