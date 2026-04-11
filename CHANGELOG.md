# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-11

### Added
- **Web UI (`serve`)**: Added a FastAPI + SvelteKit web interface for browsing top dividend stocks, screening ideas, viewing stock detail pages, and running updates from the browser.
- **Dividend Quality Score**: Introduced a new 0-100 dividend quality metric with ratings (`Elite`, `Strong`, `Developing`, `Fragile`) designed to measure stable and growing annual dividends over full history.
- **Quality filtering**: Added `--min-div-quality` to the CLI and `min_div_quality` support in the API/frontend screener.
- **Quality variables for `--condition`**: Added `dq_score` / `dividend_quality_score` and `dq_rating` / `dividend_quality_rating` for advanced screening logic.
- **Quality leaderboard**: Added a homepage/top-stocks ranking for highest dividend quality.
- **Stock detail quality panel**: Added breakdown of quality, consistency, growth, and trend-fit in the stock detail page.

### Changed
- **Stability metric replaced**: Replaced CV-based `VeryStable/Moderate/Volatile` classification with Dividend Quality as the main user-facing metric across CLI, API, and frontend.
- **Homepage redesigned**: Reworked the homepage into a cleaner editorial dashboard with `Top Yields` and `Best Quality` sections.
- **Screener presets improved**: Preset buttons now apply more truthful filter combinations, expand the filter panel so users can see applied values, and only stay highlighted while the current filters still exactly match that preset.
- **Screener limit input fixed**: Limit control now increments by 1, normalizes correctly, and accepts nearby values predictably.
- **Stock detail redesign**: Reworked the stock detail page around dividend quality, track record, cleaner fundamentals, and clearer charts.
- **Update page redesigned**: Update flow now behaves like an operational utility/settings page with live progress output.
- **Favicon and design system refreshed**: Frontend received a full visual refresh with the new editorial terminal aesthetic.

### Fixed
- **Misclassified dividend growers**: Stocks like `INDIGRID.NS` and `HDFCBANK.NS` no longer get punished by raw dispersion metrics despite visibly strong dividend growth histories.
- **Yield consistency**: Fixed contradictory yield displays (for example `CAPLIPOINT.NS`) by aligning fundamentals yield shown in stats/UI with the app's computed current yield.
- **Preset UX clarity**: Users can now see preset-applied values in the filter form immediately after clicking a preset.
- **Homepage layout issues**: Removed the broken/clipped third leaderboard layout and stabilized the overview page.

### Removed
- **Yield CAGR from UI**: Removed Yield CAGR from the stock detail page because it was confusing and not a strong user-facing metric.
- **Volatility as the primary story**: CV/std-dev remain only as legacy diagnostics for advanced CLI filtering, not as the main dividend quality signal.

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
