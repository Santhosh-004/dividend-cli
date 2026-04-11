"""Pydantic response models for the Dividend CLI API."""

from typing import Optional, List
from pydantic import BaseModel


class TickerSummary(BaseModel):
    id: int
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    current_price: Optional[float] = None
    face_value: Optional[float] = None
    last_updated: Optional[str] = None


class DBSummary(BaseModel):
    total_tickers: int
    tickers_with_dividends: int
    tickers_with_fundamentals: int
    last_updated: Optional[str] = None
    db_path: str


class FilterResult(BaseModel):
    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    shares: float
    yield_pct: float
    payout_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    div_mean: Optional[float] = None
    div_std: Optional[float] = None
    div_cv: Optional[float] = None
    dividend_quality_score: Optional[float] = None
    dividend_quality_rating: Optional[str] = None
    years_up: int
    years_stalled: int
    years_reduced: int
    years_stopped: int
    cagr_overall: Optional[float] = None
    cagr_3yr: Optional[float] = None
    cagr_5yr: Optional[float] = None
    cagr_10yr: Optional[float] = None
    cagr_15yr: Optional[float] = None
    cagr_20yr: Optional[float] = None
    cagr_25yr: Optional[float] = None
    cagr_30yr: Optional[float] = None


class SplitRecord(BaseModel):
    ex_date: str
    numerator: float
    denominator: float
    ratio: str


class DividendRecord(BaseModel):
    ex_date: str
    raw_amount: float
    forward_amount: float
    shares_at_time: float
    year: int


class YearlyDividend(BaseModel):
    year: int
    raw_total: float
    shares: float
    consolidated_total: float
    dividend_count: int


class CAGRStats(BaseModel):
    period: str
    cagr: Optional[float] = None


class YieldCAGR(BaseModel):
    period: str
    yield_cagr: Optional[float] = None


class DividendQualityInfo(BaseModel):
    score: float
    rating: str  # Elite | Strong | Developing | Fragile
    consistency_score: float
    growth_score: float
    trend_score: float
    history_score: float
    years_analyzed: int


class FundamentalsLatest(BaseModel):
    payout_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    pe_ratio: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    book_value: Optional[float] = None
    face_value: Optional[float] = None
    market_cap_cr: Optional[float] = None
    eps: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    debt_to_equity: Optional[float] = None
    last_updated: Optional[str] = None


class FundamentalsYearly(BaseModel):
    fiscal_year: str
    payout_ratio: Optional[float] = None
    eps: Optional[float] = None
    net_profit: Optional[float] = None
    revenue: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    div_yield: Optional[float] = None
    book_value: Optional[float] = None
    debt_to_equity: Optional[float] = None


class StatsResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    yield_pct: Optional[float] = None  # last complete year dividends / close_price (same as dashboard)
    splits: List[SplitRecord]
    yearly_dividends: List[YearlyDividend]
    recent_payments: List[DividendRecord]
    cagr_stats: List[CAGRStats]
    yield_cagr_stats: List[YieldCAGR]
    dividend_quality: Optional[DividendQualityInfo] = None
    years_up: int
    years_stalled: int
    years_reduced: int
    years_stopped: int
    fundamentals_latest: Optional[FundamentalsLatest] = None
    fundamentals_yearly: List[FundamentalsYearly] = []


class ScreenerResponse(BaseModel):
    symbol: str
    latest: Optional[FundamentalsLatest] = None
    yearly: List[FundamentalsYearly] = []


class UpdateRequest(BaseModel):
    symbol: Optional[str] = None
    force: bool = False
    max_age: int = 90
    limit: Optional[int] = None


class TopStock(BaseModel):
    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    yield_pct: Optional[float] = None
    cagr_overall: Optional[float] = None
    years_up: Optional[int] = None
    dividend_quality_score: Optional[float] = None
    dividend_quality_rating: Optional[str] = None
