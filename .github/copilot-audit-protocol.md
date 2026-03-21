# Copilot Audit & Command Protocol

This file contains the detailed Module Audit Protocol and Command System for structured codebase analysis.
Read this file when `/audit`, `/plan`, `/implement`, `/verify`, `/debug`, `/refactor`, `/document`, `/test`, or `/release` commands are used.

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
2. Generate: Implementation report, Architecture report,
   Gap analysis, Status document
3. Include code references for every claim
4. Mark anything unverified as NOT IMPLEMENTED

#### /audit (no module — full project)

When `/audit` is run without a module name, perform a
project-wide consistency check:

1. **File inventory** — List every file in the project
   with its purpose and current state
2. **Tech stack consistency** — Verify the tech stack
   matches across all docs (README, planning, copilot
   instructions, backend architecture, etc.)
3. **Cross-reference check** — Look for references to
   files, structures, or concepts that don’t exist
4. **Document completeness** — Flag any incomplete
   sections, placeholder content, or contradictions
5. **Crosslink verification** — Run the crosslink
   check from `/document` Crosslink Rules
6. **Status doc accuracy** — Verify status tracking
   docs match actual project state
7. **Report** — Present findings as CLEAN or list
   issues with specific file references

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

### /test [module or feature]

Write or run tests for a module or feature.

1. Identify testable logic (state mutations, service
   functions, prompt construction, data validation)
2. Check for existing tests — avoid duplicates
3. Write tests using project test framework (Jest)
4. Run tests and report results:
   - Passed / Failed / Skipped counts
   - Failure details with file + line references
5. If tests fail due to bugs (not test errors), flag
   for `/debug`

#### /test (no args — full suite)

Run all existing tests and report summary.

### /refactor [module or code]

Improve structure without changing behavior.

1. Analyze current structure
2. Identify: duplication, inconsistencies, complexity
3. Propose improvements
4. Implement only after validation

### /document [module]

Update system documentation to reflect current
implementation. Do NOT invent features — only document
what actually exists in code.

#### Documentation Checklist

1. **Identify what changed** — List all files modified
   since docs were last updated
2. **Update relevant docs** — For each file in `docs/`,
   check if the changes overlap with that doc's topic.
   Update any doc whose subject matter was affected.
3. **Update status tracking** — Update all files in
   `docs/status/` that are affected by the changes.
   Move items between Implemented/Not Implemented,
   mark resolved gaps, add new gaps if found.
4. **Update COLLABORATION_LOG.md** — Add decisions
   made, documents changed, update current phase
5. **Update README.md** — If new docs were created
   or project status changed
6. **Cross-link verification** — Run the crosslink
   check (see Crosslink Rules below)

#### Crosslink Rules

Every document must link to related docs. After any
documentation change, verify:

- `README.md` links to every doc in `docs/`
- `COLLABORATION_LOG.md` lists every doc by filename
- Each doc in `docs/` links to any other doc it
  references or depends on (e.g., schema ↔ backend,
  plan ↔ design docs, technical ↔ architecture)
- Status docs in `docs/status/` link to their source
  design docs
- No doc references a file that doesn't exist

If a new doc is created:

1. Add link in `README.md` under Docs section
2. Add filename in `COLLABORATION_LOG.md`
3. Add crosslinks from/to related existing docs

### /release

Prepare code for release commit with full documentation.

1. Add/update `@fileoverview` headers for new or
   modified files
2. Add JSDoc comments to all exported functions,
   hooks, interfaces, and types in modified files
   that lack JSDoc
3. Update `docs/changelog.md` with new features, bug
   fixes, breaking changes
4. Bump version in root `package.json`
5. Update displayed version in UI
   (`src/app/index.tsx` version tag)
6. Run `/document` checklist (including crosslinks)
7. Run pre-commit checklist:
   - TypeScript compiles without errors
   - All crosslinks are valid
   - No stale references in any doc
   - COLLABORATION_LOG.md is current
8. Commit with conventional format:
   `feat: <summary> (v0.X.0)` with body listing
   key changes
9. Push to remote
