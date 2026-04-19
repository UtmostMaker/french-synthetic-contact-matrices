# ROIA Experiment Plan

## Working paper direction
**Main idea:** a lightweight behavioral adherence layer above French synthetic contact matrices.

## ROIA-first research question
Can a bounded AI-based behavioral layer, constrained by French public data and added on top of a transparent synthetic contact matrix pipeline, improve public-health scenario analysis while remaining interpretable and socially grounded?

## Core claim discipline
We do **not** claim to recover true latent physical contacts from LLM agents.
We only claim that a bounded behavioral layer may improve the usefulness of scenario exploration, under explicit limits and empirical checks.

## Scientific contribution shape
1. A transparent French public-data pipeline for synthetic contact matrices.
2. A lightweight behavioral adherence layer that modifies contact intensity or setting weights under policy and perception changes.
3. A validation frame combining contact realism, behavioral realism, and epidemiological plausibility.
4. An explicit discussion of representational limits, social bias, and the place of AI in public-health modeling.

## Experimental ladder

### Stage 0. Data and benchmark audit
- Verify access and licensing for COMES-F, SocialCov, CoviPrev, and Santé publique France resources.
- Harmonize age bins, time windows, and geography.
- Freeze benchmark metrics before model tuning.

### Stage 1. Non-agentic baseline core
Implement and compare:
- **BASE-0001** demographic scaling baseline
- **BASE-0003** household-aware French rule-based generator
- optional **BASE-0004** mobility-augmented variant

Expected output:
- baseline contact matrices by age and setting
- first comparison against COMES-F aggregate structure

### Stage 2. Explainable uncertainty layer
Add simple uncertainty handling:
- bootstrap or parameter ranges on household, work, and school assumptions
- interval estimates on matrix entries
- uncertainty propagation to simple epidemic summaries

Expected output:
- matrix intervals
- sensitivity charts
- argument for backup paper IDEA-0002 if needed

### Stage 3. Lightweight behavioral adherence layer
Add a bounded behavior module that changes contact multipliers or setting-specific exposure according to:
- preventive behavior adoption
- risk perception
- trust or adherence proxies
- policy regime

Primary data anchors:
- CoviPrev
- SocialCov
- public policy timeline

Important constraint:
- start with explicit rules or small probabilistic state transitions
- do **not** start with OASIS or expensive LLM agents

### Stage 4. Optional agentic extension
Only if Stage 3 shows scientific value.

Possible role for OASIS / CAMEL / AgentTrust:
- generate bounded behavioral perturbation scenarios
- simulate trust-sensitive adherence shifts
- produce stress tests, not ground truth contacts

Hard constraints:
- small-scale only
- cached prompts
- strict budget monitoring
- compare against cheaper non-agentic control

## Evaluation axes

### A. Contact realism
- similarity to COMES-F matrix patterns
- age assortativity
- setting composition plausibility
- stability under small parameter perturbations

### B. Behavioral realism
- agreement with CoviPrev trends for preventive behavior and adherence proxies
- agreement with SocialCov direction of change under intervention periods

### C. Epidemiological plausibility
- simple downstream epidemic simulations
- comparison against hospital and urgent-care trend shapes, not exact causal reconstruction
- robustness across multiple plausible parameter settings

### D. ROIA-specific critical analysis
- what social realities are flattened by the model
- what trust, inequality, and territorial effects are only weakly represented
- what AI adds, and where it should remain bounded

## Baseline comparisons required
- demographic-only baseline
- household-aware rule baseline
- non-agentic behavior schedule baseline
- optional mobility baseline
- optional bounded agentic module only after the above

## Minimal viable paper path
If time or validation weakens the main idea:
1. pivot to IDEA-0002 as the main paper,
2. keep the behavioral layer as exploratory appendix or future work,
3. preserve all reusable code and benchmark outputs.

## Budget strategy
- local and rule-based first
- no open-ended agent societies
- reserve expensive external LLM calls for:
  - scenario compression,
  - controlled micro-simulations,
  - difficult interpretation or writing support
- maintain a cost log before any OASIS-style run

## Immediate next tasks
1. Create metric sheet for COMES-F, SocialCov, CoviPrev, and hospital comparisons.
2. Define the non-agentic behavioral state model.
3. Specify the simplest downstream epidemic simulator for plausibility checks.
4. Decide what exactly counts as success for a ROIA submission.
