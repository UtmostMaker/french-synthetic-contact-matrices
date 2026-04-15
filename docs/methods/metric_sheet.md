# Metric Sheet

## Purpose
This document fixes the first evaluation metrics before implementation, to reduce retrospective tuning.

## Evaluation blocks
The project evaluates three distinct things:
1. contact-structure realism,
2. behavioral realism,
3. epidemiological plausibility.

These are not interchangeable and must not be collapsed into one score.

## A. Contact-structure realism

### A1. Matrix distance to COMES-F
- Compare age-by-age matrices after harmonizing age bins.
- Candidate metrics:
  - Frobenius norm difference
  - Mean absolute error per cell
  - Symmetrized relative error
- Use case: direct comparison of synthetic baseline versus French empirical benchmark.

### A2. Age assortativity preservation
- Measure whether strong age-assortative mixing bands are preserved.
- Candidate metrics:
  - diagonal mass share
  - near-diagonal mass share
  - assortativity coefficient
- Use case: checks structural plausibility beyond raw error.

### A3. Setting composition plausibility
- Compare contact contribution by setting: home, school, work, other.
- Candidate outputs:
  - setting share bar charts
  - age-specific setting dominance profiles
- Use case: detect unrealistic over-allocation to one context.

### A4. Reciprocity consistency
- Check reciprocity after demographic weighting.
- Candidate metric:
  - mean absolute reciprocity gap by cell
- Use case: sanity check for generated matrices.

## B. Behavioral realism

### B1. CoviPrev alignment
- Compare modeled adherence states or protection multipliers against observed trends in public preventive behavior.
- Candidate variables:
  - barrier gestures
  - distancing proxies
  - mask-related behavior when relevant
  - vaccine acceptance or trust proxies if used later
- Candidate metric:
  - trend-direction agreement
  - normalized error on wave-level behavior prevalence

### B2. SocialCov contact-change alignment
- Compare direction and rough amplitude of contact changes under intervention periods.
- Candidate metric:
  - relative change error from pre-policy reference
  - rank-order agreement across periods

### B3. Policy-regime responsiveness
- Check whether the model responds in the expected direction when restrictions tighten or loosen.
- Candidate output:
  - event-study style plots around policy changes

## C. Epidemiological plausibility

### C1. Shape agreement with hospital series
- Use simple downstream epidemic simulations and compare trend shape, not exact causal identification.
- Candidate targets:
  - hospital occupancy
  - ICU occupancy or equivalent critical-care series
  - new admissions if usable
- Candidate metrics:
  - correlation on smoothed trend
  - peak timing error
  - relative peak magnitude error

### C2. Fast-signal plausibility
- Optional comparison with emergency or SOS Médecins data.
- Candidate metric:
  - wave timing agreement
  - coarse rise and decline slope agreement

### C3. Robustness under uncertainty
- Evaluate stability of epidemic summaries under uncertainty in matrix entries and behavior parameters.
- Candidate outputs:
  - interval bands on peak timing
  - interval bands on relative burden
  - tornado plot for sensitivity ranking

## D. ROIA-specific critical evaluation

### D1. Social flattening audit
- Identify what dimensions are absent or weakly represented.
- Candidate axes:
  - inequality proxies
  - territorial disadvantage
  - occupation simplification
  - household diversity simplification

### D2. AI value-added audit
- Ask what the behavioral AI layer improves over explicit rule schedules.
- Required comparison:
  - non-agentic behavior schedule baseline versus bounded behavioral layer
- Candidate outputs:
  - comparative table of gain, cost, interpretability, and fragility

## Minimal metric set for first implementation
The first implementation milestone must compute at least:
- matrix MAE or Frobenius distance to COMES-F,
- diagonal or near-diagonal age assortativity metric,
- reciprocity gap,
- one CoviPrev alignment metric,
- one SocialCov change-alignment metric,
- one smoothed hospital trend metric.

## Guardrails
- Do not optimize all metrics simultaneously without a documented tradeoff.
- Do not claim realism from epidemiological fit alone.
- Do not claim behavioral realism from one survey alignment alone.
- Keep all metrics reproducible from saved configs and outputs.
