# Optiqo Frontend — Backend Integration & Handoff Guide

## 1. Quickstart & Environment Setup

### Prerequisites
- Node.js >= 18.0.0
- npm >= 9.0.0

### Installation & Run
```bash
npm install
npm run dev
npm run test
npm run build
npx oxlint src
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Root URL of backend REST API without trailing slash. |
| `VITE_USE_MOCKS` | `false` | Set to `true` only to intentionally use mock adapters. |

---

## 2. Route Map

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `Overview` | Live Dashboard, 4 summary metric cards, pipeline stepper, demand forecast chart, risk donut, top alerts. (PRD J1) |
| `/validation` | `DataValidation` | Pre-flight sanity checks, findings table, slide-out drawer. (PRD J1, P0-01..03) |
| `/risk` | `RiskOverview` | Backend-ranked SKU-destination pairs and only the risk evidence present in the response. (PRD J2, P0-07) |
| `/plan` | `DistributionPlan` | Backend-generated transfer recommendations, checker results, plan lines, and sanitized run export. (PRD J3, P0-04..06, P0-11) |
| `/plan/:lineId` | `RecommendationDetail` | Backend explanation, forecast range, inventory, and shelf-life evidence. (PRD J4, P0-08) |
| `/backtest` | `Backtesting` | Backend K1-K7 KPI comparison and K8 cost decomposition; daily trajectories are not in the API response. (PRD J5, P0-09) |
| `/runs` | `RunDetails` | Solver execution logs, run comparison modal, CSV/JSON manifest downloads. (PRD J7) |
| `*` | `NotFound` | 404 page. |

---

## 3. Layout & Scroll Architecture

### 3-Zone Independent Scrolling
`html` and `body` have `overflow: hidden; max-height: 100dvh` — they never scroll.

| Zone | Element | Role |
|------|---------|------|
| Zone 1 | `aside` (Sidebar) | Internal nav scroll only |
| Zone 2 | `header` (Topbar) | Sticky — gains shadow when Zone 3 scrolls |
| Zone 3 | `main#main-content` | Sole scroll container for all page content |

**Rules:**
- All drawer/modal scroll locking must target `#main-content` via `mainEl.style.overflow = 'hidden'`, never `document.body`.
- Tooltips inside the collapsed sidebar use `createPortal(..., document.body)` with `position: fixed` to avoid `overflow-x: hidden` clipping.
- Scroll position is saved/restored per route by `useScrollRestoration` hook.

### Edge-to-Edge Layout
`app-shell-container` fills 100dvh x 100vw with no outer margin or border-radius. The violet canvas background has been removed for a clean full-bleed layout.

---

## 4. Component Inventory

### Layout & Shell
- **`AppShell.jsx`** — Root layout: pinned desktop sidebar, mobile overlay drawer, topbar, `#main-content` scroll zone. Persists sidebar collapse to `localStorage`.
- **`PageLayout.jsx`** — Standardized page wrapper with slots: `title`, `subtitle`, `headerActions`, `filterBar` (sticky under topbar), `summaryCards` (4-col grid), `sectionNav` (sticky in-page anchors), `children`.
- **`Topbar.jsx`** — Sticky top navbar with dynamic scroll elevation shadow, breadcrumbs, command palette trigger, solver status chip, notification popover, user menu.
- **`Sidebar.jsx`** — 3-section grouped navigation (Workspace / Analysis / Operations), collapsible rail mode, alert badges, pinned footer. Collapse state persisted to `localStorage('optiqo_sidebar_collapsed')`.

### Navigation & Search
- **`Breadcrumbs.jsx`** — Route-aware breadcrumb trail with Home icon link.
- **`CommandPalette.jsx`** — Dialog triggered by `Ctrl+K`. Fuzzy search across pages, SKUs, hubs, and quick actions. Keyboard arrow + Enter navigation.
- **`UserMenu.jsx`** — Dropdown: user profile, workspace label, theme toggle, API credentials.

### Data Display
- **`DataTable.jsx`** — Sortable table with sticky header, density toggle (persisted to `localStorage('optiqo_datatable_density')`), `selectedRowKey` row highlight, custom totals `footer`, pagination, empty/error states.
- **`StatCard.jsx`** — Metric card with large values, delta indicators, hover lift on interactive cards.
- **`SectionCard.jsx`** — Card container with header, subtitle, controls slot.
- **`ChartCard.jsx`** — SectionCard tailored for Recharts with custom `ChartTooltip`.

### Overlays & Feedback
- **`Drawer.jsx`** — Accessible slide-out panel, backdrop blur, `Escape` listener, focus trapping. Scroll locking targets `#main-content` only.
- **`Tooltip.jsx`** — Portal-based floating tooltip (`createPortal` into `document.body`, `position: fixed`). Prevents sidebar overflow clipping.
- **`HelpModal.jsx`** — Keyboard shortcuts modal triggered by `?` key.
- **`Toast.jsx`** — Toast notification provider and `useToast` hook.

### Status & Indicators
- **`RunStatusCard.jsx`** — Compact solver run status card in sidebar footer.
- **`StatusBanner.jsx`** — Maps all 7 PRD status codes (`ok`, `warning`, `error`) with action buttons.
- **`StatusChip.jsx`** — Compact status pill for solver codes.
- **`SeverityChip.jsx`** — Color-coded severity badge.

