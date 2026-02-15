# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-15

### Added
- **Dual Dividend View**: Now shows both raw (actual paid per share) and forward-adjusted (total from 1 original share) dividend data.
- **CAGR Improvements**: 
  - Excludes current year from calculations (incomplete data)
  - Skips zero-dividend years for accurate growth calculation
- **Version flag**: Added `--version` flag to CLI.

### Fixed
- **Dividend Adjustment Logic**: Fixed the core calculation that converts Yahoo Finance's backward-adjusted data to raw historical dividends, then correctly forward-adjusts for splits.
  - Previously: Multiplied by ALL splits (double adjustment)
  - Now: Multiplies by splits AFTER the dividend date to get raw, then by cumulative splits AT THAT TIME for forward-adjustment

### Changed
- **Stats Output**: Now displays two yearly tables - one for raw amounts and one for forward-adjusted.
- **Yield Calculation**: Now correctly uses raw dividend / raw price for accurate historical yield.

## [0.1.0] - 2026-02-14

### Added
- Initial release
- NSE ticker list fetching
- Yahoo Finance dividend and price data fetching
- Stock split handling
- Dividend filtering (yield, CAGR, growth years)
- Detailed stats per ticker
- SQLite local storage
