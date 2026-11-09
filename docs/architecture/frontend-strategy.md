# Frontend strategy

The workspace is a desktop-first analysis surface. The reference mood is a dark urban command centre: a map as the primary canvas, a narrow control column, a context column for ranks and charts, and a time control that only moves data which actually has that grain. It is not a marketing page, and it is not a copy of any existing city product.

The attached command-centre image is a layout reference only. Its cities, counts, and “real-time” claims are not data for URBIX.

## Stack

Next.js with the App Router, React, TypeScript, Tailwind CSS, and shadcn/ui. Charts use Apache ECharts through one wrapper so colours, empty states, and number formatting stay consistent. The map is MapLibre GL JS with the OpenFreeMap dark style verified at `https://tiles.openfreemap.org/styles/dark`. A proprietary map token is not required.

## Visual system

| Token | Use |
| --- | --- |
| Deep navy and charcoal surfaces | Application shell, map surround, panels |
| Slate borders and secondary text | Structure and metadata |
| Cyan and blue | Selection, links, primary actions |
| Green | Available coverage and within-threshold conditions |
| Amber | Partial coverage, historical-only data, warnings |
| Red | High severity alerts and failed quality checks |

Severity colours encode data state. They are not decoration. Body text meets contrast on the navy surface. Numbers use tabular figures. Units are always visible. A prediction chip is visually distinct from an observation chip.

Motion is limited to map transitions and loading indicators. Panels do not animate for emphasis.

## Shell

Persistent regions:

- **Top bar.** City or country selector, district selector, date range, search, coverage summary, alerts, account.
- **Left navigation.** The groups below.
- **Context strip.** The selected place, the active dataset version, and the grain of the current view.

Search resolves `geographical_aliases` and official names. It does not geocode free text through an uncached public Nominatim endpoint from the browser.

## Navigation and routes

### Global intelligence

| Page | Route | Behaviour |
| --- | --- | --- |
| Global overview | `/` | World map of countries that have a coverage record. Cities with data are selectable. No global average is drawn from NYC alone. |
| Country | `/countries/[code]` | Admin regions and the cities URBIX has registered. |
| City explorer | `/cities` | Cards for integrated cities with a coverage matrix, not a score. |
| Comparison | `/compare` | Two loaded geographies, one variable, one grain. Disabled with an explanation when either side lacks the variable. |

### City intelligence

| Page | Route | Behaviour |
| --- | --- | --- |
| City overview | `/cities/[id]` | The command centre. Map plus the indicators that are available. Unavailable domains appear as named gaps. |
| Map | `/cities/[id]/map` | Full map workspace. |
| District | `/cities/[id]/units/[unitId]` | One unit, its parent relationship, and the datasets that actually match its grain. |

### Urban domains

| Page | Route |
| --- | --- |
| Traffic | `/cities/[id]/traffic` |
| Environment | `/cities/[id]/environment` |
| Public safety | `/cities/[id]/safety` |
| Population | `/cities/[id]/population` |
| Transport | `/cities/[id]/transport` |
| Waste | `/cities/[id]/waste` |
| Infrastructure | `/cities/[id]/infrastructure` |

Each domain page has the same skeleton: coverage banner, time control appropriate to the grain, map or ranked units, one primary chart, a data-source drawer, and links to predictions only when a promoted model exists.

### AI intelligence

| Page | Route |
| --- | --- |
| Assistant | `/cities/[id]/assistant` |
| Investigations | `/cities/[id]/investigations` and `/investigations/[investigationId]` |
| Predictive analytics | `/cities/[id]/models` |
| Anomalies | `/cities/[id]/anomalies` |
| Cross-domain | `/cities/[id]/cross-domain` |

The assistant is a panel that can also dock on the city overview. It shows the plan, the tools that ran, and the sections defined in the AI strategy. It is not an ungrounded chat transcript.

### Operations and administration

| Page | Route |
| --- | --- |
| Reports | `/reports` and `/reports/[id]` |
| Alerts | `/alerts` |
| Data sources | `/data/sources` |
| Data quality | `/data/quality` |
| Models | `/admin/models` |
| Connectors | `/admin/connectors` |
| Settings | `/admin/settings` |

Admin routes are local-only until authentication exists. Connector controls that would start a job are disabled in the UI until the worker endpoint exists. A control is not drawn if it cannot run.

## City command centre

Desktop layout, 12 columns:

- Left rail, 3 columns: domain coverage, layer toggles, selected-unit facts.
- Map, 6 columns: boundaries and the active layer.
- Right rail, 3 columns: ranked units for the selected variable, a trend chart, and the assistant entry.
- Bottom: a time control. For monthly waste it steps by month. For subway ridership it can step by hour. For an annual indicator it becomes a year select. It never offers a minute scrubber for a dataset that has no minutes.

The first screen shows NYC because it will be the only loaded city, and the global entry point makes that explicit.

## Map behaviour

- Pan, zoom, and keyboard focus.
- Layer list with status: ready, partial, historical, unavailable, loading, failed.
- Hover tooltip: name, value, unit, period, source, grain.
- Click selects a unit and opens the district route’s summary in the side panel without a full navigation, then a link opens the full district page.
- Administrative layers from PostGIS.
- Building layer only at high zoom, from vector tiles.
- Heat or H3 choropleth for collisions and, later, archived speeds.
- Complaint layer is an aggregate choropleth. There is no point layer of offences.
- Population layers state `census`, `projection`, or `gridded_model` in the legend.
- Comparing two layers uses a split or a paired legend, not two unrelated colour scales on one map.
- Empty selection explains which boundary was clicked and that no ready dataset covers it.

Basemap attribution includes OpenFreeMap and OpenStreetMap.

## Components

Reusable pieces, each with a loading, empty, and error state:

- `AppShell`, `TopBar`, `SideNav`, `PlacePicker`, `TimeControl`
- `CoverageBanner`, `SourceDrawer`, `GrainLabel`, `PredictionBadge`
- `MapCanvas`, `LayerPanel`, `MapTooltip`
- `TrendChart`, `RankList`, `DistributionChart`, `ActualVsPredicted`
- `InvestigationThread`, `EvidenceList`, `ReportView`
- `DataTable` with pagination and an explicit null glyph that is not `0`

Charts share one palette and one formatter. Axes are labeled with units. A chart without rows renders the empty state, not a zero line.

## Responsive behaviour

Desktop and laptop are the primary targets. At tablet width the right rail moves below the map. At mobile width the navigation becomes a drawer, the map remains usable, and the rank list stacks. Dense comparison and model diagnostics are allowed to require a wider viewport, with a short explanation rather than a broken layout.

## Data contract

The frontend consumes typed clients generated from the API’s OpenAPI schema or written to match it. Every numeric response includes `value`, `unit`, `datasetVersionId`, `temporalGrain`, and `status`. The UI has no sample NYC statistics checked into components.

## Accessibility

Interactive map controls have names. Colour is not the only status signal; coverage also uses a word. Charts have a table alternative. Focus order follows the shell, then the map controls, then the side panel.
