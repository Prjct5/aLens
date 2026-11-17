# Test fixtures

Public repository: fixtures must be minimal, synthetic or trimmed, with no seller names,
phone numbers, photos or credentials.

Files named `<schema>.<table>.json` hold a list of rows. They are validated against the
Pydantic contract by `tests/contract` and loaded into the dev database by `make seed`.
