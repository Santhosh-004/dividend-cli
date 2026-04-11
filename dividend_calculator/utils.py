"""Utility functions for dividend calculations.

Provides:
* dividend_yield - compute yield given amount and price.
* cagr - compound annual growth rate for dividend totals.
* classify_years - given a list of yearly totals, return counts of
  (up, stalled, reduced, stopped).
* dividend_quality_score - score how stable and growing a dividend history is.
"""

import math
from typing import Sequence, Tuple, List, Optional, Dict


def dividend_yield(amount: float, price: float) -> float:
    """Return dividend yield as a percentage.

    ``amount`` is the dividend per share for the period, ``price`` is the
    closing price on the ex‑date.  The result is ``amount / price * 100``.
    """
    if price <= 0:
        return 0.0
    return (amount / price) * 100.0


def cagr(first: float, last: float, years: int) -> float:
    """Calculate compound annual growth rate.

    ``first`` and ``last`` are the dividend totals for the first and last year.
    ``years`` is the number of years between them.
    """
    if years <= 0 or first <= 0:
        return 0.0
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0


def classify_years(yearly_totals: Sequence[float]) -> Tuple[int, int, int, int]:
    """Classify year‑over‑year changes.

    Returns a tuple ``(up, stalled, reduced, stopped)`` where:
    * up – current year total > previous year total
    * stalled – equal to previous year total
    * reduced – current year total < previous year total but > 0
    * stopped – current year total == 0
    """
    up = stalled = reduced = stopped = 0
    for prev, cur in zip(yearly_totals, yearly_totals[1:]):
        # Use a small epsilon for float comparison
        if cur < 1e-6:
            stopped += 1
        elif cur > prev + 1e-6:
            up += 1
        elif abs(cur - prev) < 1e-6:
            stalled += 1
        else:
            reduced += 1
    return up, stalled, reduced, stopped


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    """Clamp a number into a closed interval."""
    return max(lower, min(upper, value))


def _growth_score(cagr_value: Optional[float]) -> float:
    """Map dividend CAGR to a bounded 0-100 growth score.

    The mapping intentionally saturates at high growth rates so that the metric
    rewards durable growth without letting outliers dominate the final score.
    """
    if cagr_value is None:
        return 0.0
    if cagr_value <= 0:
        return _clamp(35.0 + (cagr_value * 3.5))
    if cagr_value <= 10:
        return _clamp(35.0 + (cagr_value * 4.0))
    return _clamp(75.0 + ((cagr_value - 10.0) * 2.5))


def _log_trend_quality(values: Sequence[float]) -> float:
    """Return a 0-100 score for how smoothly dividends trend upward.

    Uses a linear fit on log dividends so compounding-like histories score well,
    while flat or erratic histories score lower. This avoids the CV problem where
    good step-up dividend histories look artificially "volatile".
    """
    positive_values = [float(v) for v in values if float(v) > 1e-6]
    if len(positive_values) < 3:
        return 0.0

    x_vals = list(range(len(positive_values)))
    y_vals = [math.log(v) for v in positive_values]
    x_mean = sum(x_vals) / len(x_vals)
    y_mean = sum(y_vals) / len(y_vals)

    ss_xx = sum((x - x_mean) ** 2 for x in x_vals)
    if ss_xx <= 1e-12:
        return 0.0

    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals)) / ss_xx
    intercept = y_mean - (slope * x_mean)

    ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
    if ss_tot <= 1e-12:
        r_squared = 1.0
    else:
        ss_res = sum((y - ((slope * x) + intercept)) ** 2 for x, y in zip(x_vals, y_vals))
        r_squared = 1.0 - (ss_res / ss_tot)

    r_squared = max(0.0, min(1.0, r_squared))
    implied_growth = ((math.exp(slope) - 1.0) * 100.0) if slope > -20 else -100.0
    return _clamp(r_squared * _growth_score(implied_growth))


