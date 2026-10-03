---
name: Forward Logistics Command
description: A light, Apple-clean station departures board for spotting the at-risk post and approving the convoy.
colors:
  ground: "#f5f5f7"
  panel: "#ffffff"
  ink: "#1d1d1f"
  ink-secondary: "#515154"
  ink-tertiary: "#6e6e73"
  hairline: "rgb(0 0 0 / 0.08)"
  selection-blue: "#0071e3"
  selection-blue-hover: "#0077ed"
  on-selection: "#ffffff"
  control-hover: "#f0f0f2"
  ok: "#1a7f3c"
  ok-wash: "#e6f4ea"
  warn: "#8a5a00"
  warn-wash: "#fff3d6"
  crit: "#c4201a"
  crit-wash: "#fde8e7"
typography:
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  time:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.4
    fontFeature: "tabular-nums"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
rounded:
  panel: "14px"
  focus: "6px"
  pill: "999px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
components:
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
  board-head:
    textColor: "{colors.ink-tertiary}"
    typography: "{typography.label}"
    padding: "8px 16px"
  board-row:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "12px 16px"
  board-row-selected:
    backgroundColor: "rgb(0 113 227 / 0.08)"
  time:
    typography: "{typography.time}"
    textColor: "{colors.ink}"
  btn:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "8px 12px"
  btn-primary:
    backgroundColor: "{colors.selection-blue}"
    textColor: "{colors.on-selection}"
    rounded: "{rounded.pill}"
    padding: "8px 12px"
  btn-primary-hover:
    backgroundColor: "{colors.selection-blue-hover}"
  chip-ok:
    backgroundColor: "{colors.ok-wash}"
    textColor: "{colors.ok}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-warn:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.warn}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  chip-crit:
    backgroundColor: "{colors.crit-wash}"
    textColor: "{colors.crit}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  pill:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
---

# Design System: Forward Logistics Command

## Overview

**Creative North Star: "The Departures Board"**

Every convoy and alert is a departure: a timed row with a place, a status and a time you can trust. The system is a station departures board and railway reservation chart set in light Apple-clean material: a pale grey ground, white panels, the platform UI font, tabular numerals, and one-pixel hairlines between rows. It is built for a planner or judge in a command room on a laptop or projector at 1280x720 or wider, who scans for the first red row, selects it, and approves the departure.

It is deliberately not a white-card analytics dashboard: no KPI tiles, no boxes inside boxes. Structure comes from a column-header row on every board and hairline rules, never from nested containers.

**Forecast panel (post view).** Selecting any alert, stock or dispatch row fills it: title with status chip and a dashed/solid line key (actual solid grey, predicted dashed ink; never colour alone), the one-sentence explanation, a stats `dl` (stock, days left, lead time), an MAE/MAPE badge with the naive baseline, a Recharts line chart with a text alternative, and up to two inbound convoys. Ink-only palette; status colour appears only inside chips.

**Key Characteristics:**
- Light, flat, hairline-ruled; depth is one faint ambient shadow on panels only.
- Blue means selection and nothing else; status colour lives only in labelled chips.
- Numbers are tabular and the running time sits right-aligned hard against the margin.
- One system font stack; hierarchy by size and weight on a fixed rem scale.

## Colors

A near-monochrome Apple-grey system with a single blue and three status inks that appear only inside chips.

