// Lazy-loaded ticker list for search suggestions.
// Fetches all tickers once on first use and caches them.

import { writable } from 'svelte/store';
import type { TickerSummary } from './types';
import { api } from './api';

export const tickerList = writable<TickerSummary[]>([]);

let _loaded = false;
let _loading = false;

export async function ensureTickersLoaded(): Promise<void> {
	if (_loaded || _loading) return;
	_loading = true;
	try {
		const tickers = await api.getTickers({ limit: 5000 });
		tickerList.set(tickers);
		_loaded = true;
	} catch {
		// silently fail — search just won't show suggestions
	} finally {
		_loading = false;
	}
}
