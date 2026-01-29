# 📈 Indian Stock Dividend Calculator & Filter

A powerful CLI tool designed for Indian equity investors to track, analyze, and filter stocks based on their complete dividend history. Unlike standard screeners, this tool handles **stock splits** using a **Forward-Adjusted Model**, showing you the true growth of a single original share over decades.

## 🚀 Key Features

- **Automated Data Pipeline**: Fetches the complete NSE ticker list and sources deep dividend/price history directly from Yahoo Finance APIs.
- **Split-Adjusted Analysis (Forward Model)**: Automatically detects stock splits (2:1, 5:1, 10:1, etc.) and calculates the growth of **1 original share**. 
  - *Example*: See how 1 share of HDFC Bank bought in 1997 has grown in total payout as it multiplied into 20 shares.
- **Multi-Period Dividend CAGR**: View Compounded Annual Dividend Growth Rates for 3, 5, 10, 15, 20, and 30-year durations.
- **Consistency Tracking**: Track years where dividends were **Increased (Up)**, **Stalled (Flat)**, **Reduced**, or **Stopped**.
- **Power-User Filtering**: Use standard flags or execute arbitrary Python-style conditions for complex research.
- **Offline Storage**: All data is persisted in a local SQLite database for blazing-fast filtering and offline access.

## 📦 Installation

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

# Find stocks where 3Yr Dividend growth is strictly better than 10Yr Dividend growth
dividend-cli filter --condition "c3 > c10"
```

### 4. Detailed Ticker Stats
See the full split-adjusted journey of a specific ticker.
```bash
dividend-cli stats HDFCBANK.NS
```

## 📊 Filter Variables Reference
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

- **Reliability**: Uses direct Yahoo Finance Chart API calls to bypass common `yfinance` connectivity and rate-limit issues.
- **Fuzzy Price Matching**: Uses `bisect` algorithms to find the closest market price for ex-dividend dates (handling holidays/weekends).
- **Forward Model**: Unlike backward-adjusted prices (which make historical dividends look like fractions of a paisa), our model multiplies the dividend by the split factor to show the **total payout per original share**.

## 📋 Requirements
- Python 3.9+
- `pandas`, `click`, `tabulate`, `tqdm`, `requests`, `yfinance`

---
*Disclaimer: This tool is for educational and research purposes only. Always verify data with official exchange filings before making investment decisions.*
