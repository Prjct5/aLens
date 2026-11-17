# Add a scraping source

1. Verify terms, robots.txt and rate limits; record the decision (M1).
2. Add the source name to `SOURCES` in `src/autolens/common/schemas/_base.py`.
3. `make schemas`; follow the contract-change process.
4. Add a scraper module and fixtures; register the stage in `pipelines/entrypoints.py`.
