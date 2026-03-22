# Design Language Audit

> Audit Date: 2026-03-22 | Version: 2.48.1
> CSS: 8,424 lines | Templates: 26 files

## Overall Rating: 8/10

---

## Strengths

### Visual Identity — 9/10

- Dark slate theme (`#0f172a` → `#1e293b`) with blue
  accents (`#2563eb`) is cohesive and modern
- Gradient effects on logo, export buttons, and error
  pages are tasteful without being overdone
- Color palette consistent across all 26 templates
- Status chip colors communicate state instantly:
  green/paid, yellow/hold, red/unpaid, blue/approved

### Component Consistency — 8/10

| Component | Class | Usage |
|-----------|-------|-------|
| Buttons | `.button`, `.button--compact`, etc. | All pages |
| Cards | `.card` | All content sections |
| Tables | `.data-table` | All data views |
| Status badges | `.status-badge`, `.status-chip` | Schedules, payouts |
| Tags | `.tag` | Model status, filters |
| Breadcrumbs | `.breadcrumb` | 9+ pages |
| Hero KPIs | `.hero-kpi-card` | Dashboard, detail |
| Alerts | `.alert.success`, `.alert.error` | All forms |

### Typography & Spacing — 8/10

- Rem-based sizing with natural breakpoint scaling
- Title progression: `2rem → 1.5rem → 1.25rem`
- Consistent 8px spacing interval
- Font stack: Inter, system-ui, -apple-system, sans-serif

### Micro-interactions — 7/10

- Smooth hover transitions on buttons and cards
- Sidebar accordion with localStorage persistence
- Skeleton loading shimmer animation for async content
- Optimistic UI pulse for pending server confirmations
- Table row hover highlight (`rgba(37, 99, 235, 0.08)`)
- Collapsible sidebar with 0.25s ease transition

### Accessibility — 7/10

- Skip-link for keyboard navigation
- `aria-label` on interactive elements
- `prefers-reduced-motion` respected (4 instances)
- `:focus-visible` outlines on buttons and inputs
- Semantic HTML (`nav`, `main`, `section`, `aside`)
- Color contrast generally adequate on dark background

---

## Weaknesses

### CSS Architecture — 5/10

- **8,424 lines in a single file** — hard to
  navigate, maintain, and debug
- ~300 lines of inline `<style>` blocks in templates
  duplicate or override global styles
- **No CSS custom properties** — same hex codes
  repeated hundreds of times throughout
- Changing the accent color requires 50+ manual
  find-and-replace operations
- No design token system for spacing, colors,
  shadows, or border-radius values
- No utility classes — every layout is bespoke

### Mobile-First Design — 6/10 (improved to 7/10)

- Desktop-first approach with mobile overrides
- Hamburger breakpoint was at 480px (now fixed to
  768px)
- Table scroll wrappers were inconsistently applied
  (now fixed — all tables wrapped)
- Some inline `style` attributes set fixed pixel
  widths that don't adapt
- No mobile-first media queries (`min-width` used
  for desktop, `max-width` for mobile patches)

### Inline Styles — 6/10

Many templates use inline `style` attributes for:

- Fixed widths on table columns
- Layout grids (`display: grid; grid-template-columns`)
- Margins and padding overrides
- Color values

This makes styles harder to maintain and override.

### Template-Level CSS Duplication

Three templates define `.data-table-wrapper` styles
locally (now redundant since global rule was added):

- `schedules/list.html`
- `schedules/detail.html`
- `models/payments.html`

---

## Color Palette (extracted from CSS)

| Use | Color | Hex |
|-----|-------|-----|
| Background (body) | Dark navy | `#0f172a` |
| Card/section bg | Slate | `#1e293b` |
| Primary accent | Blue | `#2563eb` |
| Primary hover | Deep blue | `#1d4ed8` |
| Success | Green | `#22c55e` |
| Warning | Yellow | `#facc15` |
| Danger | Red | `#ef4444` |
| Text primary | Near-white | `#f8fafc` |
| Text secondary | Light slate | `#e2e8f0` |
| Text muted | Grey | `#94a3b8` |
| Text subtle | Dark grey | `#64748b` |
| Border default | Semi-transparent | `rgba(148, 163, 184, 0.15)` |
| Border hover | Semi-transparent | `rgba(148, 163, 184, 0.25)` |
| Export button | Green gradient | `#10b981 → #059669` |
| Error gradient | Amber | `#f59e0b → #fbbf24` |

---

## Breakpoint Architecture

| Breakpoint | Width | Purpose |
|------------|-------|---------|
| Desktop XL | `≥1200px` | 4-column card grids |
| Desktop | `≥1024px` | 3-column grids, full sidebar |
| Desktop SM | `≥960px` | Card grid transitions |
| Tablet | `≤900px` | Single-column layout |
| Mobile L | `≤768px` | Hamburger menu, sidebar hides |
| Mobile M | `≤640px` | Stacked headers/buttons |
| Mobile S | `≤480px` | Tighter padding, compact UI |

