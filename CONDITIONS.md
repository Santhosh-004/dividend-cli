# Dividend CLI Condition Filtering Guide

`dividend-cli filter --condition` lets you write custom Python-style expressions for advanced screening.

Example:

```bash
dividend-cli filter --condition "dq_score >= 80 and yld > 1 and years_stopped == 0"
```

## Available Variables

| Variable | Alias | Description |
| --- | --- | --- |
| `years_up` | `up` | Total years dividend increased |
| `years_stalled` | `stalled` | Total years dividend remained flat |
| `years_reduced` | `reduced` | Total years dividend decreased but stayed above zero |
| `years_stopped` | `stopped` | Total years dividend was zero |
| `last_yield` | `yld` | Last completed year's dividend yield (%) |
| `div_growth_overall` | `div_growth` | Overall dividend CAGR |
| `c3`, `c5`, `c10`, `c15`, `c20`, `c25`, `c30` | - | Period dividend CAGR (%) |
| `div_3yr` ... `div_30yr` | - | Same CAGR values with long names |
| `dq_score` | `dividend_quality_score` | Dividend Quality Score (0-100) |
| `dq_rating` | `dividend_quality_rating` | Dividend Quality rating string |
| `div_mean` | - | Mean yearly dividend |
| `div_std` | - | Standard deviation of yearly dividends |
| `div_cv` | - | Legacy coefficient of variation |
| `price` | - | Current market price |
| `shares` | - | Shares resulting from 1 original share after splits |

## Example Screens

### Dividend quality first

```bash
dividend-cli filter --condition "dq_score >= 85 and years_stopped == 0"
```

### Reliable growers

```bash
dividend-cli filter --condition "years_up >= 2 * (years_stalled + years_reduced) and c5 > 10"
```

### Strong recent acceleration

```bash
dividend-cli filter --condition "c3 > c10 and c3 > 15"
```

### Quality plus yield

```bash
dividend-cli filter --condition "dq_score >= 75 and yld > 1.5"
```

### Cheap-ish income ideas

```bash
dividend-cli filter --condition "yld > 3 and price < 500 and years_stopped <= 1"
```

## Notes

- Missing CAGR values are treated as `0` inside the condition context.
- Hyphenated names such as `years-up` are normalized internally to `years_up`.
- `div_cv` is still available, but it is considered a legacy diagnostic rather than the main dividend quality metric.
