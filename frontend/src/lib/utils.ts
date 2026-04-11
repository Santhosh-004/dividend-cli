// Shared formatting and styling utilities — eliminates duplication across pages

export function fmt(n: number | null | undefined, decimals = 2): string {
	if (n == null) return '\u2014';
	return n.toLocaleString('en-IN', {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals,
	});
}

export function fmtPct(n: number | null | undefined): string {
	if (n == null) return '\u2014';
	return `${n.toFixed(2)}%`;
}

export function fmtCr(n: number | null | undefined): string {
	if (n == null) return '\u2014';
	if (n >= 100_000) return `\u20B9${(n / 100_000).toFixed(2)}L Cr`;
	if (n >= 1_000) return `\u20B9${(n / 1_000).toFixed(2)}K Cr`;
	return `\u20B9${n.toFixed(2)} Cr`;
}

export function fmtCompact(n: number | null | undefined): string {
	if (n == null) return '\u2014';
	if (Math.abs(n) >= 1e7) return `\u20B9${(n / 1e7).toFixed(1)}Cr`;
	if (Math.abs(n) >= 1e5) return `\u20B9${(n / 1e5).toFixed(1)}L`;
	if (Math.abs(n) >= 1e3) return `\u20B9${(n / 1e3).toFixed(1)}K`;
	return `\u20B9${n.toFixed(0)}`;
}

export function relativeTime(dateStr: string | null): string {
	if (!dateStr) return 'Never';
	const d = new Date(dateStr);
	const now = new Date();
	const diff = now.getTime() - d.getTime();
	const days = Math.floor(diff / 86_400_000);
	if (days === 0) return 'Today';
	if (days === 1) return 'Yesterday';
	if (days < 7) return `${days}d ago`;
	if (days < 30) return `${Math.floor(days / 7)}w ago`;
	return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function dividendQualityColor(rating: string | null | undefined): string {
	if (rating === 'Elite') return 'text-mint-400';
	if (rating === 'Strong') return 'text-coral-400';
	if (rating === 'Developing') return 'text-signal-amber';
	if (rating === 'Fragile') return 'text-signal-red';
	return 'text-ink-400';
}

export function dividendQualityLabel(rating: string | null | undefined): string {
	return rating ?? '\u2014';
}

export function dividendQualityBadgeClass(rating: string | null | undefined): string {
	if (rating === 'Elite') return 'badge-mint';
	if (rating === 'Strong') return 'badge-coral';
	if (rating === 'Developing') return 'badge-amber';
	if (rating === 'Fragile') return 'badge-red';
	return 'badge-neutral';
}

export function cagrColor(v: number | null | undefined): string {
	if (v == null) return 'text-ink-400';
	return v >= 0 ? 'text-mint-400' : 'text-signal-red';
}
