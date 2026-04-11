<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
	import type { YearlyDividend } from '$lib/types';

	Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

	let { data }: { data: YearlyDividend[] } = $props();

	let canvas: HTMLCanvasElement | undefined;
	let chart: Chart | null = null;

	function buildChart() {
		if (!canvas) return;
		chart?.destroy();

		const labels = data.map(d => String(d.year));
		const values = data.map(d => d.consolidated_total);

		chart = new Chart(canvas, {
			type: 'bar',
			data: {
				labels,
				datasets: [
					{
						label: 'Dividend (₹)',
						data: values,
						backgroundColor: (ctx) => {
							const chart = ctx.chart;
							const { ctx: canvasCtx, chartArea } = chart;
							if (!chartArea) return 'rgba(255, 123, 97, 0.45)';
							const gradient = canvasCtx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
							gradient.addColorStop(0, 'rgba(255, 123, 97, 0.05)');
							gradient.addColorStop(0.5, 'rgba(255, 123, 97, 0.25)');
							gradient.addColorStop(1, 'rgba(242, 92, 58, 0.55)');
							return gradient;
						},
						borderColor: 'rgba(255, 123, 97, 0.5)',
						borderWidth: 1,
						borderRadius: 3,
						borderSkipped: false,
						hoverBackgroundColor: 'rgba(255, 123, 97, 0.7)',
					},
				],
			},
			options: {
				responsive: true,
				maintainAspectRatio: true,
				animation: {
					duration: 700,
					easing: 'easeOutQuart',
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(10, 12, 16, 0.95)',
						borderColor: 'rgba(255, 123, 97, 0.15)',
						borderWidth: 1,
						titleColor: '#faf9f6',
						bodyColor: '#9098b1',
						titleFont: { family: "'Geist', sans-serif", weight: 600 as const },
						bodyFont: { family: "'Geist Mono', monospace" },
						padding: 10,
						cornerRadius: 6,
						displayColors: false,
						callbacks: {
							label: ctx => `₹${(ctx.raw as number).toFixed(2)} per share`,
						},
					},
				},
				scales: {
					x: {
						ticks: { color: '#545a72', font: { size: 10, family: "'Geist Mono', monospace" } },
						grid: { display: false },
						border: { display: false },
					},
					y: {
						ticks: {
							color: '#545a72',
							font: { size: 10, family: "'Geist Mono', monospace" },
							callback: v => `₹${v}`,
						},
						grid: { color: 'rgba(144, 152, 177, 0.05)' },
						border: { display: false },
					},
				},
			},
		});
	}

	onMount(() => buildChart());

	$effect(() => {
		data;
		buildChart();
	});

	onDestroy(() => chart?.destroy());
</script>

<canvas bind:this={canvas} class="w-full"></canvas>
