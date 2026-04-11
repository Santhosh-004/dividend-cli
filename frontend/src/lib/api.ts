// Typed API client for the Dividend CLI backend

import type {
	DBSummary,
	FilterParams,
	FilterResult,
	ScreenerResponse,
	StatsResponse,
	TickerSummary,
	TopStocksResponse,
	UpdateRequest,
} from './types';
import { cacheGet, cacheSet } from './cache';

const BASE = '/api';

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
	let url = `${BASE}${path}`;
	if (params) {
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(params)) {
			if (v !== undefined && v !== null && v !== '') {
				qs.set(k, String(v));
			}
		}
		const str = qs.toString();
		if (str) url += `?${str}`;
	}
	const res = await fetch(url);
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail ?? `HTTP ${res.status}`);
	}
	return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
	const res = await fetch(`${BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail ?? `HTTP ${res.status}`);
	}
	return res.json();
}

async function cached<T>(key: string, ttl: number, fn: () => Promise<T>): Promise<T> {
	const hit = cacheGet<T>(key);
	if (hit !== null) return hit;
	const data = await fn();
	cacheSet(key, data, ttl);
	return data;
}

export const api = {
	getSummary: () =>
		cached<DBSummary>('summary', 60_000, () => get('/summary')),

	getTickers: (params?: { search?: string; limit?: number; offset?: number }) => {
		// Only cache the unconstrained full-list fetch (used for suggestions)
		if (!params?.search && !params?.offset) {
			const limit = params?.limit ?? 100;
			return cached<TickerSummary[]>(
				`tickers:${limit}`,
				300_000,
				() => get('/tickers', params as Record<string, unknown>),
			);
		}
		return get<TickerSummary[]>('/tickers', params as Record<string, unknown>);
	},

	filterStocks: (params: FilterParams) => {
		const key = `filter:${JSON.stringify(params)}`;
		return cached<FilterResult[]>(key, 120_000, () =>
			get('/filter', params as Record<string, unknown>),
		);
	},

	getStats: (symbol: string) =>
		cached<StatsResponse>(`stats:${symbol}`, 120_000, () =>
			get(`/stats/${encodeURIComponent(symbol)}`),
		),

	getScreener: (symbol: string) =>
		get<ScreenerResponse>(`/screener/${encodeURIComponent(symbol)}`),

	getTop: (n = 10) =>
		cached<TopStocksResponse>(`top:${n}`, 300_000, () => get('/top', { n })),

	startUpdate: (req: UpdateRequest) => post<{ job_id: string }>('/update', req),

	/** Returns an EventSource for SSE update progress */
	updateProgress: (jobId: string): EventSource =>
		new EventSource(`${BASE}/update/progress/${jobId}`),
};
