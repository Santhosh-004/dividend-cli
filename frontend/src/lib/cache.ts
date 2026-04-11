// Simple in-memory TTL cache for frontend API calls

interface CacheEntry<T> {
	data: T;
	expiry: number; // ms timestamp
}

const _cache = new Map<string, CacheEntry<unknown>>();

export function cacheGet<T>(key: string): T | null {
	const entry = _cache.get(key);
	if (!entry) return null;
	if (Date.now() > entry.expiry) {
		_cache.delete(key);
		return null;
	}
	return entry.data as T;
}

export function cacheSet<T>(key: string, data: T, ttl = 60_000): void {
	_cache.set(key, { data, expiry: Date.now() + ttl });
}

export function cacheClear(): void {
	_cache.clear();
}
