---
version: 1
slug: "frontend-src-app-jsx"
primary_target: "frontend/src/App.jsx"
related_targets: []
---

# Surface brief: Command dashboard (frontend/src/App.jsx)

Mode: Operate. Visitor: planner or judge in a command room, laptop or projector (>=1280px). Task: spot the at-risk post, open the alert, follow forecast -> route -> dispatch, approve. Code-led (no image generation). Material pinned by the user: light, Apple-clean.

## Direction contract

THESIS: Every convoy and alert is a departure: a timed row with a place, a status and a time you can trust. Refuses the white-card analytics dashboard with KPI tiles.
OWN-WORLD: Station departures board and railway reservation chart in light Apple-clean material: #f5f5f7 ground, white panels, system UI font, tabular numerals, one-device-pixel hairline rules between rows with no boxes inside boxes, right-aligned ETAs hard against the margin, a column-header row on every board. Blue accent for selection only; green, amber and red appear only in status chips that always carry a text label. Raises: selecting a row pulls its numbers into focus while other rows drop faint (Ikeda); right-aligned running times (cassette j-card); hairline rules only (centre-rail).
STORY: A planner scans the board for the first red row, selects it, and the map, forecast and dispatch row answer; they approve the departure.
FIRST VIEWPORT: 1280x720. Slim top bar (title, API status pill). Map fills left two thirds. Right third is a two-part board, Alerts over Dispatch, each with a header row (Post, Item, Status, ETA) and hairline-ruled rows scrolling independently. Forecast chart and stock-risk table share the band under the map. Approve sits at the right end of each dispatch row.
FORM: Station departures board / railway chart, candidate 5 of 7, seed key 32221c3b.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
