# DESIGN.md — Sentinel Mesh visual system v2: "The Examiner's Desk"

> v2 (2026-06-07) replaces the v1 Vercel dark-band system everywhere (dashboard,
> architecture.svg, film, playground). Rationale: v1 read as the generic
> AI-generated dark-purple dashboard — visually identical to other entries in the
> same competition. v2 is an auditor's working-papers language that is also
> semantically the product: a verified ledger keeps books.

## Concept

Financial auditor's working papers. Claims are **exhibits**, verdicts are
**rubber stamps**, the verified ledger is a **carbon-copy register**, metrics are
**dotted-leader findings tables**. Honesty cues (RECORDED RUN, measured-not-asserted)
are part of the document furniture, not disclaimers.

## Tokens

```css
--paper:#f6f2e9; --paper-2:#efe9da; --paper-deep:#e7dfcc;   /* sheet, panel, page bg */
--ink:#221e16; --ink-soft:#6b6354; --ink-faint:#998f7c;
--rule:#d9d0bc; --rule-strong:#b9ad92;                       /* hairlines */
--margin-red:#bf3b2d;                                        /* ledger margin rule */
--accept:#1e6b40; --veto:#b3261e; --flag:#996000;            /* stamp inks */
--carbon:#1f4e79;                                            /* register / verified */
```

Fonts: **Instrument Serif** (display + exhibit quotes, italic for emphasis) +
**IBM Plex Mono** (all data, labels, metadata). No other faces.

## Recurring elements

- **Red double margin rule** fixed at the left of every sheet (ledger paper).
- **Doc rule header**: org wordmark `SENTINEL MESH` (MESH in margin-red) over a
  2.5px ink rule; form number top-right (`WORKING PAPERS · FORM SM-n`).
- **Stamps**: uppercase, letterspaced, double border via inset box-shadows,
  `rotate(-2.4deg)`, `mix-blend-mode:multiply`, `stamp-in` overshoot keyframe.
- **Dotted leaders** between label and value in findings tables.
- **Carbon register**: `--paper-2` panel, carbon-blue ink, perforated edges via
  CSS mask, double rule under the heading.
- **Terminal exhibits** (film): dark `#16140f` window with 1.5px ink border +
  hard offset shadow `8px 10px 0 rgba(34,30,22,.12)` — a screenshot pinned to paper.
- **Paper grain**: data-URI SVG `feTurbulence` overlay at opacity .05
  (CSS only — inside standalone SVG it artifacts; omit there).

## Gotchas (live-earned)

- SVG connector `<path>` with multi-segment `d` needs `fill="none"` or it renders
  as a filled black polygon.
- Devpost description hard limit: 5,000 chars (counter under the Quill editor);
  Save disables silently when over.
- Quill on Devpost: paste via `container.__quill` + `dangerouslyPasteHTML`, then
  the editor's own Save button — and reload-verify.

## Surfaces

| Surface | File | Notes |
|---|---|---|
| Dashboard | `dashboard/index.html` | findings grid + diff stage + register + exam panel + playground CTA |
| Architecture | `dashboard/architecture.svg` | system-stack fonts only (Georgia/Menlo) — no webfont in standalone SVG |
| Film | `film/film.html` | 1920×1080; same tokens at film scale; terminal exhibits stay dark |
| Playground | `playground/static/index.html` | single-sheet layout, giant verdict stamp |
