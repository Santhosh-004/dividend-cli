"""Utility functions for dividend calculations.

Provides:
* dividend_yield – compute yield given amount and price.
* cagr – compound annual growth rate for dividend totals.
* classify_years – given a list of yearly totals, return counts of
  (up, stalled, reduced, stopped).
"""

from typing import Sequence, Tuple, List


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


def adjust_dividends(dividends: List[dict], splits: List[dict]) -> List[dict]:
    """Adjust dividend amounts forward (Growth of 1 Original Share).
    
    This model assumes you bought 1 share at the beginning. As splits occur, 
    your share count increases, and so does your total dividend received.
    
    Formula: Adjusted Amount = Raw Amount * (Cumulative Split Ratio at that time)
    """
    # Sort everything chronologically
    sorted_splits = sorted(splits, key=lambda x: x['ex_date'])
    sorted_divs = sorted(dividends, key=lambda x: x['ex_date'])
    
    adjusted = []
    current_multiplier = 1.0
    split_idx = 0
    
    for div in sorted_divs:
        # Apply all splits that happened BEFORE or ON this dividend ex-date
        # Note: Usually splits happen on the ex-date morning.
        while split_idx < len(sorted_splits) and sorted_splits[split_idx]['ex_date'] <= div['ex_date']:
            split = sorted_splits[split_idx]
            current_multiplier *= (split['numerator'] / split['denominator'])
            split_idx += 1
            
        new_div = dict(div)
        new_div['amount'] = div['amount'] * current_multiplier
        # We also store the multiplier for later reference (e.g. for price/yield)
        new_div['multiplier'] = current_multiplier
        
        # Note: Yield is ALWAYS (Raw Amount / Raw Price). 
        # If we adjust both by the same multiplier, the ratio stays the same.
        if div.get('close_price'):
            new_div['close_price'] = div['close_price'] * current_multiplier
            
        adjusted.append(new_div)
        
    return adjusted
