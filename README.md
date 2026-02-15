# 📈 Indian Stock Dividend Calculator & Filter

A powerful CLI tool designed for Indian equity investors to track, analyze, and filter stocks based on their complete dividend history. Unlike standard screeners, this tool handles **stock splits** correctly, showing you both the raw historical dividends and the true growth of a single original share.

## 🚀 Key Features

- **Automated Data Pipeline**: Fetches the complete NSE ticker list and sources deep dividend/price history directly from Yahoo Finance APIs.
- **Dual Dividend View**:
  - **Raw**: What was actually paid per share at that time (matches company filings)
  - **Forward-Adjusted**: Total payout from 1 original share (shows true growth)
- **Correct Split Handling**: Properly handles stock splits by converting Yahoo's backward-adjusted data to raw, then forward-adjusting correctly.
- **Smart CAGR**: 
  - Excludes current year (incomplete data)
  - Skips zero-dividend years for accurate growth calculation
- **Multi-Period Dividend CAGR**: View Compounded Annual Dividend Growth Rates for 3, 5, 10, 15, 20, and 30-year durations.
- **Consistency Tracking**: Track years where dividends were **Increased (Up)**, **Stalled (Flat)**, **Reduced**, or **Stopped**.
- **Power-User Filtering**: Use standard flags or execute arbitrary Python-style conditions for complex research.
- **Offline Storage**: All data is persisted in a local SQLite database for blazing-fast filtering and offline access.

## 📦 Installation

### Option 1: Pre-built Executables (No Python Required)

1. **Download** the zip file for your OS from [Releases](https://github.com/Santhosh-004/dividend-cli/releases)
2. **Extract** the zip file
3. **Run** the executable:
   - Windows: `dividend-cli.exe update`
   - Linux/Mac: `./dividend-cli update`

   This will download the dividend data to `dividend.db` in the same folder.

4. **Now you can view stats**:
   - Windows: `dividend-cli.exe stats HDFCBANK.NS`
   - Linux/Mac: `./dividend-cli stats HDFCBANK.NS`

### Option 2: From Source (Python Required)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Santhosh-004/dividend-cli.git
   cd dividend-cli
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the CLI tool**:
   ```bash
   pip install -e .
   ```

## 🛠️ Usage

### 1. Download/Update Data
Download the latest NSE ticker list and fetch history for all stocks. The tool intelligently refreshes data only if it's older than 90 days.
```bash
# Update all stocks (this may take time due to rate limiting)
dividend-cli update

# Update a small batch for testing
dividend-cli update --limit 50
```

### 2. Filter for Quality Stocks
Find "Dividend Aristocrats" or high-growth opportunities using robust filters.

```bash
# Basic Filter: Min 1.5% yield and 10% 5-year Dividend CAGR
dividend-cli filter --min-yield 1.5 --cagr-5yr-min 10

# Consistency Filter: Min 5 years of Dividend growth, Max 1 year of Dividend reduction
dividend-cli filter --years-up 5 --years-reduced 1
```

### 3. Power-User: Arbitrary Conditions
Use the `--condition` flag to run complex mathematical logic.
```bash
# Find stocks where Dividend growth years outpace stalled/stopped years by 2x
dividend-cli filter --condition "(years-stopped + years-stalled) * 2 <= years-up"

# Find stocks where 3Yr Dividend growth is strictly better than 10Yr growth
dividend-cli filter --condition "c3 > c10"
```

### 4. Detailed Ticker Stats
See the full dividend journey of a specific ticker with both raw and forward-adjusted data.
```bash
dividend-cli stats HDFCBANK.NS
```

## 📊 Output Explanation

### Stats Command
The `stats` command shows:

1. **Yearly Totals (Raw)**: What was actually paid per share at that time - matches company filings exactly.
2. **Yearly Totals (Forward)**: Total dividend from 1 original share - shows true wealth creation.
3. **CAGR**: Compound annual growth rate, calculated excluding:
   - Current year (incomplete data)
   - Years with zero dividends
4. **Recent Payments**: Shows raw amount, forward-adjusted amount, and number of shares at that time.

### Filter Variables Reference
When using the `--condition` flag, you can use the following variables:

| Variable | Description |
| :--- | :--- |
| `up` / `years_up` | Total years dividend increased |
| `stalled` / `years_stalled` | Total years dividend remained flat |
| `reduced` / `years_reduced` | Total years dividend decreased |
| `stopped` / `years_stopped` | Total years dividend was zero |
| `yield` / `avg_yield` | Average historical yield (%) |
| `cagr` / `cagr_overall` | Dividend CAGR since first record |
| `c3`, `c5`, `c10` ... | Dividend CAGR for last 3, 5, 10, 15, 20, 30 years |
| `price` | Current market price |
| `shares` | Current share count from 1 original share |

## 🧠 How it Works

### Data Adjustment Process

1. **Yahoo Finance Data**: Yahoo provides backward-adjusted dividends (divided by splits).
2. **Convert to Raw**: Multiply by splits that happened AFTER each dividend date to get what was actually paid.
3. **Forward Adjust**: Multiply by cumulative splits AT THAT TIME to show total from 1 original share.

**Example with HDFC Bank:**
- 1997: Raw ₹0.80 (1 share), Forward ₹0.80 (1 share)
- 2012: Raw ₹4.30 (per share), Forward ₹21.50 (5 shares)
- 2022: Raw ₹15.50 (per share), Forward ₹155.00 (10 shares)

### Why This Matters

- **Raw dividends** match company filings exactly - useful for verification
- **Forward-adjusted** shows true dividend growth per original share - useful for long-term analysis
- **CAGR excludes incomplete years** - gives accurate growth picture
- **Skips zero-dividend years** - avoids false dips in growth (e.g., RBI dividend ban in 2020)

## 📋 Requirements
- Python 3.9+
- `pandas`, `click`, `tabulate`, `tqdm`, `requests`

---
*Disclaimer: This tool is for educational and research purposes only. Always verify data with official exchange filings before making investment decisions.*
