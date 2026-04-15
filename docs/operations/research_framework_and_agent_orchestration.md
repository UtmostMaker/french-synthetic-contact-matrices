# Research Framework and Agent Orchestration

## Purpose of this document
This document explains how the study is organized, how agentic work is orchestrated, and how transparency is maintained during the project.

It is meant to support:
- scientific traceability,
- reproducibility,
- internal auditability,
- and later methodological transparency in the paper or repository.

It does **not** force full public disclosure of every exploratory prompt or every discarded branch. The goal is transparent scientific process, not self-sabotage.

## Project philosophy
The study is run as a structured research program, not as ad hoc chat output.

Core principles:
- local-first work,
- explicit logs and registries,
- bounded use of agents,
- reproducible experiments,
- modest claims,
- ROIA-first framing,
- optional agentic simulation only after strong non-agentic baselines exist.

## Separation of layers

### 1. Research framework layer
This is the durable backbone of the project.

It includes:
- project status,
- task system,
- decision log,
- hypothesis log,
- risk register,
- failure log,
- literature map,
- dataset registry,
- baseline registry,
- experiment registry,
- manuscript workspace,
- artifact conventions.

This layer should survive session resets, interruptions, and model changes.

### 2. Scientific method layer
This contains:
- research question,
- baselines,
- evaluation metrics,
- validation strategy,
- ablations,
- robustness checks,
- limitations.

Current anchor document:
- `docs/methods/roia_experiment_plan.md`

### 3. Agent orchestration layer
This layer is optional and instrumental.

Agents are used to accelerate bounded tasks such as:
- literature structuring,
- idea ranking,
- drafting internal notes,
- implementation support,
- review and consistency checks.

Agents are **not** treated as autonomous scientific authorities.
They do not define the truth of the project. They assist the workflow.

## Transparency policy
The user requested transparent operation.

For this study, transparency means:
- always state whether active work is happening or whether input is needed,
- explicitly say when a background agent is launched,
- state what that agent is working on,
- state when it has finished,
- log meaningful pivots and decisions,
- keep the project state in files rather than only in chat memory.

Transparency does **not** mean:
- publishing every internal scratch note,
- exposing sensitive operational details unnecessarily,
- or giving away scientific credit.

## Authorship and credit
The human remains the scientific owner and decision-maker.
The assistant contributes to:
- structuring the research program,
- finding and comparing sources,
- drafting methodology,
- implementing experiments,
- organizing documentation,
- and preparing publication assets.

If the work becomes publishable, authorship and acknowledgments must be decided explicitly by the human before submission.

## Agent usage policy for this project

### Default mode
Default mode is direct work in the main session.
Use no background agents unless there is a clear bounded task.

### When to use a background agent
Use a background agent only if all are true:
- the task is clearly scoped,
- the output can be verified,
- the task is not externally destructive,
- the task benefits from isolated focus.

Examples:
- ranking candidate paper ideas,
- extracting a literature shortlist,
- drafting a methodological comparison note,
- reviewing a code patch for consistency.

### When not to use a background agent
Do not use a background agent for:
- vague strategic drift,
- irreversible actions,
- public submissions,
- expensive uncontrolled agent loops,
- anything requiring silent hidden autonomy.

## Current orchestration model

### Main session
Role:
- control tower,
- user communication,
- project state management,
- final decision integration.

Responsibilities:
- maintain transparency,
- update logs and memory,
- approve or reject subagent outputs,
- keep the scientific line coherent.

### Subagents
Role:
- bounded workers for a narrow subtask.

Requirements:
- one main objective per run,
- no depth explosion,
- no implicit public actions,
- outputs must be checkable and written back into project files.

## Current practical workflow
1. Define or refine the scientific objective.
2. Write or update the relevant project file.
3. If needed, launch one bounded subagent.
4. Review and integrate the result.
5. Log the decision or state change.
6. Move to the next concrete artifact.

## Experimentation policy
The paper must not depend on agentic novelty alone.

Required order:
1. transparent non-agentic baseline,
2. stronger structured baseline,
3. uncertainty or robustness layer,
4. only then bounded agentic extension if justified.

This prevents a flashy but weak paper.

## External orchestration references used for this study
The orchestration policy is informed by official project documentation, not by ad hoc intuition.

### CAMEL
CAMEL documents a modular multi-agent stack with agents, societies, memory, interpreters, models, and a `Workforce` coordinator abstraction for bounded collaboration.
For this project, the key lesson is: use a coordinator with clearly scoped workers, not an open-ended society.

### OASIS
OASIS is documented by CAMEL as a large-scale social simulation environment for platforms like Twitter or Reddit, with many possible actions and scalable agent interaction.
For this project, the key lesson is: OASIS is relevant only as a bounded social-behavior scenario generator, not as the core engine for epidemiological contact truth.

### AgentTrust
AgentTrust positions itself as a trust layer for autonomous agents with identity, verification, secure communication, and auditability.
For this project, the key lesson is: if multiple agents are used later, trust and audit concepts matter more than realism theater. We need explicit logs, clear provenance, and bounded communication.

## OASIS / CAMEL / AgentTrust policy
These tools are treated as optional experimental modules.

They may be used to:
- generate bounded behavioral scenarios,
- test trust-sensitive adherence changes,
- run controlled stress tests,
- support auditable bounded agent collaboration if the project later needs a multi-agent experimental harness.

They must not be used to:
- replace empirical data,
- claim realistic latent contact recovery,
- trigger uncontrolled high-cost runs,
- or create the illusion of continuous autonomous progress when no active run exists.

## Operational orchestration rule for this project
The project now follows a stricter transparency rule:
- if no background run is active, say clearly that no background run is active,
- if direct work is happening, say it is direct work,
- if a subagent is launched, say what it is doing and when it ends,
- never imply continuous autonomous execution when the system is idle.

## Cost discipline
The human stated a rough budget of about 400 USD for model-backed experimentation.

Therefore:
- local rules and scripts first,
- cheap baselines first,
- no open-ended societies,
- cache prompts and outputs,
- use expensive model calls only for high-value steps,
- keep agentic simulation bounded and benchmarked against cheaper controls.

## Minimal audit trail
Every important project change should leave evidence in at least one of:
- `PROJECT_STATUS.md`
- `status/project_status.json`
- `docs/operations/decision_log.md`
- `docs/operations/task_system.md`
- `memory/YYYY-MM-DD.md`

## Current state summary
At the time of writing:
- the project is ROIA-first,
- the selected main idea is a lightweight behavioral adherence layer above French synthetic contact matrices,
- the backup idea is explainable uncertainty-aware French synthetic matrices,
- the current active phase is methodology design,
- no background agent is currently required for the main thread.

## External references
- CAMEL Workforce docs: https://docs.camel-ai.org/key_modules/workforce
- CAMEL Workforce API reference: https://docs.camel-ai.org/reference/camel.societies.workforce.workforce
- OASIS repository and docs entry point: https://github.com/camel-ai/oasis
- AgentTrust overview: https://agenttrust.ai/about

## Future documentation to add
- exact metric sheet,
- implementation module map,
- experiment naming convention,
- cost log for agentic runs,
- publication asset checklist for ROIA.