---

## Recommendations (Priority Order)

### High Priority

1. **Extract CSS custom properties** — Define color,
   spacing, and shadow tokens at `:root` level to
   enable easy theming and reduce duplication
2. **Split CSS into modules** — Break `styles.css`
   into logical files (base, layout, components,
   pages, responsive) and use a build step to
   concatenate

### Medium Priority

3. **Remove inline `<style>` blocks** from templates
   — move all styles to global CSS
4. **Replace inline `style` attributes** on tables
   and grids with CSS classes
5. **Add CSS variables** for the color palette so
   theme changes are one-line edits

### Low Priority

6. **Consider mobile-first rewrite** — flip media
   queries to `min-width` (progressive enhancement)
7. **Add utility classes** for common patterns
   (margins, flex layouts, text alignment)
8. **Implement dark/light theme toggle** using CSS
   custom properties (foundation already dark-only)

---

## Iconography Audit

> Audit Date: 2026-03-22

### Current State: SVG Icon System Complete

The emoji-based UI markers have been fully replaced
across `app/templates/` with a shared Lucide SVG
icon system in `app/icons.py`. Templates now use
`{{ icon('name') }}` so icons render consistently
on all platforms and can be styled with CSS.

Current implementation covers:

- **Page titles** — primary blue accent
- **Section headings** — muted slate icon color
- **Hero/KPI cards** — semantic icon colors by card
  variant (primary, warning, success, accent)
- **Action buttons** — icons inherit button color
- **Status indicators** — overdue, locked, warning,
  and save states now use SVG icons
- **Alert banners** — warning and danger icons match
  their banner state colors
- **Empty states** — neutral or contextual icons
- **JS-driven quick actions** — schedule detail and
  combined payouts keep SVG icons after DOM updates
- **Search placeholders** — emoji removed in favor of
  plain text placeholders
- **CSS pseudo-content** — the alert pseudo-element
  was changed from emoji to a styled indicator dot

### Semantic Color Behavior

The SVG system uses `currentColor`, and the main
stylesheet now assigns icon color by location:

| Context | Color Direction |
|---------|-----------------|
| Page titles | Blue accent |
| Section icons | Muted slate |
| Primary/info cards | Blue |
| Success/paid cards | Green |
| Warning/pending cards | Amber |
| Danger/compliance/overdue | Red |
| Accent/adhoc cards | Violet |
| Neutral/secondary areas | Slate |
| Buttons | Inherit button text color |

### Problems with Emoji Icons

1. **Inconsistent rendering** — Emoji look different
   on Windows, macOS, iOS, Android, and Linux.
   Colors, shapes, and sizes vary by OS and browser.
2. **No color control** — Cannot style emoji to
   match the app's blue/slate theme. They always
   render in their native colors.
3. **Unpredictable sizing** — Emoji don't scale
   linearly with `font-size`. Some appear larger
   or smaller than neighbors at the same size.
4. **No hover/active states** — Cannot change icon
   appearance on interaction (hover, focus, active).
5. **Accessibility gaps** — Screen readers may
   announce emoji inconsistently or announce the
   full Unicode name ("pile of poo" instead of
   "delete").
6. **Print rendering** — Emoji may not render in
   print stylesheets or PDF exports.

These issues are now resolved by the SVG rollout.

### Implemented Replacement: SVG Icon System

**Approach: Lucide Icons via Jinja2 helper**

[Lucide](https://lucide.dev) is a lightweight,
MIT-licensed icon library (1,500+ icons) used by
shadcn/ui and modern web apps. Implementation:

1. **Jinja2 icon helper** — `{{ icon('wallet') }}`
   renders an inline SVG with consistent sizing
2. **Theme-aware** — Icons inherit `currentColor`,
  then receive semantic color by UI context
3. **Scalable** — Crisp at any size, no pixelation
4. **Interactive** — Can change color on hover/focus
5. **Accessible** — Proper `aria-hidden="true"` with
   text labels, or `aria-label` for icon-only buttons
6. **Centralized** — New icons can be added in one
  place and reused across templates

### Outcome

- Template icon usage is now platform-consistent
- Icon styling is theme-aware and semantic
- UI no longer mixes emoji and SVG styles
- Future icon work can remain CSS-driven instead of
  editing per-template colors

**Alternative: Custom SVG sprite sheet**

A `<symbol>`-based sprite loaded once in `base.html`
and referenced with `<svg><use href="#icon-name">`.
More control but requires building/maintaining the
sprite file manually.

---

## Related

- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) — Architecture
- [archive/UI_UX_GUIDE.md](archive/UI_UX_GUIDE.md) — Workflow
  diagrams, form patterns, component HTML examples
- [DOCUMENT-INDEX.md](DOCUMENT-INDEX.md) — All docs