def dividend_quality_score(
    yearly_totals: Sequence[float],
    overall_cagr: Optional[float] = None,
) -> Optional[Dict[str, float | int | str]]:
    """Score a stock's dividend history for stable and growing payouts.

    The old CV-based approach measured dispersion, which punishes exactly the
    kind of long upward stair-step histories we want to reward. This score is
    designed for dividend quality instead:

    * Consistency: rewards years up, tolerates some flat years,
      penalizes cuts and stoppages heavily.
    * Growth: rewards positive long-term CAGR, but with capped influence.
    * Trend quality: rewards histories that follow a smooth upward trajectory.
    * History depth: gives a small boost to longer proven records.
    """
    values = [float(v) for v in yearly_totals]
    if len(values) < 2:
        return None

    transitions = len(values) - 1
    positive_years = sum(1 for v in values if v > 1e-6)
    up, stalled, reduced, stopped = classify_years(values)

    consistency_score = _clamp(
        ((up + (0.6 * stalled) - (1.0 * reduced) - (1.4 * stopped)) / transitions) * 100.0
    )
    growth_score = _growth_score(overall_cagr)
    trend_score = _log_trend_quality(values)
    history_score = _clamp((positive_years / 10.0) * 100.0)

    total_score = _clamp(
        (0.45 * consistency_score)
        + (0.25 * growth_score)
        + (0.20 * trend_score)
        + (0.10 * history_score)
    )

    if total_score >= 85:
        rating = "Elite"
    elif total_score >= 70:
        rating = "Strong"
    elif total_score >= 55:
        rating = "Developing"
    else:
        rating = "Fragile"

    return {
        "score": round(total_score, 2),
        "rating": rating,
        "consistency_score": round(consistency_score, 2),
        "growth_score": round(growth_score, 2),
        "trend_score": round(trend_score, 2),
        "history_score": round(history_score, 2),
        "years_analyzed": len(values),
    }


def adjust_dividends(dividends: List[dict], splits: List[dict]) -> List[dict]:
    """Adjust dividend amounts: Yahoo backward-adjusted -> RAW -> Forward-adjusted.
    
    Yahoo Finance provides BACKWARD-ADJUSTED dividends (divided by splits).
    This function converts them to:
    1. RAW: What was actually paid per share at that time
    2. Forward-adjusted: Total payout from 1 original share at that time
    
    Step 1 (Yahoo -> RAW): Multiply by splits AFTER the dividend date
    Step 2 (RAW -> Forward): Multiply by cumulative splits AT THAT TIME
    
    The 'amount' field will be forward-adjusted (total from 1 original share at that time).
    """
    sorted_splits = sorted(splits, key=lambda x: x['ex_date'])
    sorted_divs = sorted(dividends, key=lambda x: x['ex_date'])
    
    adjusted = []
    
    for div in sorted_divs:
        # Calculate splits AFTER this dividend date (for RAW conversion)
        # Yahoo backward-adjusts by dividing by these splits, so we multiply to reverse
        splits_after = 1.0
        # Calculate cumulative splits AT THIS TIME (for forward adjustment)
        splits_at_time = 1.0
        
        for split in sorted_splits:
            if split['ex_date'] > div['ex_date']:
                splits_after *= (split['numerator'] / split['denominator'])
            elif split['ex_date'] <= div['ex_date']:
                splits_at_time *= (split['numerator'] / split['denominator'])
        
        new_div = dict(div)
        
        # Step 1: Yahoo backward-adjusted -> RAW
        # Multiply by splits that happen AFTER this dividend date
        raw_amount = div['amount'] * splits_after
        
        # Step 2: RAW -> Forward-adjusted (total from 1 original share at that time)
        # Multiply by cumulative splits AT THAT TIME
        forward_amount = raw_amount * splits_at_time
        
        new_div['amount'] = forward_amount
        new_div['raw_amount'] = raw_amount
        new_div['splits_at_time'] = splits_at_time
        
        if div.get('close_price'):
            # Yahoo prices are also backward-adjusted, so convert to raw the same way
            # Multiply by splits AFTER to get the raw historical price
            raw_price = div['close_price'] * splits_after
            new_div['close_price'] = raw_price
            
        adjusted.append(new_div)
        
    return adjusted
