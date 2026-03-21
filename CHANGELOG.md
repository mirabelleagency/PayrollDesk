# Changelog

All notable changes to this project will be documented in this file.

## v2.50.0 - 2026-03-22

### Added
- feat(ui): Lucide SVG icon system — `app/icons.py` renders inline SVG icons with configurable size and CSS classes, replacing emoji characters
- feat(css): Icon styling rules — `.icon`, `.page-title .icon`, `.section-icon .icon`, hero/metric card icon sizes, `.button .icon` alignment
- docs: Iconography audit section added to `docs/DESIGN_AUDIT.md` — emoji inventory, replacement strategy, rollout plan

### Changed
- refactor(templates): Replaced emoji with `{{ icon() }}` calls in login, changelog, audit log, pending advances, and purge confirm templates
- refactor(deps): Registered `icon` as Jinja2 global template function via `app/dependencies.py`

---

## v2.49.0 - 2026-03-22

### Added
- feat(ui): Favicon — blue gradient calendar icon matching sidebar logo, added to all page types (base, login, error)
- feat(ui): Styled error pages for 400, 403, 404, 405, 500 — browser requests now get a branded error card instead of raw JSON
- feat(responsive): Hamburger menu breakpoint raised from 480px to 768px — mobile menu now activates on tablets and phones per UI guide
- feat(responsive): Global `.data-table-wrapper` CSS rule with `overflow-x: auto` — all 20+ data tables now scroll horizontally on mobile
- feat(responsive): Touch-target enforcement — compact buttons get `min-height: 44px` on screens ≤768px
- feat(responsive): Resolve duplicates grid uses `auto-fit` for mobile stacking
- docs: Design language audit (`docs/DESIGN_AUDIT.md`) — color palette, breakpoints, component inventory, 8/10 rating with recommendations
- docs: README now links to all 13 docs in `docs/` (was zero links before)
- docs: Created `COLLABORATION_LOG.md` (required by project conventions, was missing)
- docs: Copilot audit protocol (`.github/copilot-audit-protocol.md`)

### Changed
- refactor(main): HTTP exception handler now renders styled HTML error pages for browser requests while preserving JSON responses for API clients
- style(css): Sidebar breakpoints restructured — at ≤768px sidebar hides off-screen, hamburger toggle appears (was overlapping at 481–768px)
- docs: Updated `copilot-instructions.md` with current tech stack, coding conventions, and command system
- docs: Updated `ISSUES.md` audit version from v2.44.0 to v2.48.1
- docs: Updated `TECHNICAL_SPEC.md` version to v2.48.1
- docs: Updated `README.md` — removed SQLite references, updated DB config table

### Fixed
- fix(responsive): Table scroll wrappers added to `all_table.html`, `audit_log.html`, `combined_payouts.html`, `detail.html` (alert table), `list.html` (payment history)
- fix(ui): Error page now loads `styles.min.css?v=4` instead of unminified `styles.css`

### Removed
- Removed obsolete `docs/tasksync.md`
- Removed `.github/workflows/auto-versioning.yml` (unused)
- CSS cache-bust version remains `v=4` (styles changed but not structurally)

---

## v2.48.1 - 2026-03-22

### Fixed
- fix(export): `_compute_run_etag` referenced non-existent `Payout.updated_at` column, crashing Excel export — replaced with `func.max(Payout.id)`

## v2.48.0 - 2026-03-17

### Added
- feat(ui): Settings page UX redesign
  - Breadcrumb navigation (Dashboard > Settings)
  - Config Name + Currency fields side-by-side (two-column grid)
  - Pay day picker rendered in a styled bordered container with CSS classes
  - Hidden raw JSON input — day picker buttons are the primary interaction
  - Frequency Plans help text moved to a styled callout box with code formatting
  - Maintenance actions redesigned as individual sub-cards in a responsive grid
  - Amber "warning" buttons for maintenance actions (replacing mismatched primary/secondary)
  - Danger Zone with red-tinted background, stacked layout, prominent warning copy
- feat(css): New CSS components — `.settings-day-picker`, `.settings-day-btn`, `.settings-help-callout`, `.settings-maintenance-grid`, `.settings-maintenance-card`, `.settings-danger-zone`, `.button--warning`
- feat(security): Global `getCsrfToken()` JS helper function in base template for fetch calls

### Fixed
- fix(security): CSRF token missing from all AJAX/fetch POST calls — status changes, bulk updates, commission toggles, and alert resolutions now include `_csrf_token` in FormData
  - Fixed in: combined_payouts.html, detail.html, commissions/index.html
- fix(ui): Approve button toggle on schedule detail page — clicking "Unmark Approved" was incorrectly changing status to `on_hold` instead of `not_paid`
  - Root cause: JS `applyRowStatusUpdate` only handled 2 buttons but template renders 3 (Paid, Approved, Hold); `buttons[1]` (Approve) was treated as Hold button

### Changed
- Combined Payouts "actionable" filter now shows only `approved` items (previously included `on_hold`)
- CSS cache-bust version bumped to `v=4`

---

## v2.47.0 - 2026-03-17

### Added
- feat(ui): Collapsible sidebar sections with accordion behavior
  - Workspace, Admin, and Account sections toggle on click with chevron indicators
  - Only one section expanded at a time (accordion pattern)
  - Workspace section expanded by default on first visit
  - State persisted to localStorage across page loads
  - Smooth 0.25s ease-in-out collapse/expand animation
- feat(ui): Button tooltips across all templates (15 files)
  - Added descriptive `title` attributes to ~80+ buttons and action links
  - Covers admin, dashboard, models, schedules, profile, and auth pages
- feat(ui): Auto-apply filters on Combined Payouts (onchange submit, debounced text input)
- feat(ui): Breadcrumb navigation on 9 pages (cycle detail, model profile, model form, combined payouts, ad hoc, snapshot, all payments, all cycles card, all cycles table)
- feat(ui): Breadcrumb CSS component in global stylesheet
- feat(ui): Combined Payouts as standalone sidebar nav item with document icon

### Changed
- Combined Payouts defaults to "Actionable" status filter (on_hold + approved)
- Combined Payouts hero cards redesigned using schedule-metric pattern (matching cycle detail page)
- Combined Payouts hero cards moved above filters section
- Dashboard "View All Payouts" renamed to "View All Cycles" linking to `/schedules`
- Payroll Hub "Combined Payouts" button removed (now in sidebar)
- Payroll Hub: removed duplicate "Auto-Generate Drafts" button from Upcoming Pay Dates section
- CSS cache-busting query string added to stylesheet link
- All navigation "Back to..." buttons replaced with breadcrumbs across 7 pages

### Removed
- Redundant "Back to Hub" button from Combined Payouts page
- Redundant navigation buttons from cycle detail, model profile, snapshot, payments, all cycles, ad hoc pages
- Empty unused template `all_content.html`

### Fixed
- "Back to Dashboard" mislabeled as "Back to Dashboard" on All Cycles table (was pointing wrong)
- Payroll Hub active state in sidebar now correctly excludes Combined Payouts path

## v2.46.0 - 2026-03-17

### Added
- feat(schedules): Combined Payouts view (`/schedules/combined-payouts`)
  - Flat table showing all individual payouts across every cycle for a selected year
  - Columns: Cycle (linked), Pay Date, Code (linked), Working Name, Method, Frequency, Amount, Status, Notes, Actions
  - Filter by year, status, code, frequency, and payment method
  - "Actionable" quick filter (on_hold + approved combined) for accountant workflow
  - Per-row "Mark as Paid" button with optimistic UI
  - Checkbox selection + bulk "Mark as Paid" for batch processing
  - Summary cards: payout count, total amount, paid, outstanding
  - Overdue and locked payout indicators
