# D1 – Source verification: ContactCars

| Field | Value |
|---|---|
| URL pattern | `https://www.contactcars.com/en/used-cars/<make>-<model>/<source_listing_id>` |
| Content available | Make, model, year, mileage, price, transmission, fuel, body |
| Fields **not** collected | Seller identity/contact |
| Volume in supplied archive | 6,384 listings |
| Request budget (live plan) | ≤1 req/s, concurrency ≤2, off-peak, robots.txt + Retry-After honoured |
| Verdict | **allowed with limits** (pending live terms check in Week 1) |
| Fallback | Dubizzle archive |
| Evidence | URL patterns + field availability from the supplied CSV. |

Dealer/individual flag mentioned in the handbook is not present in this archive; it is
recorded as a missing field rather than guessed. The `seller_type` column remains NULL
for M2 until a source actually exposes it.
