# Market Analytics Dashboard Design

## Route

`/analytics`, linked from the main dashboard header.

## Desktop layout

```text
┌ Market Analytics ───────────────────────────── [Dashboard] ┐
│ Window [30 days] [Refresh]                               │
│ Note: observed events are not sales/inventory data       │
├ Collection trend (full width compact SVG) ───────────────┤
├ Category intelligence ─────┬ Top opportunities ──────────┤
│ category/currency table    │ ranked listing table         │
├ Watchlist effectiveness (full width table) ──────────────┤
└────────────────────────────────────────────────────────────┘
```

## Mobile

All two-column content becomes one column. Tables remain horizontally scrollable.

## States

- Loading: muted “Loading analytics…” message.
- Empty: each panel explains that more observations are required.
- Error: visible red error text; no stale success state.

## Tokens

Reuse the dashboard dark palette, panel border, pills, typography, spacing, and link colors. No external charting dependency; SVG is generated from escaped numeric API data.
