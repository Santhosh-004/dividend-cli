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