---

## 5. Global Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open Command Palette search |
| `?` | Open Help & Keyboard Shortcuts modal |
| `Esc` | Close any open modal, drawer, or palette |
| `Up` / `Down` | Navigate command palette results |
| `Enter` | Select command palette result |
| `Tab` / `Shift+Tab` | Trap focus inside open Drawer or modal |

---

## 6. Persistence Keys (localStorage)

| Key | Values | Component |
|-----|--------|-----------|
| `optiqo_sidebar_collapsed` | `'true'` / `'false'` | `AppShell.jsx` / `Sidebar.jsx` |
| `optiqo_datatable_density` | `'comfortable'` / `'compact'` | `DataTable.jsx` |
| `optiqo_theme` | `'light'` / `'dark'` | `useTheme.js` |

---

## 7. Backend endpoints used by frontend services

| Service Area | Endpoint | Method | Mock | Real Backend |
|--------------|----------|:------:|:----:|:------------:|
| **Demo data** | `/demo-data` | GET | N/A | Seeded synthetic dataset |
| **Validation** | `/data/validate` | POST | Ready | Synchronous validation report |
| **Forecast** | `/forecast` | POST | Ready | Synchronous forecast response |
| **Risk** | `/risk` | GET | Ready | Ranked alerts and shortage SKU IDs |
| **Plan** | `/plan` | POST | Ready | Synchronous plan and checker result |
| **Backtest** | `/backtest` | POST | Ready | Synchronous K1-K7 and K8 result |
| **Runs** | `/runs`, `/runs/{run_id}` | GET | Ready | Run index and persisted manifest |
| **Export** | `/runs/{run_id}/export` | GET | Ready | Sanitized backend CSV/JSON artifact |

---

## 8. Current integration boundaries

- `frontend/src/services/` adapts view models to the live `/api` routes. The
  generated OpenAPI page at `http://localhost:8000/api/docs` is canonical.
- The backend runs forecasting, optimization, and verification engines in
  process. The separate top-level `aiml/` package is an offline toolkit, not a
  remote service currently invoked by FastAPI.
- Risk responses do not include regions or numeric network deficits; backtest
  responses do not include daily trajectories. The UI does not synthesize
  missing values.

---

## 9. Manual Demo Script

### Journey J1: Validation (`/validation` -> `/`)
1. Open `/validation` and review the report returned by the configured dataset.
2. Click **"Validate Dataset"** — observe staged progress bar.
3. Click any finding row — observe slide-out drawer with schema coordinates.
4. Navigate to `/` Overview.

### Journey J2: Risk Overview (`/risk`)
1. Observe severity totals returned by the risk API.
2. Review network-shortage SKU IDs returned by the API; no unreported deficit quantities are shown.
3. Click **Cover (Days)** column header to sort — observe reset-to-default badge.
4. Click `SKU-1042 at WH-3` row — observe quantitative drivers drawer.

### Journey J3: Distribution Plan (`/plan`)
1. Review the plan summary and checker result returned by the backend.
2. Click a plan row to inspect its backend-provided evidence.
3. Use **Columns** to toggle visible columns.
4. Export CSV to download the sanitized backend artifact.

### Journey J4: Recommendation Detail (`/plan/:lineId`)
1. Open a line from the current plan and review its backend explanation and checker state.
2. Inspect available forecast, inventory, shelf-life, and optional next-best-warehouse evidence.
3. Test Prev/Next navigation.
4. Test 404: `/plan/unknown-line-999` — verify graceful empty state.

### Journey J5: Backtesting (`/backtest`)
1. Review aggregate K1-K7 comparisons and K8 cost decomposition.
2. Run a supported evaluation window and seed.
3. Daily trajectories are not shown because the API returns aggregate metrics only.

### Journey J7: Run Details (`/runs`)
1. Select two runs — click **"Compare Selected Runs"** to open comparison modal.
2. Open a run to inspect its persisted manifest.
3. Export its plan CSV or JSON manifest and verify the download.

---

## 10. Design Token Reference

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--color-shell` | `#FFFFFF` | `#151322` | App shell background (edge-to-edge) |
| `--color-surface` | `#FFFFFF` | `#1A1728` | Card and panel surfaces |
| `--color-sidebar` | `#F8F6FF` | `#12101E` | Sidebar pale-violet background |
| `--color-tint` | `#EFEBFF` | `#24203A` | Hover states, subtle highlights |
| `--color-primary` | `#7B68F5` | `#9585FF` | Violet accent, active states |
| `--color-primary-lilac` | `#B5AAF9` | `#7B68F5` | Secondary violet, chart fills |
| `--color-ink` | `#14121F` | `#EDE9FE` | Primary text |
| `--color-muted` | `#8E8BA0` | `#7F7B98` | Secondary text, labels |
| `--color-border` | `#E4E0F0` | `#29253E` | Card and component borders |
| `--radius-card` | `24px` | `24px` | Card border radius |
| `--radius-pill` | `9999px` | `9999px` | Button and chip border radius |
