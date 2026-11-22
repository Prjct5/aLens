# D1 – Source verification: Dubizzle Egypt

| Field | Value |
|---|---|
| URL pattern | `https://www.dubizzle.com.eg/en/ad/<slug>-for-sale-<city>-ID<id>.html` |
| Content available | Make, model, year, mileage, price, transmission, fuel, body; city embedded in URL |
| Governorate extraction | `governorate_from_url()` maps city slug -> code (ALX, CAI, GIZ, …); NULL otherwise |
| Volume in supplied archive | 18,377 listings |
| Request budget (live plan) | ≤1 req/s, concurrency ≤2, off-peak, robots.txt honoured |
| Verdict | **allowed with limits** (pending live terms check in Week 1) |
| Fallback | Hatla2ee archive |
| Evidence | URL patterns and city slugs verified from the supplied CSV. |

Only a minority of URLs expose a city slug, so `same_governorate` is frequently missing;
FS/EM treats missing as a third level (never as disagreement) – see 8.7.2.
