// TypeScript types mirroring the Pydantic API response models

export interface DBSummary {
	total_tickers: number;
	tickers_with_dividends: number;
	tickers_with_fundamentals: number;
	last_updated: string | null;
	db_path: string;
}

export interface TickerSummary {
	id: number;
	symbol: string;
	name: string | null;
	sector: string | null;
	current_price: number | null;
	face_value: number | null;
	last_updated: string | null;
}

export interface FilterResult {
	symbol: string;
	name: string | null;
	price: number | null;
	shares: number;
	yield_pct: number;
	payout_pct: number | null;
	roe_pct: number | null;
	roce_pct: number | null;
	div_mean: number | null;
	div_std: number | null;
	div_cv: number | null;
	dividend_quality_score: number | null;
	dividend_quality_rating: string | null;
	years_up: number;
	years_stalled: number;
	years_reduced: number;
	years_stopped: number;
	cagr_overall: number | null;
	cagr_3yr: number | null;
	cagr_5yr: number | null;
	cagr_10yr: number | null;
	cagr_15yr: number | null;
	cagr_20yr: number | null;
	cagr_25yr: number | null;
	cagr_30yr: number | null;
}

export interface SplitRecord {
	ex_date: string;
	numerator: number;
	denominator: number;
	ratio: string;
}

export interface DividendRecord {
	ex_date: string;
	raw_amount: number;
	forward_amount: number;
	shares_at_time: number;
	year: number;
}

export interface YearlyDividend {
	year: number;
	raw_total: number;
	shares: number;
	consolidated_total: number;
	dividend_count: number;
}

export interface CAGRStats {
	period: string;
	cagr: number | null;
}

export interface YieldCAGR {
	period: string;
	yield_cagr: number | null;
}

export interface DividendQualityInfo {
	score: number;
	rating: 'Elite' | 'Strong' | 'Developing' | 'Fragile';
	consistency_score: number;
	growth_score: number;
	trend_score: number;
	history_score: number;
	years_analyzed: number;
}

export interface FundamentalsLatest {
	payout_ratio: number | null;
	dividend_yield: number | null;
	pe_ratio: number | null;
	roe: number | null;
	roce: number | null;
	book_value: number | null;
	face_value: number | null;
	market_cap_cr: number | null;
	eps: number | null;
	revenue_growth: number | null;
	profit_growth: number | null;
	debt_to_equity: number | null;
	last_updated: string | null;
}

export interface FundamentalsYearly {
	fiscal_year: string;
	payout_ratio: number | null;
	eps: number | null;
	net_profit: number | null;
	revenue: number | null;
	roe: number | null;
	roce: number | null;
	div_yield: number | null;
	book_value: number | null;
	debt_to_equity: number | null;
}

export interface StatsResponse {
	symbol: string;
	name: string | null;
	current_price: number | null;
	yield_pct: number | null;
	splits: SplitRecord[];
	yearly_dividends: YearlyDividend[];
	recent_payments: DividendRecord[];
	cagr_stats: CAGRStats[];
	yield_cagr_stats: YieldCAGR[];
	dividend_quality: DividendQualityInfo | null;
	years_up: number;
	years_stalled: number;
	years_reduced: number;
	years_stopped: number;
	fundamentals_latest: FundamentalsLatest | null;
	fundamentals_yearly: FundamentalsYearly[];
}

export interface ScreenerResponse {
	symbol: string;
	latest: FundamentalsLatest | null;
	yearly: FundamentalsYearly[];
}

export interface TopStock {
	symbol: string;
	name: string | null;
	price: number | null;
	yield_pct: number | null;
	cagr_overall: number | null;
	years_up: number | null;
	dividend_quality_score: number | null;
	dividend_quality_rating: string | null;
}

export interface TopStocksResponse {
	by_yield: TopStock[];
	by_cagr: TopStock[];
	by_quality: TopStock[];
}

export interface UpdateRequest {
	symbol?: string;
	force?: boolean;
	max_age?: number;
	limit?: number;
}

export interface FilterParams {
	symbol?: string;
	min_yield?: number;
	max_yield?: number;
	div_growth_min?: number;
	div_3yr_min?: number;
	div_5yr_min?: number;
	div_10yr_min?: number;
	years_up?: number;
	years_stalled?: number;
	years_reduced?: number;
	years_stopped?: number;
	min_payout?: number;
	max_payout?: number;
	min_roe?: number;
	min_roce?: number;
	min_div_quality?: number;
	condition?: string;
	limit?: number;
}
