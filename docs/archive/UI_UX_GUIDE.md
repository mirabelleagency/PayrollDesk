> **ARCHIVED** — Superseded by [DESIGN_AUDIT.md](../DESIGN_AUDIT.md)
> for design system. Workflow diagrams and form patterns
> here remain valid reference material.

# PayrollDesk UI/UX Guide

> User interface documentation, design patterns, and
> workflow guides for PayrollDesk.

**Version:** 2.32.2  
**Last Updated:** December 24, 2025

---

## Table of Contents

1. [Design Overview](#design-overview)
2. [Layout System](#layout-system)
3. [Navigation](#navigation)
4. [Page Templates](#page-templates)
5. [Component Library](#component-library)
6. [User Workflows](#user-workflows)
7. [Form Patterns](#form-patterns)
8. [Status Indicators](#status-indicators)
9. [Accessibility](#accessibility)
10. [Mobile Responsiveness](#mobile-responsiveness)

---

## Design Overview

### Design Philosophy

PayrollDesk uses a **dark theme** optimized for:
- Extended work sessions (reduced eye strain)
- Financial data focus (clean, professional appearance)
- Clear visual hierarchy for critical information

### Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Background** | Deep Navy | `#0f172a` | Page background |
| **Surface** | Slate | `#1e293b` | Cards, panels |
| **Primary Text** | White | `#f8fafc` | Headings, important text |
| **Secondary Text** | Cool Gray | `#94a3b8` | Labels, descriptions |
| **Accent** | Blue | `#3b82f6` | Links, active states |
| **Success** | Green | `#22c55e` | Paid status, positive values |
| **Warning** | Amber | `#f59e0b` | On hold, pending |
| **Error** | Red | `#ef4444` | Errors, overdue |
| **Muted** | Slate Gray | `#64748b` | Inactive, disabled |

### Typography

```css
font-family: "Segoe UI", Tahoma, sans-serif;
```

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Page Title | `1.5rem` | 700 | `#f8fafc` |
| Section Header | `1.25rem` | 600 | `#f8fafc` |
| Card Title | `1rem` | 600 | `#f8fafc` |
| Body Text | `0.875rem` | 400 | `#94a3b8` |
| Labels | `0.75rem` | 500 | `#64748b` |
| Metrics | `1.5rem+` | 700 | Contextual |

---

## Layout System

### Page Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser Window                            │
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                       │
│          │  ┌─────────────────────────────────────────────────┐ │
│  SIDEBAR │  │              PAGE HEADER                        │ │
│          │  │  Title + Actions                                │ │
│  - Brand │  └─────────────────────────────────────────────────┘ │
│  - Nav   │                                                       │
│  - User  │  ┌─────────────────────────────────────────────────┐ │
│          │  │              CONTENT AREA                       │ │
│          │  │                                                 │ │
│          │  │  Cards, Tables, Forms                           │ │
│          │  │                                                 │ │
│          │  └─────────────────────────────────────────────────┘ │
│          │                                                       │
│          │                                        [v2.32.2] │
└──────────┴──────────────────────────────────────────────────────┘
```

### Grid Classes

| Class | Columns | Usage |
|-------|---------|-------|
| `.card-grid` | Auto-fit | Responsive card layouts |
| `.columns-2` | 2 | Two-column sections |
| `.columns-3` | 3 | Three-column KPI sections |
| `.columns-4` | 4 | Four-column compact grids |

### Spacing System

```css
/* Base unit: 8px */
4px   /* Tight spacing */
8px   /* Default padding */
16px  /* Standard gap */
24px  /* Section spacing */
32px  /* Large sections */
```

---

## Navigation

### Sidebar Structure

```
┌────────────────────┐
│  PD  Payroll Desk  │  ← Brand (logo + title)
│      [collapse ←]  │  ← Toggle button
├────────────────────┤
│  WORKSPACE         │  ← Section label
│  📊 Dashboard      │  ← Nav link (active)
│  🧾 Models         │
│  🗓️ Payroll Hub    │
│  💼 Commissions    │
│  📝 Changelog      │
├────────────────────┤
│  ACCOUNT           │  ← Section label
│  👤 Profile        │
│  👥 User Admin     │  ← Admin only
│  ⚙️ Admin Settings │  ← Admin only
├────────────────────┤
│  AB  username      │  ← User avatar + info
│      admin         │
│  🚪 Logout         │
└────────────────────┘
```

### Navigation States

| State | Visual |
|-------|--------|
| Default | White text, no background |
| Hover | Light background, brighter text |
| Active | Blue left border, highlighted background |
| Collapsed | Icons only, tooltip on hover |

### Mobile Navigation

- Hamburger menu (☰) appears at `< 768px`
- Sidebar slides in as overlay
- Tap outside or nav link to close

---

## Page Templates

### Template Hierarchy

```
base.html
├── dashboard/index.html
├── models/
│   ├── list.html
│   ├── view.html
│   ├── form.html (new/edit)
│   ├── snapshot.html
│   └── payments.html
├── schedules/
│   ├── list.html
│   ├── detail.html
│   ├── form.html
│   ├── adhoc.html
│   ├── all.html
│   └── all_table.html
├── commissions/
│   └── index.html
├── admin/
│   ├── users.html
│   ├── user_form.html
│   └── settings.html
├── auth/
│   └── login.html
├── profile/
│   └── index.html
└── changelog.html
```

### Page Header Pattern

Every page uses a consistent header structure:

```html
<section class="page-header">
    <div>
        <h1 class="page-title">Page Title</h1>
        <p>Descriptive subtitle for context.</p>
    </div>
    <div class="header-actions">
        <button class="button">Action</button>
    </div>
</section>
```

---

## Component Library

### Cards

```html
<!-- Basic Card -->
<div class="card">
    <h3 class="card-title">Title</h3>
    <div class="card-content">Content</div>
</div>

<!-- Metric Card -->
<div class="card metric-card">
    <h3 class="metric-card-title">Model Roster</h3>
    <div class="metric-grid">
        <div class="metric-item">
            <div class="metric-label">Total</div>
            <div class="metric-number">42</div>
        </div>
    </div>
</div>
```

### Hero KPI Cards

```html
<section class="hero-kpis">
    <div class="hero-kpi-card hero-kpi-card--primary">
        <div class="hero-kpi-label">Monthly Total</div>
        <div class="hero-kpi-value">$50,000</div>
        <div class="hero-kpi-trend hero-kpi-trend--up">↑ 5% from last month</div>
    </div>
</section>
```

| Modifier | Usage |
|----------|-------|
| `--primary` | Blue gradient, main KPI |
| `--alert` | Red border, needs attention |
| Default | Standard dark card |

### Buttons

| Class | Usage | Example |
|-------|-------|---------|
| `.button` | Primary actions | Save, Submit |
| `.button.secondary` | Secondary actions | Cancel |
| `.button.danger` | Destructive actions | Delete |
| `.button.export` | Export actions | Download |
| `.button.outline` | Tertiary actions | Filter |

```html
<button class="button">Primary</button>
<button class="button secondary">Secondary</button>
<button class="button danger">Delete</button>
```

### Tables

```html
<table class="styled-table">
    <thead>
        <tr>
            <th>Column 1</th>
            <th>Column 2</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>Data</td>
            <td>Data</td>
        </tr>
    </tbody>
</table>
```

Features:
- Alternating row colors
- Hover highlighting
- Sticky headers (on scroll)
- Responsive horizontal scroll

### Badges / Status Pills

```html
<span class="badge badge--success">Paid</span>
<span class="badge badge--warning">On Hold</span>
<span class="badge badge--danger">Overdue</span>
<span class="badge badge--muted">Inactive</span>
```

### Forms

```html
<form class="form-card">
    <div class="form-group">
        <label for="field">Label</label>
        <input type="text" id="field" class="form-input" required>
    </div>
    <div class="form-actions">
        <button type="submit" class="button">Save</button>
        <a href="/cancel" class="button secondary">Cancel</a>
    </div>
</form>
```

### Alerts / Messages

```html
<div class="alert alert--success">Operation completed successfully.</div>
<div class="alert alert--warning">Please review before continuing.</div>
<div class="alert alert--error">An error occurred.</div>
```

---

## User Workflows

### 1. Model Management Workflow

```
┌─────────────────┐
│  Models List    │ ← View all models with filters
│  /models        │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌──────────┐
│ + New │ │  View    │ ← Click model row
│Model  │ │  Detail  │
└───┬───┘ └────┬─────┘
    │          │
    ▼          ├──────────────┬──────────────┐
┌───────┐      ▼              ▼              ▼
│ Form  │ ┌────────┐    ┌──────────┐   ┌──────────┐
│Create │ │  Edit  │    │ Advances │   │ Adhoc    │
└───────┘ │  Form  │    │ Section  │   │ Payments │
          └────────┘    └──────────┘   └──────────┘
```

### 2. Payroll Cycle Workflow

```
┌─────────────────┐
│  Payroll Hub    │
│  /schedules     │
└────────┬────────┘
         │
         ├──────────────────┬────────────────┐
         ▼                  ▼                ▼
┌────────────────┐   ┌───────────┐   ┌────────────┐
│  Create New    │   │  View     │   │  All       │
│  Schedule Run  │   │  Existing │   │  Payments  │
│  /schedules/new│   │  Run      │   │  /all      │
└───────┬────────┘   └─────┬─────┘   └────────────┘
        │                  │
        │                  ▼
        │           ┌──────────────────────────────┐
        │           │  Schedule Detail             │
        │           │  - Payout table              │
        │           │  - Status updates            │
        │           │  - Export options            │
        │           │  - Add New Models button     │
        │           │  - NEW badge on added models │
        │           │  - Highlight for new entries │
        │           └──────────────────────────────┘
        │
        ▼
┌────────────────────────────────┐
│  Form: Select Year/Month       │
│  → Generates pay schedule      │
│  → Creates payout records      │
│  → Applies advance deductions  │
└────────────────────────────────┘
```

### 3. Dashboard Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                       DASHBOARD                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HERO KPIs                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │Monthly  │ │Monthly  │ │YTD      │ │Attention│              │
│  │Total    │ │Unpaid   │ │Paid     │ │Required │              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
│                                                                 │
│  METRIC CARDS                                                   │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │
│  │ Model Roster  │ │ Financial     │ │ Latest Cycle  │         │
│  │ - Total       │ │ - Lifetime    │ │ - Models Paid │         │
│  │ - Active      │ │ - Outstanding │ │ - Total       │         │
│  │ - Inactive    │ │ - Pending     │ │ - Breakdown   │         │
│  └───────────────┘ └───────────────┘ └───────────────┘         │
│                                                                 │
│  OVERDUE PAYMENTS (if any)                                      │
│  ┌─────────────────────────────────────────────────┐           │
│  │ Table of payments needing attention              │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                 │
│  RECENT ACTIVITY                                                │
│  ┌─────────────────────────────────────────────────┐           │
│  │ Timeline of recent schedule runs                 │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Commission Workflow

```
┌─────────────────┐
│  Commissions    │
│  /commissions   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Commission Dashboard                    │
│  - Summary metrics                       │
│  - Filter by status/date                 │
│  - Table of commission payouts           │
│     - Click row: Update status          │
│     - Bulk actions                       │
└─────────────────────────────────────────┘
```

### 5. Admin Workflow

```
┌─────────────────┐
│  Admin Panel    │
│  /admin         │
└────────┬────────┘
         │
    ┌────┴────────────┬─────────────────┐
    ▼                 ▼                 ▼
┌──────────┐   ┌───────────┐   ┌────────────┐
│  Users   │   │  Settings │   │  Deleted   │
│  List    │   │  Page     │   │  Models    │
└────┬─────┘   └─────┬─────┘   │  (Purge)   │
     │               │         └────────────┘
     ├───────┐       │
     ▼       ▼       ▼
┌───────┐ ┌──────┐ ┌────────────────────┐
│ New   │ │ Edit │ │  Maintenance       │
│ User  │ │ User │ │  - Cleanup runs    │
└───────┘ └──────┘ │  - Remove orphans  │
                   │  - Reset data      │
                   └────────────────────┘
```

---

## Form Patterns

### Form Layout

```
┌─────────────────────────────────────────┐
│  Section Title                          │
├─────────────────────────────────────────┤
│                                         │
│  Label *                                │
│  ┌─────────────────────────────────┐   │
│  │ Input field                      │   │
│  └─────────────────────────────────┘   │
│  Helper text or validation message      │
│                                         │
│  ┌─────────────────┐ ┌───────────────┐ │
│  │ Field 1         │ │ Field 2       │ │  ← Two-column for related fields
│  └─────────────────┘ └───────────────┘ │
│                                         │
├─────────────────────────────────────────┤
│  [Cancel]              [Save] [Submit]  │  ← Actions right-aligned
└─────────────────────────────────────────┘
```

### Input Types Used

| Type | Component | Usage |
|------|-----------|-------|
| Text | `<input type="text">` | Names, codes |
| Number | `<input type="number">` | Amounts, counts |
| Date | `<input type="date">` | Dates |
| Select | `<select>` | Dropdowns (status, frequency) |
| Textarea | `<textarea>` | Notes, descriptions |
| Checkbox | `<input type="checkbox">` | Boolean toggles |

### Validation States

```css
/* Error state */
.form-input.error {
    border-color: #ef4444;
}

.form-error {
    color: #ef4444;
    font-size: 0.75rem;
}
```

---

## Status Indicators

### Payout Statuses

| Status | Badge Color | Icon | Meaning |
|--------|-------------|------|---------|
| `paid` | Green | ✓ | Payment completed |
| `approved` | Blue | ✓ | Ready for payment |
| `on_hold` | Amber | ⏸ | Temporarily paused |
| `not_paid` | Gray | – | Awaiting action |

### Model Statuses

| Status | Display | Usage |
|--------|---------|-------|
| Active | Green badge | Currently on payroll |
| Inactive | Gray badge | Paused, not receiving payments |
| Deleted | (hidden) | Soft-deleted, visible to admin only |

### Advance Statuses

| Status | Badge Color | Workflow Position |
|--------|-------------|-------------------|
| `requested` | Blue | Initial request |
| `approved` | Amber | Awaiting activation |
| `active` | Green | Deductions ongoing |
| `closed` | Gray | Fully repaid |

### Commission Statuses

| Status | Badge Color |
|--------|-------------|
| `unpaid` | Amber |
| `paid` | Green |

---

## Accessibility

### Keyboard Navigation

- All interactive elements are focusable
- Tab order follows visual layout
- Focus indicators visible (outline on focus)
- Escape closes modals/overlays

### Screen Reader Support

```html
<!-- Hidden helper text -->
<span class="sr-only">Opens in new tab</span>

<!-- ARIA labels -->
<button aria-label="Toggle sidebar">...</button>
<nav aria-label="Main navigation">...</nav>
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.001ms !important;
        transition-duration: 0.001ms !important;
    }
}
```

### Color Contrast

All text meets WCAG AA standards:
- Normal text: 4.5:1 contrast ratio
- Large text: 3:1 contrast ratio
- Interactive elements: Clear focus states

---

## Mobile Responsiveness

### Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Desktop | `≥1024px` | Sidebar visible, multi-column grids |
| Tablet | `768px-1023px` | Collapsible sidebar, 2-column grids |
| Mobile | `<768px` | Hamburger menu, single column |

### Mobile Adaptations

1. **Sidebar** → Overlay with hamburger toggle
2. **Tables** → Horizontal scroll wrapper
3. **Forms** → Full-width inputs
4. **Cards** → Stack vertically
5. **Actions** → Bottom-fixed on long pages

### Touch Targets

- Minimum 44x44px for buttons/links
- Adequate spacing between interactive elements
- Swipe-friendly table scrolling

---

## File Reference

### Templates Location

```
app/templates/
├── base.html              # Main layout template (214 lines)
├── changelog.html         # Changelog viewer
├── admin/                 # Admin section templates
├── auth/                  # Login templates
├── commissions/           # Commission templates
├── dashboard/             # Dashboard template
├── models/                # Model management templates
├── profile/               # User profile templates
└── schedules/             # Payroll schedule templates
```

### Styles Location

```
app/static/css/
└── styles.css             # Main stylesheet (4,743 lines)
```

### Static Assets

```
app/static/
├── css/                   # Stylesheets
├── dist/                  # Vendor libraries
└── import_templates/      # CSV import templates
```

---

## Maintenance

### When to Update This Document

| Change | Update Section |
|--------|----------------|
| New page/template added | Page Templates |
| New component created | Component Library |
| Color scheme change | Design Overview |
| New user workflow | User Workflows |
| Form pattern added | Form Patterns |
| Status added/changed | Status Indicators |
| Breakpoint change | Mobile Responsiveness |

### Related Documentation

- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) - Backend architecture and API
- [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) - Documentation standards
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

*Document generated for PayrollDesk v2.32.2*
