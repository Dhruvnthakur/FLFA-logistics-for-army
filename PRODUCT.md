# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Depot Logistics Officers and Senior Planners working at a laptop or projector in a command room (PRD §4). They decide what to send, where and when, and need region-wide risk at a glance. Demo judges are a second audience: one must be able to trace diesel at Post 7 from forecast to delivery plan in under 2 minutes.

## Product Purpose
Student prototype of a predictive logistics and forward supply chain system for Indian Army forward posts. It forecasts demand, flags stock risk from a simulated IoT feed, shows route status and recommends dispatches on one command dashboard. Success: a new reading appears within 5 s, and clicking an alert walks forecast → route → dispatch.

## Positioning
One screen links forecast, stock risk, route status and the dispatch plan, so a single item (e.g. Post 7 diesel) can be followed end to end.

## Operating Context
Laptops at 1280px or wider, and projectors. The dashboard only reads from the API and polls every few seconds. Data is synthetic: Post 1..N, plausible regions (Ladakh, Arunachal), no real units.

## Capabilities and Constraints
- Status thresholds (Green/Amber/Red) and item priority are served by the backend `/stock`; the frontend never duplicates them.
- Every forecast shown reads as one sentence, e.g. "Post 7 runs out of diesel in 4 days".
- Dispatch rows can be approved and marked dispatched.
- No mobile layout, auth or offline mode (PRD non-goals).
- Map stack: react-leaflet with OpenStreetMap tiles; charts: Recharts.

## Brand Commitments
Visual direction pinned by the user: light, clean, Apple-style. No logo or palette exists yet.

## Evidence on Hand
Seeded synthetic network of depots and posts, with forecasts, alerts, routes and dispatch plans served by the existing API. No real data exists, and none may be invented.

## Product Principles
1. Status is never colour alone: always colour plus a text label.
2. One item must be traceable from forecast to dispatch in under 2 minutes.
3. Calm by default, loud only for real risk.
4. The dashboard reads; the backend decides.

## Accessibility & Inclusion
Status shown by colour and label. Legible at projector distance (1280px layout).
