# Copilot Audit & Command Protocol

This file contains the detailed Module Audit Protocol and Command System for structured codebase analysis.
Read this file when `/audit`, `/plan`, `/implement`, `/verify`, `/debug`, `/refactor`, or `/document` commands are used.

---

## Module Audit Protocol

When asked to audit any module (`/audit [module]`), follow this structure exactly.

### Required Outputs

#### 1. Implementation Report

List ALL features related to the module.

For each feature include:

- Feature name
- Status: Implemented | Partial | UI only | Backend only | Not implemented
- Description of actual behavior
- Code references: file names, functions/classes, components

#### 2. Architecture Report

Include:

- **Data Model** — Entities, fields, relationships, constraints
- **Lifecycle / State Behavior** — State transitions, what actually happens in code
- **API / Services / Jobs** — Endpoints, service methods, background jobs
- **UI Components** — Pages, components, interactive vs static
- **Dependencies / Integrations** — External services, shared modules

#### 3. Gap Analysis

Provide a table:

| Feature | Current State | Expected Behavior | Gap | Priority |
|---------|---------------|-------------------|-----|----------|

Be explicit and concrete.

#### 4. Status Document

Create or update: `docs/status/[module-name]-status.md`

Use this template:

```markdown
# [Module Name] Status

## Current State
### Implemented
### Partial
### UI Only
### Backend Only
### Not Implemented

## Data Model
## Lifecycle / State Behavior
## API / Services / Jobs
## UI Components
## Dependencies / Integrations
## Known Issues

## Next Priority Tasks
1.
2.
3.
```

### Simulation Requirement

Simulate the main end-to-end flow of the module. For each step:

- Describe what actually happens
- Identify what works
- Identify what is missing or broken

Do NOT assume behavior.

### Code Verification Rules

For every claim:

- Include code references
- If no reference exists → mark as NOT IMPLEMENTED

Never:

- Infer backend from UI
- Infer UI from schema
- Assume logic exists because fields exist

### Codebase Coverage

When analyzing a module, also inspect: shared models, services, state management, validators, permissions, background jobs, integration hooks. Do NOT limit analysis to files with the module name.

---

## Command System

Each command has a defined behavior. When a command is used, follow it strictly. Execute ONE command at a time. If unclear, ask for clarification.

### /audit [module]

Analyze the current state of a module based on actual code.

1. Inspect codebase for all module-related logic
2. Generate: Implementation report, Architecture report, Gap analysis, Status document
3. Include code references for every claim
4. Mark anything unverified as NOT IMPLEMENTED

### /plan [feature or module]

Design an implementation approach before coding. Do NOT implement yet.

1. Analyze current implementation
2. Identify gaps
3. Propose: approach, files to modify, data model changes, API changes, UI changes, risks

### /implement [task]

Implement a clearly defined, scoped change.

1. Confirm scope of task
2. Identify affected files
3. Implement ONLY what is requested — avoid unrelated changes
4. After implementation: list all changed files, explain what was done, highlight limitations

### /verify [module or feature]

Validate actual system behavior. Do NOT assume success.

1. Simulate real user flow
2. Identify: what works, what fails, edge cases
3. Confirm consistency across: UI, backend, data

### /debug [issue]

Identify root cause of a problem.

1. Reproduce or simulate issue
2. Identify failure point: UI, backend, data, integration
3. Provide: root cause, exact location (file + function), fix plan

### /refactor [module or code]

Improve structure without changing behavior.

1. Analyze current structure
2. Identify: duplication, inconsistencies, complexity
3. Propose improvements
4. Implement only after validation

### /document [module|organize]

Update system documentation to reflect current implementation,
or organize the docs directory.

**Always (both modes):**

1. Maintain `docs/DOCUMENT-INDEX.md` — every doc must be listed
2. Maintain crosslinks — every doc must have a `Related:` header
   linking to related docs
3. Fix any broken references found during the update
4. Do NOT invent features — only document what exists in code

**When a module is specified** (`/document image`,
`/document turn-flow`, etc.):

1. Search all docs for content about the module (grep for
   keywords, check DOCUMENT-INDEX.md)
2. Update each doc that covers the module: architecture,
   status, API reference, schema docs, usage notes
3. Ensure consistency — same facts in all docs that mention
   the module
4. If a status doc exists in `docs/status/`, update it
5. If no status doc exists and the module is complex enough,
   create one using the status template

**When "organize" is specified** (or no module given):

1. Scan docs/ for content overlap — flag docs with >50%
   shared content
2. Merge overlapping docs (keep the more complete version,
   redirect the other)
3. Archive obsolete docs to `docs/archive/` with a note at
   the top pointing to the replacement or explaining why
4. Verify DOCUMENT-INDEX.md is complete and accurate
5. Remove dead crosslinks, fix broken references
6. Ensure consistent frontmatter (`Related:` links at top)
7. Report: what was merged, archived, or reorganized

### /release

Prepare code for a release commit.

1. **Determine version bump** — Scan commits since last
   release: `feat:` → MINOR, `fix:` → PATCH, breaking
   changes → MAJOR (semver)
2. **Bump version** — Update version in all package/config
   files (discover with `file_search **/*package.json` or
   equivalent manifest files for the project's language)
3. **Update changelog** — Add entry to changelog with new
   features, bug fixes, breaking changes (create changelog
   if none exists)
4. **Update documentation** — Update any docs affected by
   the changes. Run `/document organize` checks (crosslinks,
   index, broken references)
5. **Add code documentation** — Add/update doc comments on
   new or modified exported symbols (JSDoc, docstrings, etc.
   per language)
6. **Verify build** — Ensure the project compiles/builds
   without errors
7. **Commit** — Use conventional commit format:
   `release: vX.Y.Z`
8. **Push** — Push the release commit to the configured
   remote. If tags are part of the release flow, push the
   release tag as well after the commit succeeds