- feat(crud): `list_all_payouts()` function for querying payouts across multiple runs with filters
- feat(schedules): cross-run bulk status update endpoint (`POST /schedules/combined-payouts/bulk-status`)

### Changed
- Dashboard "View All Cycles" button now links to Combined Payouts view
- Payroll Hub header: replaced "All Cycles Table" button with "Combined Payouts"
- All Cycles Table page: added "Combined Payouts" link in header actions

## v2.45.0 - 2026-01-11

### Added
- feat(crud): batch query optimizations for dashboard data (Enhancement #4)
  - `batch_run_payment_summaries(db, run_ids)` — 4 queries instead of 3×N
  - `batch_frequency_counts(db, run_ids)` — 1 query with GROUP BY instead of N
  - Dashboard and runs-by-year views now use batch functions

- feat(schedules): advance deduction confirmation dialog (Enhancement #6)
  - `confirm()` prompt when marking a payout as "paid" with active advance deduction
  - Shows deduction amount and asks for explicit confirmation
  - `update_payout()` and `_realize_allocations_for_paid_payout()` now return deducted amounts

- feat(schedules): advance deduction toast notifications (Enhancement #8)
  - `showAdvanceToast()` animated bottom-right toast for deducted amounts
  - Triggers on single payout status change and bulk status updates
  - 4-second auto-dismiss with close button

- feat(admin): bulk advance approval workflow (Enhancement #10)
  - New `GET /admin/advances/pending` page with checkbox selection
  - `POST /admin/advances/bulk-approve` route with audit logging
  - `list_pending_advances()` CRUD function
  - "Advances" nav link in admin sidebar with dollar-sign icon

- feat(schedules): export cache with ETag headers (Enhancement #11)
  - Lightweight data-timestamp ETag (payout count + max updated_at)
  - 304 Not Modified returned for unchanged exports
  - File-based ETag (mtime + size) for pre-generated export files
  - Applied to CSV, Excel, and static file download endpoints

- feat(admin): pay config visual day picker (Enhancement #15)
  - Toggle buttons for days 1-31 + EOM
  - Syncs with JSON input field bidirectionally
  - Updates frequency plan date previews on change

- feat(admin): frequency plan computed dates preview (Enhancement #17)
  - "Resolved Pay Dates" column in frequency plans table
  - `resolveIndices()` maps pay_day_indices to ordinal labels (e.g., "7th, 14th, 21st, EOM")
  - Live updates on index input change

### Changed
- refactor(admin/users): unify user management styling (Enhancement #12)
  - `users.html` — removed ~160 lines of inline `<style>`, replaced with design system classes
  - `user_form.html` — removed all inline styles, uses `.card`, `.form`, `.form-row`, `.form-actions`

- refactor(admin/users): password reset UX improvements (Enhancement #16)
  - Password reset moved from inline input to `<dialog>` modal per user
  - New password + confirm password fields with `validateResetForm()` validation
  - Mismatch error display and cancel button

- refactor(admin/audit_log): fix inconsistent button classes
  - Replaced `btn btn--sm btn--primary/secondary` with `button button--compact button--primary/secondary`
  - Replaced inline styles with design system utility classes (`.text-muted`, `.code-badge`, `.pagination`)

- refactor(profile): remove inline style block (~100 lines)
  - Replaced custom `.profile-container`, `.btn-submit`, `.btn-cancel` with design system classes
  - Uses `.card`, `.form`, `.form-row`, `.form-actions`, `.button--primary`, `.button--secondary`, `.alert`

- refactor(admin/pending_advances): replace inline styles with utility classes
  - Uses `.page-header__sub`, `.text-muted`, `.cell--center`, `.form-actions`

- refactor(sidebar): reorganize navigation for clarity
  - Separate "Admin" section label for admin-only links (was mixed under "Account")
  - "Account" section now at bottom with My Profile and Changelog
  - Admin links reordered: Settings → Users → Advances → Audit Log (most-to-least used)
  - Distinct wallet icon for Advances (was using same dollar sign as Commissions)
  - Clock icon for Audit Log (was using same document icon as Changelog)
  - "Admin Settings" renamed to "Settings" (already in Admin section)
  - "User Admin" renamed to "Users"

- refactor(admin/settings): improve settings page UX
  - Split Maintenance into "Maintenance" (cleanup) and "Danger Zone" (destructive reset)
  - Danger Zone has red border and explicit warning styling
  - Fixed `button secondary` → `button--secondary` (missing `--` prefix)
  - Fixed reset button: inline danger styles → `button--danger` class
  - Added confirmation dialog on "Delete Empty Runs"
  - Removed confusing "Tools" section with raw API endpoints
  - All section descriptions use `.page-header__sub` instead of inline styles
  - Table inputs use `.table-input` class instead of inline styles

- style(css): add shared utility classes to design system
  - `.text-muted`, `.cell--nowrap`, `.cell--sm`, `.cell--center` — table/text helpers
  - `.code-badge` — inline code chip styling
  - `.details-toggle`, `.details-pre` — expandable detail formatting
  - `.page-header__sub` — page header subtitle
  - `.pagination`, `.pagination__info` — pagination nav component
  - `.table-input` — inline table input with focus states
  - `.maintenance-action` — stacked button + description layout

### Verified
- Enhancement #9 (Bulk compensation alert resolution) — already fully implemented
  - Backend: `bulk_resolve_alerts` endpoint exists
  - Frontend: "Apply All Pro-rated" and "Dismiss All" buttons present in UI

### Tests
- Test count: 233 passed, 7 pre-existing failures (UNIQUE constraint in test fixtures)

---

## v2.44.0 - 2026-01-10

### Added
- feat(schedules): clickable model codes in schedule detail page
  - Model codes in payout table now link to `/models/{id}`
  - Model codes in compensation alert table link to model profile
  - Blue link styling with hover effects matching app theme
  - Proper focus states for keyboard navigation

### Changed
- style(schedules): standardize buttons in compensation alert banner
  - Replace custom btn--* classes with standard .button system
  - Use `button--success` (green) for "Apply New"
  - Use `button--info` (blue) for "Pro-rate"
  - Use `button--secondary` (outline) for "Keep Original" / "Dismiss"
  - Use `button--warning` (amber) for "Show/Hide Details" toggle
  - Add clickable header area to expand/collapse alert details

- refactor(models): trigger alerts from Compensation Adjustments panel
  - New/modified entries in Compensation Adjustments now generate alerts
  - Remove separate "Effective Date of Change" field from main form
  - Uses existing effective date from adjustment records directly

### Tests
- Test count: 234 (unchanged)
- All tests passing

---

## v2.43.0 - 2026-01-10

### Added
- feat(models): Compensation Alert System for mid-cycle compensation changes
  - New `PayoutCompensationAlert` database model tracking compensation changes
  - Alert generation when a new compensation adjustment is created via the Compensation Adjustments panel
  - Pro-rata calculation support for monthly/weekly/biweekly payment frequencies
  - Integration with existing Compensation Adjustments feature for effective date tracking

- feat(schedules): Alert management UI on schedule run detail page
  - Alert banner showing count of pending compensation alerts
  - Collapsible table displaying affected payouts with original/new/prorated amounts
  - Individual alert resolution: Apply New Amount, Apply Pro-rated, Dismiss, Acknowledge
  - Bulk resolve functionality for handling multiple alerts at once
  - Toast notifications for success/error feedback

- feat(api): Compensation alert API endpoints
  - `GET /{run_id}/compensation-alerts` - List alerts for schedule run
  - `GET /{run_id}/compensation-alerts/count` - Count pending alerts
  - `POST /{run_id}/compensation-alerts/{alert_id}/resolve` - Resolve single alert
  - `POST /{run_id}/compensation-alerts/bulk-resolve` - Bulk resolve alerts
  - `GET /{run_id}/payouts/{payout_id}/alert` - Get alert for specific payout

- feat(crud): Compensation alert CRUD functions
  - `create_compensation_alert()` - Create or update alert
  - `list_compensation_alerts()` - Query alerts with filters
  - `get_compensation_alert()` - Get alert by ID
  - `count_pending_alerts_for_run()` - Count pending for schedule
  - `get_alert_for_payout()` - Get pending alert for payout
  - `resolve_compensation_alert()` - Mark alert as applied/dismissed/acknowledged
  - `apply_alert_to_payout()` - Apply amount change and resolve
  - `generate_alerts_for_compensation_change()` - Auto-generate on adjustment creation
  - `calculate_prorated_compensation()` - Pro-rata calculation engine
  - `bulk_resolve_alerts()` - Resolve multiple alerts

### Changed
- refactor(models/update): trigger alert generation from Compensation Adjustments panel
  - New or modified entries in Compensation Adjustments now generate alerts for affected payouts
  - Uses existing effective date from the adjustment (no additional date field required)
  - Creates alerts for unpaid payouts in schedule runs matching the adjustment's effective month

### Database
- Migration: `fe8ae1eb2e95_add_payout_compensation_alerts_table.py`
  - New `payout_compensation_alerts` table
  - Indexes on payout_id, model_id, schedule_run_id, status
  - Foreign key constraints to payouts, models, schedule_runs

### Tests
- New: `tests/test_compensation_alerts.py` with 16 tests
  - TestCompensationAlertCreation (3 tests)
  - TestAlertListing (3 tests)
  - TestAlertResolution (4 tests)
  - TestProRataCalculation (3 tests)
  - TestAlertGeneration (3 tests)
- Test count: 234 (16 new)
- All tests passing

---

## v2.42.0 - 2026-01-06

### Added
- feat(crud): comprehensive payment totals functions
  - `total_adhoc_paid_by_model()` - Sum paid adhoc payments per model
  - `total_commission_paid_by_model()` - Sum paid commission payouts per model
  - `top_paid_models_comprehensive()` - Top earners with payroll/adhoc/commission breakdown
  - `total_paid_by_model_comprehensive()` - Map of comprehensive totals for all models

### Changed
- refactor(dashboard): update Top Earners to show comprehensive payment totals
  - Combined total now includes payroll + adhoc + commission payments
  - Inline breakdown shows adhoc/commission amounts when present
  - Hover tooltip displays full breakdown: "Payroll: $X | Ad Hoc: $Y | Commission: $Z"
  
- refactor(models/list): update Lifetime Paid column with comprehensive totals
  - Model list now shows combined total from all payment sources
  - Color-coded breakdown: blue for adhoc, amber for commission
  - Tooltip on hover shows full breakdown

- refactor(models/view): update Total Paid stats with comprehensive breakdown
  - Main stat shows combined total with "(Combined)" label
  - Detailed breakdown displayed below when adhoc/commission > 0
  - Payment Information section updated with tooltip

### Fixed
- fix(totals): adhoc payments and commission payouts now included in model total paid
  - Previously only regular payroll payouts were counted
  - Now all three payment types are aggregated for accurate lifetime totals

### Tests
- Test count: 218 (unchanged)
- All tests passing

---

## v2.41.0 - 2026-01-06

### Added
- feat(schedules): highlight newly added models in schedule view
  - Success banner now displays specific model codes that were added
  - Green gradient highlight on newly added payout rows
  - "NEW" badge displayed next to each newly added model code
  - Auto-scroll to first highlighted row for easy visibility
  - "Clear Highlights" button to dismiss visual indicators and clean URL
  - URL parameters `added` and `added_codes` for tracking added models

### Changed
- refactor(schedules): update add-new-models endpoint to pass model codes
  - Redirect now includes `added_codes` parameter for UI highlighting
  - Maintains backward compatibility with existing `added` count parameter

### Tests
- Test count: 218 (unchanged)
- All tests passing

---

## v2.40.0 - 2025-12-24

### Changed
- refactor(view.html): extract 132+ inline styles to BEM classes
  - `.model-view-actions`, `.model-view-actions__form` for button groups
  - `.button--action-paid/pending/delete/neutral` compact button variants
  - `.model-view-expand-*` classes for expandable table rows
  - `.model-view-cell--*` variants (nowrap, center, truncate, minwidth)
  - `.model-view-strong--warning`, `.model-view-value--*` text variants
  - `.model-view-table-wrap` for no-padding table containers
  - `.status-chip--muted` variant for closed advance status
  - Replace `style=display:none` with `hidden` attribute
- refactor(view.html): improve accessibility
  - Add `aria-hidden="true"` to decorative emoji icons
  - Add `aria-labelledby` and `aria-controls` to collapsible details
  - Add `aria-expanded` attribute updated dynamically via JS
  - Add `role="alert"` and `role="status"` to feedback messages
- feat(view.html): add loading states on admin forms
  - `.button--loading` with spinner animation
  - JavaScript handler disables submit button during form submission
  - Prevents double-submission on slow connections
- Regenerate minified CSS (153KB → 114KB)

### Fixed
- No fixes in this release

### Tests
- Test count: 218 (unchanged)
- All tests passing

---

## v2.39.0 - 2025-12-24

### Added
- feat(models/form): form route integration tests
  - 6 new tests in `TestModelFormRoutes` class
  - Auth requirement tests for new/edit routes
  - 404 handling for non-existent model edit
  - Context verification for referrable_models
  - Loading state attribute tests
  - `auth_client` fixture with MagicMock dependency override
- feat(models/form): loading state on form submit
  - `.button--loading` class with spinner animation
  - JavaScript form handler disables button on submit
  - Visual feedback prevents double-submission

### Changed
- refactor(models/form): extract inline CSS to stylesheet
  - ~47 inline styles moved to BEM classes
  - `.commission-card`, `.commission-card__*` components
  - `.referrer-picker`, `.referrer-picker__*` components
  - `.referrer-chip` with nested content classes
  - `.referral-terms-panel`, `.referral-term-card__*`
  - Form hint utility classes (--no-margin, --max-width, etc.)
- refactor(models/form): improve accessibility
  - Add `aria-describedby` linking hints to form inputs
  - Crypto wallet and referrer search fields now linked to hints

### Fixed
- No fixes in this release

### Tests
- Test count: 218 (was 212)
- All tests passing

---

## v2.38.0 - 2025-12-24

### Added
- feat(models): rate limiting on `/models/export` endpoint
  - Uses slowapi with 5 requests/minute limit
  - Centralized rate limiter config in `app/core/rate_limiter.py`
  - User-friendly 429 error message when limit exceeded
- feat(models): 18 route integration tests in `test_models_routes.py`
  - Auth requirements, filter URL validation, route structure tests
  - Pagination parameter tests, currency config tests
  - Rate limiting decorator verification
- feat(models): payment history pagination
  - Server-side pagination (20 per page, max 100)
  - Frontend pagination controls with page navigation
  - Total summary calculated across all payouts
- feat(models): focus trap for modal accessibility
  - `createFocusTrap()` utility for keyboard navigation
  - Tab cycling stays within modal when open
  - Returns focus to trigger element on close

### Changed
- refactor(models): extract export modal CSS to stylesheet
  - ~100 lines of inline styles moved to `styles.css`
  - BEM-style classes: `.export-modal`, `.export-modal__*`
  - Responsive breakpoints for mobile layouts
- refactor(models): extract currency constant to config
  - New `app/core/config.py` with `DEFAULT_CURRENCY`, `DEFAULT_LOCALE`
  - Template variables `app_currency`/`app_locale` passed to frontend
  - JS uses template variables instead of hardcoded 'USD'

### Improved
- feat(models): JS error boundaries with toast notifications
  - `showToast()` function for user-friendly error messages
  - `try-catch` wrappers on `toggleModelPayments` and `toggleAllPayments`
- feat(models): loading skeleton for payment history
  - Shimmer animation skeleton rows while fetching `/payments.json`
  - Smooth transition when content loads

### Notes
- All 212 tests passing (209 → 212)
- Models page architecture improvements: 10/10 assessment score

## v2.37.0 - 2025-12-24

### Added
- feat(models): keyboard navigation for expandable model rows
  - Enter/Space keys toggle payment history expansion
  - `tabindex="0"` makes rows focusable
  - `role="button"` for screen reader announcement
- feat(models): ARIA accessibility attributes
  - `aria-expanded` toggles with row state
  - `aria-label` provides descriptive row names
- feat(models): export modal accessibility enhancements
  - `role="dialog"` and `aria-modal="true"`
  - `aria-labelledby` links to modal title

### Changed
- refactor(models): extract ~400 lines of inline CSS to stylesheet
  - `.model-metrics-dashboard` section styles
  - `.filter-toolbar` and `.model-management-table` styles
  - `.model-row` with `:focus` visible outlines
  - `.frequency-badge`, `.status-chip`, `.payment-history-*` styles
  - Responsive breakpoints for mobile layouts

### Notes
- All 194 tests passing
- Models page now follows accessibility best practices

## v2.36.0 - 2025-12-24

### Added
- feat(dashboard): Pending/On Hold status badges in Financial Overview
  - Compact pill-styled badges below sparkline chart
  - Yellow highlight when on-hold count > 0
- feat(dashboard): SVG icons for summary card headers
  - Recent Activity: pulse/activity icon
  - Top Earners: users icon
  - Ad Hoc Payments: document icon

### Changed
- refactor(dashboard): extract ~170 lines of inline CSS to stylesheet
  - Add `dashboard-page` wrapper class for scoped styles
  - Better cacheability with external stylesheet
  - Add `hero-kpi-value--warning` color variant

### Notes
- All 194 tests passing
- Dashboard cleanup: moved mobile responsive styles to styles.css

## v2.35.0 - 2025-12-24

### Added
- feat(dashboard): SVG icons and accent colors on hero KPI cards
  - Calendar, checkmark, dollar, and alert triangle icons
  - Color-coded accent top-borders (blue, green, gray, red)
- feat(dashboard): replace "Unpaid" KPI with "Month Paid" progress
  - Shows paid amount with percentage completion
  - Clearer distinction between cards, eliminates redundancy
- feat(dashboard): skeleton loading states for hero KPIs
  - Shimmer animation placeholders during page load
  - Smooth fade-in transition when content ready
  - Respects `prefers-reduced-motion` (no animation)
- feat(dashboard): payment status donut chart
  - SVG donut showing paid/unpaid ratio in Latest Cycle card
  - Percentage displayed in center
  - Legend with amounts for paid (green) and unpaid (gray)
- feat(dashboard): count-up animation for hero KPI numbers
  - Numbers animate from $0 to final value
  - Ease-out cubic timing for smooth deceleration
  - Currency prefix and proper decimal formatting preserved
- feat(dashboard): 6-month trend sparkline chart
  - Pure SVG sparkline with area fill gradient
  - Current month highlighted with larger dot
  - Monthly labels displayed below chart
  - Data from ScheduleRun historical totals

### Changed
- refactor(dashboard): YTD Paid card uses new `--secondary` variant (neutral gray)
- refactor(dashboard): Financial Overview card shows sparkline instead of pending/on-hold counts
- refactor(crud): `dashboard_summary()` now returns `monthly_trend` array for sparkline

### Notes
- All 194 tests passing
- All 7 dashboard enhancement tasks complete (from B+ assessment)

## v2.34.0 - 2025-12-24

### Added
- feat(ui): redesign sidebar with custom SVG icon system
  - Replace emoji icons with consistent stroke-based SVG icons
  - New PayrollDesk logo (calendar with dots design)
  - Icons: Dashboard, Models, Payroll Hub, Commissions, Changelog, Profile, User Admin, Settings, Logout
- feat(ui): improved sidebar collapse button
  - Move from cut-off edge position to integrated top-right placement
  - Subtle transparent background with border styling
  - Focus-visible accessibility support

### Changed
- refactor(ui): nav-link icon styling updated for SVG support
  - Icon color transitions on hover/active states
  - Active state uses accent blue (#60a5fa)
- refactor(ui): logo container updated for SVG artwork
  - Hover scale effect added
  - Slightly smaller container (48px → 44px)

### Notes
- All 194 tests passing
- Consistent design language across all sidebar icons

## v2.33.2 - 2025-12-24

### Performance
- perf(frontend): CSS minification (115KB → 85KB, 26% savings)
  - Add `styles.min.css` compressed stylesheet
  - Update base.html to use minified version
- perf(frontend): add preload resource hint for critical CSS
- perf(cache): add CacheControlMiddleware for static assets
  - Hashed files: `max-age=31536000, immutable` (1 year)
  - Non-hashed files: `max-age=86400, must-revalidate` (1 day)
- note: gzip compression automatic on Render.com platform

### Documentation
- Update TODO.md with frontend performance completion status
- CSS code splitting deferred (85KB gzipped ~12KB, complexity > benefit)

### Notes
- All 194 tests passing
- Frontend performance section complete (5/6 tasks done, 1 deferred)

## v2.33.1 - 2025-12-24

### Added
- feat(a11y): sidebar accessibility enhancements
  - Add `:focus-visible` to `.nav-link` for keyboard navigation (blue outline)
  - Change sidebar section labels from `<p>` to semantic `<h3>` elements
  - Add opacity transition (0.2s) to collapsed sidebar text elements
- refactor(css): consolidate mobile sidebar breakpoints (768px/480px → single 768px rule)

### Documentation
- Update TODO.md with sidebar enhancement status

### Notes
- All sidebar accessibility improvements complete
- Global `prefers-reduced-motion` already present (line 45)
- Continuing UI/UX polish work

## v2.33.0 - 2025-12-24

### Added
- feat(ui): comprehensive button system with BEM naming convention
  - `.button--primary`, `--secondary`, `--success`, `--danger`, `--warning`, `--info`, `--ghost`, `--tertiary`
  - Active and disabled states for all variants
  - Consistent `:focus-visible` styles for accessibility
- feat(ui): skeleton loader CSS system for async content
  - Shimmer animation with `prefers-reduced-motion` support
  - Variants: text, avatar, card, row, stat, button
- feat(a11y): global focus styles for interactive elements
  - Skip-link for keyboard navigation
  - Focus states for links, inputs, selects, textareas
- feat(a11y): ARIA labels on icon-only action buttons
  - Schedule detail page action buttons
  - Commission action buttons
- docs: add comprehensive UI/UX guide (`docs/UI_UX_GUIDE.md`)
  - Design system documentation (colors, typography, spacing)
  - Component library reference
  - Workflow diagrams for key user journeys
  - Accessibility guidelines

### Changed
- refactor(login): extract inline styles to main stylesheet
  - Updated login page to match app's dark navy theme
  - Consistent form styling with rest of application
- refactor(base): update main content landmark ID for accessibility

### Documentation
- Add TECHNICAL_SPEC.md for system architecture reference
- Add TODO.md housekeeping guidelines to documentation guide
- Update DOCUMENTATION_GUIDE.md with version sync checklist
- Fix changelog dates (2024→2025 corrections)

### Notes
- All 194 tests passing
- UI/UX improvements: 6/8 tasks complete, 2 low-priority pending
- Login page now uses consistent dark theme

## v2.32.2 - 2025-12-24

### Added
- perf(crud): add `eager_load_payouts` parameter to `list_schedule_runs()` for N+1 prevention
- perf(schedules): add in-memory dashboard caching with 5-minute TTL
- perf(models): add composite indexes to payouts table
  - `idx_payout_run_status` (schedule_run_id, status)
  - `idx_payout_run_model` (schedule_run_id, model_id)
  - `ix_payouts_schedule_run_id` (FK index)
  - `ix_payouts_model_id` (FK index)
- feat(database): add configurable PostgreSQL pool settings
  - `DB_POOL_SIZE` (default: 5)
  - `DB_MAX_OVERFLOW` (default: 10)
  - `DB_POOL_RECYCLE` (default: 3600)

### Changed
- perf(crud): optimize `cleanup_empty_runs()` from O(N) to O(1) queries
  - Replace loop with subquery approach
  - Use bulk delete instead of individual deletes
- refactor(schedules): cache invalidation on schedule/payout modifications

### Database
- Migration `f61db652388a`: add payout composite indexes

### Notes
- Dashboard cache auto-invalidates on: schedule creation/deletion, payout updates
- Pool settings logged at startup when using PostgreSQL
- All 194 tests passing

## v2.32.1 - 2025-12-24

### Added
- test: add comprehensive CRUD test coverage (80 tests)
  - `test_crud_models.py` - 20 tests for model filtering/counting
  - `test_crud_payouts.py` - 18 tests for payout/schedule run operations
  - `test_crud_referrals.py` - 15 tests for referral terms/compensation
  - `test_crud_advances.py` - 17 tests for cash advance operations
  - `test_crud_adhoc.py` - 10 tests for adhoc payment operations
- test: add integration tests for critical workflows (14 tests)
  - Model creation workflow
  - Schedule run workflow  
  - Health endpoints workflow
  - Authentication workflow
  - Dashboard workflow
- test: add error scenario tests (20 tests)
  - Validation errors (model, adhoc, advance)
  - API error handling (404s, unauthorized)
  - Edge cases (duplicate detection, invalid months)

### Changed
- docs: update TODO.md with testing progress

### Notes
- Test count increased from 118 → 194 (+76 tests)
- Coverage on crud.py improved from 75% → 86%
- All medium priority testing tasks completed

## v2.32.0 - 2025-12-25

### Added
- feat(database): add connection retry logic with exponential backoff
  - Configurable via `DB_CONNECT_RETRIES` (default: 3) and `DB_RETRY_DELAY` (default: 1.0s)
  - Exponential backoff: 1s → 2s → 4s between retries
  - Logs retry attempts at WARNING level
- test: add 6 tests for connection retry logic

### Notes
- Improves resilience during transient database outages
- Falls back to SQLite in development mode only after all retries exhausted
- Production mode fails loudly after retry exhaustion

## v2.31.0 - 2025-12-25

### Added
- feat(api): add `/health/db` endpoint with database connection test and response time
- feat(database): add query timing/logging (enable with LOG_QUERIES=true env var)
- feat(models): add soft delete support via `deleted_at` column
- feat(crud): add `soft_delete_model()`, `restore_model()`, `list_deleted_models()`, `get_deleted_model()`
- test: add 3 health endpoint tests
- test: add 10 soft delete tests

### Changed
- refactor(crud): `list_models()` and `count_models()` now exclude soft-deleted models by default
- refactor(crud): add `include_deleted` parameter to model listing/counting functions

### Database
- Migration `e50dc541277e`: add `deleted_at` column with index to models table

### Notes
- Soft delete preserves model data while hiding from normal queries
- Use `include_deleted=True` to include soft-deleted models in queries
- Query logging logs slow queries (>100ms) at WARNING level

## v2.30.0 - 2025-12-25

### Added
- feat(crud): add CommissionPayout CRUD operations in `app/crud.py`
  - `get_commission_payout()` - retrieve by ID
  - `list_commission_payouts()` - list with filters (status, date range, model IDs)
  - `count_commission_payouts()` - count with filters
  - `sum_commission_payouts()` - sum amounts with filters
  - `create_commission_payout()` - create new payout
  - `get_or_create_commission_payout()` - idempotent create
  - `update_commission_payout_status()` - update paid/unpaid status
  - `bulk_update_commission_payout_status()` - bulk status updates
  - `delete_commission_payout()` - delete single payout
  - `delete_commission_payouts_by_model()` - delete all payouts for a model
- test: add 15 tests for CommissionPayout CRUD operations

### Changed
- refactor(commissions): use CRUD functions instead of direct queries in router
- fix(conftest): import models before Base to ensure all tables are registered

### Notes
- CommissionPayout model existed but had no dedicated CRUD layer
- Now follows the same patterns as Model, Payout, and AdhocPayment CRUD

## v2.29.0 - 2025-12-24

### Changed
- refactor(database): remove legacy `ensure_schema_updates()` function (180+ lines removed)
- refactor(database): replace print statements with proper Python logging
- perf(database): add PostgreSQL connection pooling (pool_size=5, max_overflow=10)
- refactor(database): extract engine initialization to `_initialize_engine()` function
- cleanup(database): reduce file from 332 lines to ~170 lines

### Removed
- Legacy manual schema migration code - use Alembic instead

### Notes
- Schema migrations are now handled exclusively by Alembic
- The `ensure_schema_updates()` function ran raw SQL on every startup
- All databases already have the required columns from previous runs
- Future schema changes: `alembic revision --autogenerate -m "description"`

## v2.28.0 - 2025-12-24

### Added
- feat(migrations): add Alembic database migration support
- feat(migrations): create initial baseline migration (0001)
- docs: add MIGRATIONS.md with comprehensive migration guide

### Changed
- deps: add alembic>=1.17.0 to requirements.txt
- config(migrations/env.py): configure for PayrollDesk models and dual-DB support

### Notes
- Existing databases should run `alembic stamp 0001` to mark as baseline
- Future schema changes should use `alembic revision --autogenerate`
- See MIGRATIONS.md for full documentation

## v2.27.1 - 2025-12-24

### Fixed
- fix(database): enable SQLite foreign key enforcement in development mode
- Previously, foreign keys were only enforced in tests via conftest.py PRAGMA
- Now `_enable_sqlite_foreign_keys()` ensures FK constraints match PostgreSQL behavior

### Notes
- This fix ensures data integrity in SQLite development mode matches PostgreSQL production
- Without this, orphaned records could be created locally that would fail on production

## v2.27.0 - 2025-12-24

### Added
- feat(schedules): add "Add New Models" button to safely include new models in existing schedule
- feat(services): add `add_new_models_to_run()` method for non-destructive model addition
- docs: add comprehensive DOCUMENTATION_GUIDE.md for project documentation standards

### Fixed
- fix(schedules): remove auto-refresh on schedule view that was causing data loss
- fix(payouts): preserve manual status/notes updates when viewing current month's schedule

### Changed
- ui(schedules/detail): "Add New Models" button added inline with Back and Export buttons
- behavior: viewing schedule page no longer regenerates payouts automatically

### Notes
- The auto-refresh behavior was causing payout data (status, notes) to be lost when viewing the current month's schedule. This has been removed to prevent data loss.
- To add new models to an existing schedule, use the "Add New Models" button which safely adds only models not already in the schedule without affecting existing payouts.

## v2.23.1 - 2025-11-16

### Changed
- ui(models/form): remove the manual commission duration field from the referral picker; duration is now handled automatically.
- ux(models/edit): keep the edit form open after saving so admins can make successive changes without being bounced to the roster list.

## v2.23.0 - 2025-11-16

### Added
- core(commissions): allow each referrer to choose a payout cadence (1st, 14th, or both) and generate schedules/estimates accordingly.
- ui(models): expose commission frequency selector, disable it when payouts are off, and display the schedule on the profile card (which now spans the full row).
- ui(commissions): surface schedule mix in the KPI card, show each referrer's frequency in the detail table, and align stats with the new cadence logic.

### Changed
- infra(nav): fully retire the legacy analytics router/import to eliminate startup import errors.

## v2.22.0 - 2025-11-16

### Added
- ui(commissions): introduce dedicated Commissions dashboard with stat cards, payout timeline, and referral-level schedule table.
- core(commissions): generate referral payout schedules on the 1st and 14th after acceptance to power the dashboard and projections.
- ui(css): add timeline card styles to keep the new schedule grid consistent with existing design language.

### Changed
- ui(models): remove roster pagination so filtered results always show in a single view while keeping aggregate counters accurate.
- nav(sidebar): swap the retired Analytics shortcut for a Commissions link so the new dashboard is a first-class surface.

## v2.19.0 - 2025-11-08

### Added
- feat(payouts): introduce new payout status 'Approved' (distinct from 'Paid' and 'Not Paid') for pre-payment verification workflow
- ui(schedules/detail): add third quick action button to toggle Approved; inline button logic now supports Paid, Approved, On Hold cycles
- ui(schedules/detail): add blue info chip and filter styling for Approved; row background highlight
- importer(excel): normalize 'Approved' and 'Approve' payout status values when importing
- tests: add test_status_approved.py covering status transitions and overdue exclusion logic

### Changed
- core(constants): extend PAYOUT_STATUS_ENUM with 'approved'
- ui(schedules/detail): refactor status chip variant mapping to include info/neutral fallback

### Notes
- Overdue semantics remain limited to 'not_paid' and 'on_hold' to preserve existing escalation logic; 'approved' is treated as non-overdue even if past pay_date.

## v2.14.1 - 2025-11-08

## v2.16.1 - 2025-11-08

- change(overdue UX): dashboard "Review" now links to the current month payroll cycle with overdue filter (`/schedules/{run_id}?show=overdue#payments-overdue`) when available; falls back to consolidated current-month view
- fix(overdue): simplify backend overdue_target_url to a consolidated current-month listing when run-specific link unavailable
- feat(templates): add anchors (`#payments-overdue`, `#payments-on-hold`) for deep links from dashboard alert actions
- test(overdue): coverage for consolidated overdue list across runs and dashboard link to current-month cycle
- chore(version): resolve rebase conflict by advancing version to 2.16.1 (supersedes 2.16.0 & 2.15.2)


- version: align with remote v2.14.0 and include local fixes
- test(env): add per-test domain reset fixture to eliminate cross-test data leakage and stabilize counts
- fix(import): normalize model code lookup (strip + lower) to prevent false 'model not found' errors
- docs(schedules): clarify monthly summary excludes orphan payouts (improves maintainability)

## v2.13.2 - 2025-11-08

- test(env): add per-test domain reset fixture to eliminate cross-test data leakage and stabilize counts
- fix(import): normalize model code lookup (strip + lower) to prevent false 'model not found' errors
- docs(schedules): clarify monthly summary excludes orphan payouts (improves maintainability)

## v2.13.1 - 2025-11-08

- tests(auth): add redirect + next flow coverage (preserve destination; handles 303/307 and absolute Location)
- a11y: add prefers-reduced-motion CSS to respect user accessibility settings
- docs: update changelog entries

## v2.12.1 - 2025-11-08

- fix(types): correct form parameter types (date, Decimal) for model create/update; resolve Pylance diagnostics
- feat(auth): add next parameter support to login redirect (return user to intended destination after auth)
- feat(auth): redirect 401 HTML requests to login with original path preserved

## v2.9.1 - 2025-11-08

- chore(version): align history after remote bump to 2.9.0; set internal version to 2.9.1
- ui(models): refine removal of broad transitions (retain only subtle feedback) and document change

## v2.8.1 - 2025-11-08

- ui(models): remove hover lift and broad transitions on the Models page to eliminate perceived animations; keep subtle feedback only
- chore: bump version to 2.8.1

## v2.7.0 - 2025-11-08

- feature(ui): add `/changelog` route, markdown rendering, and sidebar link to publish release notes in-app
- feature(models): paginate roster table with database-backed counts, page controls, and live aggregates
- ui(models): align filter clear action with select inputs for consistent layout
- build: add `markdown` dependency for rendering documentation
- docs: describe version bump workflow and changelog surface in README

## [2.0.0] - 2025-10-20
### Added
- Stable release: Consolidated exporter to `app.exporting` with a new multi-sheet XLSX exporter.
- UI: Snapshot preview page and improved sidebar navigation.
- Removed legacy export buttons from Schedules and Models pages; export now available from Dashboard (admin only).
## v2.15.0 - 2025-11-08

- Merge branch 'Dev' into staging
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.3.0 - 2025-11-04

- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.4.0 - 2025-11-05

- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.5.0 - 2025-11-06

- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.6.0 - 2025-11-06

- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.8.0 - 2025-11-08

- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.9.0 - 2025-11-08

- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.10.0 - 2025-11-08

- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.11.0 - 2025-11-08

- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.12.0 - 2025-11-08

- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.13.0 - 2025-11-08

- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.14.0 - 2025-11-08

- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.15.0 - 2025-11-08

- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.16.0 - 2025-11-08

- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.17.0 - 2025-11-08

- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.18.0 - 2025-11-08

- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.19.0 - 2025-11-08

- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.20.0 - 2025-11-08

- Merge branch 'staging' of https://github.com/mirabelleagency/PayrollDesk into staging
- Merge branch 'Dev' into staging
- feat(payouts): add Approved status with quick actions and bulk-select; importer normalization; tests; bump version to 2.19.0
- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.21.0 - 2025-11-15

- Merge feature/filtered-export into staging: overdue badge + metrics FOUC fix
- Fix: instant overdue badge update & prevent FOUC in metrics cards
- schedules(detail): remove CSV export, make Excel export mirror current status filter (include overdue mapping)
- schedules(detail): mirror filter chips to dropdown, prevent reload on chip click (keep local filter)
- Merge branch 'staging' of https://github.com/mirabelleagency/PayrollDesk into staging
- Merge branch 'Dev' into staging
- feat(payouts): add Approved status with quick actions and bulk-select; importer normalization; tests; bump version to 2.19.0
- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.24.0 - 2025-11-16

- fix(models): keep edit form open and simplify referral fields
- refactor(commission): per-referral terms + active flag; update UI and view
- Redesign referral/commission UI: split Referral Source & Referred Models, lock commission for referees; add View Model button; show referrer names; fix optional pay_date handling
- Feature: commission  model referral fields, standalone commission service, and profile UI
- UI: center align table rows to match headers (schedule payouts)
- Merge feature/filtered-export into staging: overdue badge + metrics FOUC fix
- Fix: instant overdue badge update & prevent FOUC in metrics cards
- schedules(detail): remove CSV export, make Excel export mirror current status filter (include overdue mapping)
- schedules(detail): mirror filter chips to dropdown, prevent reload on chip click (keep local filter)
- Merge branch 'staging' of https://github.com/mirabelleagency/PayrollDesk into staging
- Merge branch 'Dev' into staging
- feat(payouts): add Approved status with quick actions and bulk-select; importer normalization; tests; bump version to 2.19.0
- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.24.1 - 2025-11-16

- Internal changes
## v2.25.0 - 2025-11-15

- chore(release): resolve merge conflicts, bump to v2.24.1
- fix(models): keep edit form open and simplify referral fields
- refactor(commission): per-referral terms + active flag; update UI and view
- Redesign referral/commission UI: split Referral Source & Referred Models, lock commission for referees; add View Model button; show referrer names; fix optional pay_date handling
- Feature: commission  model referral fields, standalone commission service, and profile UI
- UI: center align table rows to match headers (schedule payouts)
- Merge feature/filtered-export into staging: overdue badge + metrics FOUC fix
- Fix: instant overdue badge update & prevent FOUC in metrics cards
- schedules(detail): remove CSV export, make Excel export mirror current status filter (include overdue mapping)
- schedules(detail): mirror filter chips to dropdown, prevent reload on chip click (keep local filter)
- Merge branch 'staging' of https://github.com/mirabelleagency/PayrollDesk into staging
- Merge branch 'Dev' into staging
- feat(payouts): add Approved status with quick actions and bulk-select; importer normalization; tests; bump version to 2.19.0
- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.26.0 - 2025-11-22

- ui(models): add 'Back to Models' in edit form and show success toast after save; remove pre-save toast; routers(models): redirect with saved flag; ui(schedules): make Select All apply only to visible/filtered rows
- chore(release): resolve merge conflicts, bump to v2.24.1
- fix(models): keep edit form open and simplify referral fields
- refactor(commission): per-referral terms + active flag; update UI and view
- Redesign referral/commission UI: split Referral Source & Referred Models, lock commission for referees; add View Model button; show referrer names; fix optional pay_date handling
- Feature: commission  model referral fields, standalone commission service, and profile UI
- UI: center align table rows to match headers (schedule payouts)
- Merge feature/filtered-export into staging: overdue badge + metrics FOUC fix
- Fix: instant overdue badge update & prevent FOUC in metrics cards
- schedules(detail): remove CSV export, make Excel export mirror current status filter (include overdue mapping)
- schedules(detail): mirror filter chips to dropdown, prevent reload on chip click (keep local filter)
- Merge branch 'staging' of https://github.com/mirabelleagency/PayrollDesk into staging
- Merge branch 'Dev' into staging
- feat(payouts): add Approved status with quick actions and bulk-select; importer normalization; tests; bump version to 2.19.0
- merge: Dev into staging (resolve version & changelog conflicts, set version 2.18.0)
- fix(types): avoid mutating summary dict; pass view model for latest_run to satisfy type checker
- change(overdue): dashboard Review links to current month cycle with overdue filter; bump 2.15.2
- fix(overdue): unify dashboard review link to consolidated current-month listing; add anchors and tests; bump version to 2.15.1
- Merge branch 'Dev' into staging
- chore(version): bump to 2.13.2; fix(import): normalize model code lookup; test(env): add per-test domain reset; docs: clarify orphan payout exclusion
- chore(version): bump to 2.13.1; docs(changelog): add auth redirect tests + a11y motion reduction
- test(auth): add redirect + next flow tests; a11y: add prefers-reduced-motion CSS; docs: update changelog
- chore(version): bump to 2.12.1; docs(changelog): record auth redirect next param and type fixes
- fix(types): use date & Decimal in model create/update forms; explicit description=None for AdhocPaymentUpdate
- feat(auth): preserve intended destination with next param on login redirect
- feat(auth): redirect 401 HTML requests to /login instead of JSON Not authenticated
- chore(version): bump to 2.9.1 align commit history and refine models page transitions
- chore(version): bump to 2.7.1 and remove models page animations
- merge: resolve conflicts in excel_importer (date parsing & adhoc code normalization)
- feat(models): add server-side pagination + DB aggregates for roster page; feat(ui): in-app changelog page and sidebar link; chore: bump version to v2.7.0; docs: update README; build: add markdown dep
- schedules/detail: make status chips filter client-side (no reload) and intercept bulk update for in-place changes; schedules: add bulk JSON endpoint
- schedules/detail: make quick actions in-place (no full reload) via JSON endpoint; schedules: add /status API for payout updates; admin/diagnostics: redact details in production; docs: add Render Postgres setup section
- schedules: add Current Month quickfilter + green button; admin: add DB diagnostics endpoint for DB backend check (password-masked); ci: tweak auto-versioning.yml 'on' key formatting
- importer: normalize model code lookups with strip().lower() to fix Postgres mismatch causing most payouts to be skipped; add test for multiple payouts import
- tests: remove duplicate test_admin_reset_data.py from repo root; keep under tests/
- admin: add secondary confirmation ('RESET') for database reset; validate server-side and disable submit until matched; show error message on mismatch
- ci: add auto version bump and changelog workflow; script to bump __version__ and append commits to CHANGELOG
- Database: prevent accidental SQLite fallback in prod by defaulting ENVIRONMENT=production and requiring LOCAL_DEV_SQLITE_FALLBACK for dev fallback; add startup logging
- Template: add second Adhoc sample row with status=paid; update samples script to ensure both pending and paid examples
- Import template: add Adhoc sheet with status dropdown and example row; extend validation and sample scripts to manage Adhoc
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- Importer: support optional 'Adhoc' sheet for AdhocPayment import; add status normalization and summary fields; type-check fixes for row numbering
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- UI: keep schedule payouts header titles inline and set column widths to avoid wrapping on /schedules/:id
- Merge remote-tracking branch 'origin/Dev' into staging
- Import template: add weekly sample row (Models) and on_hold sample row (Payouts); include idempotent script to maintain samples
- feat(template): add dropdowns to import template (Models payment_frequency; Payouts status) including all allowed types; add maintenance script to update validations
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): hide Cycle ID and Created columns in Payroll Hub cycles table
- feat(ui): show app version across pages; centralize version in app.__init__; expose APP_VERSION to Jinja templates; use version in FastAPI metadata
- feat(dev): fallback to SQLite when DB unreachable in development; improve Excel import to handle empty Payouts and invalid pay dates non-fatally; fix nullable types for crypto_wallet and notes
- chore(vscode): add Run Uvicorn Server task (PowerShell .venv activation + uvicorn)
- ui(models/form): update compensation adjustments to match system theme - use form-row pattern with proper labels and dark glassmorphic styling; add card background, improve spacing and alignment
- export(xlsx): remove AdvanceAllocations sheet; drop internal IDs and use model code across sheets (no model_id, no payout_id/schedule_run_id); tidy Advances/AdvanceRepayments columns
- export(xlsx): include cash advances in dashboard Excel  add Advances, AdvanceRepayments, and AdvanceAllocations sheets
- ui: add Deductions column to schedule and restyle models view (advances/ad-hoc payments)  move tables into cards, color buttons, inline repayment controls, remove emojis
- ui: preserve scroll position across form submissions and link navigations (restore on same-path load)
- export: include cash advance impacts in Pay_Schedule Excel (gross, advances deducted, net, status); keep CSV download for schedules as DB net amounts
- feat(advances): cash advance requests, approval, auto-deduction with safeguards; allocations apply on schedule and convert to repayments on payment; model page UI for advances
- admin(settings): remove purge preview & orphan-cleanup button; simplify settings route
- admin: add hard purge for models with dry-run preview; CRUD helpers and tests
- dashboard: recent activity totals recomputed from linked paid payouts to avoid residuals
- dashboard: zero out residuals when models are deleted; filter metrics to payouts with model_id; show YTD paid instead of run rate
- schedules/all-table: fix year selector by passing available_years and auto-submit on change
- schedules: persist filters after quick status/note updates (redirect_to)
- ui(dashboard/models): include pending ad hoc in Requires Attention badge; highlight current month unpaid as warning; replace broken models metric icons with inline SVGs
- fix(analytics): prevent Safari mobile overflow for date range inputs (min-width:0, flex, -webkit-appearance)
- ui(dashboard): change pending adhoc payment card to yellow/amber alert
- ui(sidebar): fix User Admin icon with accessible SVG
- ui(schedules): remove checkboxes and adjust table columns for single-run view
- ui(schedules): remove Code filter from payout schedule
- ui: preserve dashboard export button label after export
- UI: dashboard KPI label -> '<Month> Total to pay' (dynamic)
- UI: center-align hero stat cards (Total Payout, Outstanding, Paid, Ad Hoc) on Payroll Hub for mobile
- JS: add defensive guards to schedules/detail.html to avoid DOM null errors
- UI: center-align model metric cards (Total Roster, Payment Methods, Payment Frequency, Lifetime Paid) for mobile view on /models/ page
- UI: center-align all dashboard elements including hero KPI cards and trend text for mobile view
- UI: finalize mobile dashboard spacing fixes and center alignment
- UI: fix filter section gap and add horizontal table scrolling on model payments page for mobile
- UI: make admin users page mobile responsive with horizontal scroll and stacked action buttons
- UI: fix filter overflow, enable horizontal table scroll, and center-align Status column on schedule detail page
- UI: make action buttons (Open/Delete) uniform size in schedules table on mobile
- UI: make All Payroll Cycles table responsive for mobile with horizontal scroll and improve Export to Excel button styling
- UI: make Model Registry & Payment History table responsive for mobile view with horizontal scroll and compact layout
- UI: fix filter card vertical gap by adjusting responsive breakpoint from 1024px to 768px
- UI: make Import Excel, Snapshot, Register Model, and Export to Excel buttons same size in mobile view
- UI: make 'Not Paid' status chip yellow (warning style) in Payment History
- UI: center Status column in Payment History and add colored status chips (paid/on hold/not paid)
- UI: remove 'Last Payment' column from Model Registry table; adjust colspan and JS accordingly
- UI: move 'Lifetime Paid' card to end of metrics (after Payment Frequency) on /models
- UI: fix Snapshot button icon on /models (replace garbled glyph with )
- UI: inline quick search with filter selects on /models and make search flex-grow; keep responsive wrapping
- UI: center-align Frequency column in Model Registry table
- UI: fix biweekly frequency badge styling in Model Registry table (support .frequency-badge--biweekly)
- Models: payment methods card shows selected method count and per-method breakdown counts (mirrors frequency card)
- Models: show counts by payment frequency in dashboard card (value reflects selected frequency; breakdown shows per-frequency counts)
- tools: add debug script to inspect exported Payouts columns (dev only)
- Import template: remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Export (xlsx): remove Payment Frequency from Payouts sheet (redundant; present on Models)
- Importer: update-or-create payouts by code+pay_date; add regression test; UI: overdue card pulse CSS
- schedules: add blue info button style for Open action
- schedules: match Open button style to Delete button (secondary compact)
- dashboard: rename Special Payments card to Ad Hoc Payments
- dashboard: rename Top Contributors card to Top Earners
- schedules: wire Compliance card to on-hold/detail filter and render compliance list; adjust templates
- ui(schedules): compact single-line filters for All Payroll Cycles
- ui(schedules): Pending Approvals card, badge variants, and Salary Payments rename
- UI: center brand and icons in collapsed sidebar; tweak toggle placement
- UI: sidebar polish (collapsible + gradients) and standardize export buttons styling/text/icon across app
- Tests: use temporary SQLite DB per session (isolated PAYROLL_DATABASE_URL), remove drop_all and clean up temp dir
- Feature: prorate first-month payouts based on start_date; add test
- Feature: default Payroll Hub cycles filter to current month; keep clear action
- Refactor: replace 'run(s)' with 'cycle(s)' and make schedules export respect year/range filters
- Initial commit

## v2.39.0 - 2025-12-24

- feat(models/form): improve form to 10/10 score
- chore(release): v2.38.0 - Models architecture improvements
- docs: update TODO.md with pagination and currency config completion
- feat(models): add payment pagination and currency config
- docs: update TODO.md with completed architecture improvements
- feat(models): add rate limiting, tests, accessibility improvements
- docs(todo): add Models page assessment gaps to backlog
- chore(todo): housekeeping - consolidate achievements, prune obsolete tasks
- docs(release): v2.37.0 - Models page CSS extraction and accessibility
- docs: bump version to v2.36.0, update CHANGELOG and TODO
- feat(dashboard): add SVG icons to summary card headers
- feat(dashboard): add Pending/On Hold status badges
- refactor(dashboard): extract inline CSS to styles.css
- chore(todo): housekeeping - archive UI/UX section, consolidate notes
- docs: bump version to v2.35.0, update CHANGELOG and TECHNICAL_SPEC
- feat(dashboard): add monthly trend sparkline
- feat(dashboard): add count-up animation to hero KPIs
- feat(dashboard): add payment status donut chart
- feat(dashboard): add skeleton loaders to hero KPIs
- refactor(dashboard): replace Unpaid KPI with Month Paid progress
- feat(dashboard): add SVG icons and accent colors to hero KPIs
- fix(ui): prevent collapse button overlap with logo
- docs: version 2.34.0 - sidebar SVG icon redesign
- feat(ui): redesign sidebar icons and collapse button
- docs(guide): add single-commit note to execute workflow
- docs(todo): archive frontend performance section
- docs: version 2.33.2 - frontend performance improvements
- perf(cache): add cache-control headers for static assets
- perf(frontend): add CSS minification and preload hints
- docs(todo): add frontend performance improvement backlog
- docs: add 'remove fully-completed sections' to housekeeping checklist
- chore(docs): TODO.md housekeeping - archive completed sidebar section
- chore(release): v2.33.1 - sidebar accessibility
- feat(a11y): sidebar accessibility enhancements
- docs: add 'Execute Documentation Guide' workflow section
- docs(TODO): housekeeping - archive completed tasks, fix dates
- chore(release): v2.33.0 - UI/UX improvements and accessibility
- docs: add TODO.md housekeeping guidelines to documentation guide
- docs(TODO): update UI/UX task status to reflect completions
- feat(ui): add skeleton loaders and ARIA accessibility improvements
- feat(ui): standardize button system and improve accessibility
- docs(TODO): add UI/UX improvement tasks from assessment
- docs: add comprehensive UI/UX guide
- docs: fix changelog dates (2024->2025) and add sync guidance to documentation guide
- docs: add TECHNICAL_SPEC.md maintenance guidance to documentation guide
- docs: add comprehensive technical specification
- chore(release): v2.32.2 - performance optimizations
- docs(TODO): housekeeping - consolidate completed tasks
- perf: add medium priority performance optimizations
- perf: optimize cleanup_empty_runs and add dashboard caching
- docs(TODO): add performance optimization tasks from assessment
- docs(TODO): perform housekeeping - archive completed tasks
- docs(TODO): add usage guide and housekeeping instructions
- refactor(database): add type hints and improve logging
- chore(release): v2.32.1 - test coverage improvements
- test: add error scenario tests (20 tests)
- docs: update TODO - 86% coverage achieved
- test: improve crud.py coverage to 86% (160 tests)
- docs: add medium priority testing tasks to TODO.md
- docs: update TODO.md - all high priority backlog items complete
- test: improve crud.py test coverage from 70% to 75%
- feat(database): add connection retry logic with exponential backoff
- docs: update TODO.md with backlog completion status
- feat: add health check, query logging, and soft delete (v2.31.0)
- docs: update TODO.md with completed CommissionPayout CRUD tasks
- feat(crud): add CommissionPayout CRUD operations with 15 tests
- chore: update TODO.md with completed tasks and bump version to 2.29.0
- refactor(database): remove legacy schema migrations, add proper logging
- docs: add database.py refactor task checklist to TODO.md
- docs: add lean QUICK_ASSESSMENT.md guide for ad-hoc assessments
- chore: create docs/ folder and further cleanup
- chore: project directory cleanup and reorganization
- feat(migrations): add Alembic database migration support
- fix(database): enable SQLite foreign key enforcement in dev mode
- feat: add safe 'Add New Models' button to schedule view
- fix: remove auto-refresh on schedule view to prevent data loss
- ui(models): add 'Back to Models' in edit form and show success toast after save; remove pre-save toast; routers(models): redirect with saved flag; ui(schedules): make Select All apply only to visible/filtered rows
- chore(release): resolve merge conflicts, bump to v2.24.1

