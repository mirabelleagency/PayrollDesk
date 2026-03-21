# Collaboration Log

Tracks decisions, document changes, and current project phase.

## Current Phase

**Maintenance & Polish** — v2.51.1

## Documents

| File | Purpose |
|------|---------|
| `README.md` | Project overview, setup, docs index |
| `CHANGELOG.md` | Release notes by version |
| `COLLABORATION_LOG.md` | This file — decisions and progress |
| `docs/SYSTEM_OVERVIEW.md` | Architecture and system design |
| `docs/TECHNICAL_SPEC.md` | Technical specification |
| `docs/UI_UX_GUIDE.md` | UI/UX guidelines |
| `docs/ALEMBIC_GUIDE.md` | Alembic migration guide |
| `docs/MIGRATION_GUIDE.md` | Data migration procedures |
| `docs/ASSESSMENT_GUIDE.md` | Assessment procedures |
| `docs/DOCUMENTATION_GUIDE.md` | Documentation standards |
| `docs/DUPLICATE_HANDLING.md` | Duplicate detection logic |
| `docs/SCHEDULE_REVAMP.md` | Schedule redesign plan |
| `docs/ENHANCEMENTS.md` | Feature enhancement plans |
| `docs/ISSUES.md` | Known issues & tech debt |
| `docs/TODO.md` | Task tracking |
| `docs/DESIGN_AUDIT.md` | Design language audit |

## Decision Log

### 2026-03-22

- **Icon color system**: Added semantic icon coloring
  in `app/static/css/styles.css` so SVG icons inherit
  contextual colors by location instead of staying
  monochrome.
- **Design audit updated**: `docs/DESIGN_AUDIT.md`
  now documents the completed icon rollout and the
  semantic color behavior.

- **Icon rollout completed**: Replaced remaining emoji-based UI
  markers across all templates in `app/templates/`.
  Schedules, models, admin, profile, dashboard, and
  commissions now use the shared Lucide SVG helper.
- **Interactive icon consistency**: Updated JS-driven
  quick-action states in schedule detail and combined
  payouts so buttons keep SVG icons after status changes.

- **Icon system**: Replaced ~100 emoji instances across
  18 templates with Lucide SVG icon system (`app/icons.py`).
  CSS icon classes added. Initial batch: 5 templates converted
  (login, changelog, audit_log, pending_advances, purge_confirm).
- **Iconography audit**: Added to `docs/DESIGN_AUDIT.md` —
  inventoried all emoji usage, replacement plan, rollout strategy.

### 2026-03-22 (earlier)

- **Doc audit**: README now links to all 13 docs in `docs/`
- **Mobile audit**: Raised hamburger breakpoint 480→768px,
  added global table scroll wrappers, touch-target sizing
- **ISSUES.md**: Updated audit version from 2.44.0 → 2.48.1
- **COLLABORATION_LOG.md**: Created (was missing per project
  conventions)