### Primary
- **Selection Blue** (#0071e3): selection and primary actions only. Drives the selected-row wash (8% alpha), the focus ring, and the primary button; a row's primary button stays quiet white until its row is selected. Hover is #0077ed.

### Neutral
- **Ground Grey** (#f5f5f7): page background.
- **Panel White** (#ffffff): panels, pill, default buttons. The build defines this twice (`--panel`, `--panel-solid`) at the same value; recorded once.
- **Ink** (#1d1d1f): primary text.
- **Ink Secondary** (#515154): pill text.
- **Ink Tertiary** (#6e6e73): column headers, empty-state text, and the dimmed non-selected rows. Raised to #515154 under `prefers-contrast: more`.
- **Hairline** (rgb(0 0 0 / 0.08)): every rule and panel border.
- **Control Hover** (#f0f0f2): hover fill of default buttons.

### Status (chips only)
- **Ok** (#1a7f3c on #e6f4ea), **Warn** (#8a5a00 on #fff3d6), **Crit** (#c4201a on #fde8e7).

### Named Rules
**The Blue Is Selection Rule.** Blue marks the selected row, focus, and the one primary action of the selected row. It is never decoration, never a status.

**The Labelled Status Rule.** Green, amber and red appear only inside a chip that carries a text label (Green/Amber/Red or equivalent). Never colour alone, never as a row fill, border or text colour elsewhere. The one exception is the map: post markers fill with their worst item's status (Red also draws larger and carries a standing name label), degraded/closed routes draw amber dashed / red dotted while open routes stay neutral grey, and an always-visible legend labels every colour and dash.

## Typography

**Font:** the platform UI stack (-apple-system, BlinkMacSystemFont, SF Pro Text, Segoe UI Variable Text, Segoe UI, system-ui, sans-serif). No webfont.

**Character:** quiet, native, numeric. Tabular figures are set on the body so columns of days and ETAs align.

### Hierarchy
- **Title** (600, 1.25rem, 1.15, -0.02em): the app name in the top bar.
- **Headline** (650, 1.0625rem, -0.01em): panel titles.
- **Time** (700, 1.25rem, tabular, right-aligned): the running-time column of a board row; the largest, heaviest figure in a row.
- **Body** (400, 0.9375rem, 1.4): empty states and default text. Board row text is 1.0625rem.
- **Label** (600, 0.75rem, +0.04em, uppercase): board column headers only, in Ink Tertiary. Sizes on the scale: 0.75, 0.8125, 0.9375, 1.0625, 1.25rem.

### Named Rules
**The Right-Margin Time Rule.** The last numeric column is right-aligned (`.num`) hard against the panel padding and set in the Time style.

## Layout

A fixed command-room shell: a grid of a slim top bar over a main area, 12px outer padding and 12px gaps, minimum width 1100px, designed for 1280x720. The main area is two columns (1.6fr map and bottom band, a right column of at least 440px) and two rows (1.4fr over 1fr). The map occupies the top left; the right column holds Alerts over Dispatch plan, each scrolling independently; the bottom band holds Forecast beside Stock risk (5fr / 4fr). Spacing steps are 4, 8, 12, 16, 24px. Boards share one column template per board via a `--grid` variable so header and rows align. There is no responsive collapse below the minimum width.

## Elevation & Depth

Flat with one faint ambient lift. Panels carry `box-shadow: 0 1px 2px rgb(0 0 0 / 0.05), 0 4px 16px rgb(0 0 0 / 0.05)` plus a hairline border; nothing else has a shadow. Depth between rows is conveyed by hairlines and the selected-row wash, not by elevation.

### Named Rules
**The Hairline Only Rule.** Rows are separated by a single 1px rgb(0 0 0 / 0.08) rule; the last row has none. No nested cards.

## Shapes

Soft panels (14px) with pill-shaped controls (999px): buttons, chips and the status pill are fully rounded; the focus ring uses a 6px corner. Chips lead with a 6px dot in the chip's colour. The map's bottom corners follow the panel radius.

## Components

### Panels
A white, 14px-rounded, hairline-bordered, ambient-shadowed container with an h2 title (12px 16px 4px padding) and a scrolling body. Empty states are Ink Tertiary text at 8px 16px 16px.

### Board header and rows
Header: Label style, hairline above and below, padding 8px 16px. Row: same grid template, 12px vertical padding, 1.0625rem text, hairline below, press feedback of a 4% black wash. Selected: Selection Blue 8% wash, and every other row in that panel drops to Ink Tertiary while chips stay full strength. Rows and chips ship in Alerts, Dispatch plan and Stock risk. Board grids use `minmax(0, 1fr)` for the flexible column so long text can't widen a row past its header.

### Chips
Pill, 2px 8px, 0.75rem/600, +0.02em, leading 6px dot, colour pair per status (see Colors). Always a text label.

### Buttons
Pill, 600 0.8125rem, 8px 12px padding, white with hairline border, hover #f0f0f2. Press scales to 0.97 over 100ms (feedback on press, not release); disabled is 45% opacity. Primary is Selection Blue with white text, but inside a row it is white until that row is selected.

### Pill (API status)
White pill with hairline, 0.8125rem Ink Secondary text, 4px 12px; carries role="status".

### Time
The right-aligned Time-style figure at the end of a board row.

## Do's and Don'ts

### Do:
- **Do** keep a column-header row on every board and share its `--grid` template with the rows.
- **Do** right-align the running-time column and keep numerals tabular.
- **Do** pair every status colour with a text label inside a chip.
- **Do** give press feedback on press, with transitions off under `prefers-reduced-motion`.
- **Do** use the token spacing and rem type scales.

### Don't:
- **Don't** use blue for anything but selection, focus and the selected row's primary action.
- **Don't** use green, amber or red outside labelled chips.
- **Don't** nest boxes or cards inside panels, or add KPI tiles.
- **Don't** introduce a webfont or a second shadow style.
