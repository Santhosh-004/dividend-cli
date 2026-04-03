# Dividend CLI: Condition Filtering Guide

The `--condition` flag allows you to filter stocks using arbitrary Python-style expressions. This is powerful for complex financial analysis that standard flags cannot handle.

## 🔍 Basic Syntax
The condition is evaluated for each stock. If the expression returns `True`, the stock is included in the results.

**Example:**
```bash
dividend-cli filter --condition "yld > 5 and div_5yr > 10"
```

## 📊 Available Variables
The following variables are available in the evaluation context:

| Variable | Alias | Description |
| :--- | :--- | :--- |
| `years_up` | `up` | Total years the dividend increased. |
| `years_stalled` | `stalled` | Total years the dividend remained flat. |
| `years_reduced` | `reduced` | Total years the dividend decreased (but > 0). |
| `years_stopped` | `stopped` | Total years the dividend was zero. |
| `last_yield` | `yld` | The dividend yield of the last completed year (%). |
| `div_growth_overall`| `div_growth` | Overall Dividend CAGR from the first record to now. |
| `c3` | - | 3-Year Dividend CAGR (%). |
| `c5` | - | 5-Year Dividend CAGR (%). |
| `c10` | - | 10-Year Dividend CAGR (%). |
| `c15` | - | 15-Year Dividend CAGR (%). |
| `c20` | - | 20-Year Dividend CAGR (%). |
| `c25` | - | 25-Year Dividend CAGR (%). |
| `c30` | - | 30-Year Dividend CAGR (%). |
| `price` | - | Current market price (raw). |
| `shares` | - | Total shares resulting from 1 original share (split-adjusted). |

> **Note:** CAGR values (c3, c5, etc.) are `0` if the stock does not have enough history for that period.

## 🚀 Advanced Examples

### 1. The "Stability" Filter
Ensure the years of growth significantly outweigh the years of stagnation or reduction.
```bash
# Growth years must be at least double the sum of stalled and reduced years
--condition "years_up >= 2 * (years_stalled + years_reduced)"
```

### 2. The "Acceleration" Filter
Find stocks where recent growth (3yr) is faster than long-term growth (10yr).
```bash
--condition "c3 > c10 and c3 > 15"
```

### 3. The "Value" Filter
Find high-yield stocks where the price is relatively low (e.g., under ₹500).
```bash
--condition "yld > 4 and price < 500"
```

### 4. The "Long-Term Compounder" Filter
Find stocks that have split significantly (meaning they've grown a lot) and still pay a good yield.
```bash
--condition "shares >= 5 and yld > 2"
```

## 🛠️ Internal Processing
The CLI automatically converts hyphens to underscores for convenience. You can use `years-up` instead of `years_up` in your string.

**Supported Hyphen Conversions:**
- `years-up` -> `years_up`
- `years-stalled` -> `years_stalled`
- `years-reduced` -> `years_reduced`
- `years-stopped` -> `years_stopped`
- `cagr-overall` -> `cagr_overall`
