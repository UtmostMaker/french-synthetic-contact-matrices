# Task System

## Status labels
- backlog
- active
- blocked
- done
- dropped

## Priority labels
- P0 critical
- P1 high
- P2 normal
- P3 low

## Operating rule
Every meaningful task should have:
- a clear owner,
- a concrete output,
- a dependency note if relevant,
- and a definition of done.

## Active task board
| ID | Status | Priority | Task | Output | Dependencies |
|---|---|---|---|---|---|
| T0001 | done | P0 | Bootstrap repository structure | Initial framework files | None |
| T0002 | active | P0 | Start broad literature mapping | Source index + annotated notes | T0001 |
| T0003 | done | P1 | Build candidate idea backlog | Scored idea list | T0002 |
| T0004 | done | P1 | Select main and backup idea | Decision entry | T0003 |
| T0005 | active | P1 | Formalize ROIA experiment plan and implementation scaffold | Method note + metric sheet + baseline skeleton | T0004 |
| T0006 | done | P2 | Document research framework and agent orchestration | Operations note | T0001 |
