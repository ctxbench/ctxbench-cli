# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12
**Primary Dependencies**: The primary dependencies are in pyproject.toml and flake.nix
**Storage**: N/A
**Testing**: pytest 
**Target Platform**: Linux Server
**Project Type**: cli  
**Performance Goals**: NEEDS CLARIFICATION  
**Constraints**: NEEDS CLARIFICATION  
**Scale/Scope**: NEEDS CLARIFICATION

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The plan MUST either satisfy each gate or document the violation in Complexity Tracking with
rationale, scope, and mitigation.

- [ ] Lifecycle phases remain explicit and separated.
- [ ] Answer-generation and evaluation costs are not conflated.
- [ ] New or changed metrics define value, unit, lifecycle phase, and provenance.
- [ ] Metric provenance distinguishes reported, measured, derived, estimated, and unavailable values.
- [ ] Estimated metrics are not presented as reported or measured values.
- [ ] Unavailable metrics are represented as unavailable/null, not as zero.
- [ ] Metric comparisons do not mix provenance categories without explicit labeling.
- [ ] New metric metadata is minimal and justified by current research needs.
- [ ] Canonical and derived artifacts are identified when artifacts are created or changed.
- [ ] Artifact/schema changes are documented as compatible, breaking, transitional, or experimental.
- [ ] Strategy comparability is preserved, or intentional asymmetries are documented.
- [ ] Dataset/domain-specific behavior remains isolated from generic benchmark components.
- [ ] Provider-specific behavior remains isolated from strategy orchestration.
- [ ] Architectural boundaries and dependency direction are preserved; cycles require documented migration exceptions.
- [ ] Provider-backed execution is not required for validation unless explicitly approved.
- [ ] Documentation impact is identified, especially for CLI, artifacts, metrics, datasets, and reproducibility.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
