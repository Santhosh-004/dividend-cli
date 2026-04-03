# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-04-03

### Added
- **REITs and INVITs Support**: Automatically discovers and fetches dividend data for REITs (Embassy, Mindspace, Brookfield, Nexus) and INVITs (IndiaGrid, PowerGrid, IRB, Cube, Shrem, NDR, Anantam) from Yahoo Finance
- **Dividend Stability Metrics**: Added mean, standard deviation, and coefficient of variation (CV%) to both `stats` and `filter` commands for measuring dividend volatility - CV <20% = very stable, 20-50% = moderate, >50% = volatile
- **Yield CAGR**: New calculation showing compound growth of dividend yield over 10, 15, 20, 25, 30 years
- **25-Year CAGR**: Added 25-year dividend growth period to stats and filter
- **New filter flags**: `--div-growth-min`, `--div-3yr-min`, `--div-5yr-min`, `--div-10yr-min` (renamed from `--cagr-*`)
- **New condition variables**: `div_mean`, `div_std`, `div_cv`, `div_25yr`, `div_30yr`, `div_growth`, `div_3yr` through `div_30yr`, `yld`
- **Update single ticker**: `--symbol` flag for `update` command to update a specific stock
- **CONDITIONS.md**: Documentation for condition filtering
- **Cross-platform builds**: GitHub Actions workflow for Windows, Linux, Mac executables
- **run.py**: Proper entry point for PyInstaller

### Fixed
- **`yield` keyword conflict**: Replaced `yield` with `yld` in `--condition` expressions (Python reserved keyword)
- **Yield calculation**: Now uses last year's total dividend / price on last dividend date (was using historical average)
- **CAGR calculation**: Properly handles zero-dividend years and excludes current incomplete year
- **Empty yearly totals**: Handles edge case when stock has no dividend data
- **Build workflow**: Multiple fixes for PyInstaller, Windows zip creation, permissions, timeouts
- **Silent error handling**: Ticker fetch failures no longer print error messages to console

### Changed
- **Filter output**: Renamed columns for clarity (`CAGR Overall` → `Div Growth Overall`, added `Div Mean`, `Div StdDev`, `Div CV`)
- **Filter flags**: `--cagr-min` → `--div-growth-min`, `--cagr-3yr-min` → `--div-3yr-min`, etc.
- **Ticker fetching**: Now includes EQ, BE, BZ series (previously only EQ)
- **Trigger on push**: Build workflow now runs on push to main branch, not just version tags
- **Build artifacts**: Removed zip archives - releases now contain raw executables directly
- **Stats output**: Simplified display, removed redundant raw dividend table

### Removed
- **`avg_yield`** condition variable (was misleadingly same as last year's yield)
- **`yield_5yr`**, **`five_yr_yield`** condition variables (replaced by yield CAGR)
- **`--cagr-min`**, **`--cagr-3yr-min`**, etc. flags (renamed to `--div-growth-min`, `--div-3yr-min`)

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
