# Agents

Custom agents and skills are defined in the `.claude/` directory. Read those files for full instructions when invoking these workflows.

## plan-reviewer

**Definition:** [`.claude/agents/plan-reviewer.md`](.claude/agents/plan-reviewer.md)

Senior engineer agent that reviews implementation plans against the actual codebase. Produces structured feedback ranked by priority (HIGH / MED / LOW).

## review-plan

**Definition:** [`.claude/skills/review-plan/SKILL.md`](.claude/skills/review-plan/SKILL.md)

Orchestration skill that iteratively spawns `plan-reviewer`, auto-applies HIGH/MED feedback, and asks the user about LOW items.
