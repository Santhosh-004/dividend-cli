# Dividend CLI Frontend

This is the SvelteKit frontend for `dividend-cli`.

It is built as a static app and served by the FastAPI backend in `dividend_calculator.server`.

## Tech stack

- SvelteKit
- Svelte 5 runes mode
- TypeScript
- Tailwind CSS v4
- Chart.js

## Development

Install frontend dependencies:

```bash
npm install
```

Run the frontend dev server:

```bash
npm run dev
```

The Vite config proxies `/api` requests to the backend running on `127.0.0.1:7788`.

## Production build

Build the frontend:

```bash
npm run build
```

This writes static assets to `frontend/dist/`, which the FastAPI server serves in production/local `serve` mode.

## Notes

- If you change frontend code, rebuild before testing through `dividend-cli serve`.
- The frontend is designed around dividend quality, dividend growth, and split-aware annual dividend history.
