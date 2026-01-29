"""Top level package for dividend_calculator.

The package provides a small CLI tool that downloads Indian equity dividend
history from Yahoo Finance, stores it in a local SQLite database and offers a
set of filtering utilities.

Only a subset of the full feature‑set described in the design document is
implemented – enough to satisfy the core requirements of fetching dividend
data, persisting it and allowing the user to filter by yield, CAGR and year‑
over‑year classifications.
"""

__all__ = ["db", "fetch", "cli", "utils"]
