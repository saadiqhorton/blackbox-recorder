Unified GSD + Superpowers + GStack Workflow

The Three Frameworks

GSD (Get Shit Done) — Context Manager

• Purpose: Phase-based execution that prevents context rot
• Key Files: .planning/ directory with STATE.md, ROADMAP.md, REQUIREMENTS.md
• Phase Command: /gsd-discuss-phase, /gsd-plan-phase [N], /gsd-execute-phase [N]

Superpowers — Execution Framework

• Purpose: Test-driven development with mandatory skill workflows
• Skills: brainstorming → writing-plans → subagent-driven-development → test-driven-development → code-review → finishing-branch
• Auto-triggers: Skills activate automatically before any code task

GStack — Decision Framework

• Purpose: Role-based decisions when AI hits ambiguity
• Roles: /plan-ceo-review, /plan-eng-review, /plan-design-review, /review, /ship, /browse, /qa, /cso
• Activates: When design/architecture decisions are needed

The Integration

1. GStack for clarification and spec (the "what are we building?")
  • Use GStack roles to refine product intent
  • Output: SPEC.md with clear requirements
2. GSD for phase splitting (the "how do we slice it?")
  • GSD breaks SPEC into phases under 50% context each
  • Creates phase prompt files in .planning/phases/
  • Manages state across phases
3. Superpowers for execution (the "how do we build it?")
  • TDD-first: write tests before code
  • Subagent-driven-development for parallel task execution
  • Code review and verification before marking phase complete

Phase Workflow

Each phase follows this pattern:

1. GStack roles for any design decisions needed in this phase
2. GSD executes the phase with fresh context
3. Superpowers TDD skill enforces test-first within the phase
4. Superpowers code-review skill verifies before phase close
5. Update STATE.json, advance to next phase

Key Principles

• GSD ensures no single session exceeds 50% context
• GStack roles handle decision paralysis (AI asks virtual team)
• Superpowers enforces test-first and mandatory skill workflows
• All three together: reliable large-project execution
