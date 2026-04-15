# Baseline Registry

## Baseline families to implement or emulate

### BASE-0001 Simple demographic scaling
- Description: Start from the empirical French COMES-F matrix and adapt only by demographic reweighting to a target French population structure.
- Why it matters: Extremely frugal and difficult to beat if the proposed method adds complexity without real gain.
- Data needs: COMES-F, target population age distribution.

### BASE-0002 Prem-style synthetic transfer
- Description: Reproduce a country-transfer synthetic baseline using demographic and institutional covariates, as close as practical to Prem et al. 2017 or 2021.
- Why it matters: Canonical synthetic benchmark.
- Data needs: Public demographic, schooling, and work covariates.

### BASE-0003 Household-aware French rule-based generator
- Description: Build setting-specific contacts using French household size/composition plus school enrolment and work participation priors, without high-resolution synthetic micro-populations.
- Why it matters: Likely strongest lightweight baseline and possibly the natural stepping stone to a paper contribution.
- Data needs: INSEE demographic, household, schooling, and activity data.

### BASE-0004 Mobility-augmented French baseline
- Description: Add territorial or commute-flow modifiers to a baseline French synthetic matrix.
- Why it matters: Tests whether mobility or territorial context adds measurable value beyond demography alone.
- Data needs: INSEE commute or mobility flow data.

### BASE-0005 Uncertainty-aware probabilistic baseline
- Description: Instead of a point estimate, generate posterior samples or interval estimates for contact matrix entries under simple structural assumptions.
- Why it matters: Potentially differentiating contribution if uncertainty is handled transparently and usefully.
- Data needs: Same as BASE-0003 or BASE-0004 plus uncertainty assumptions.

## Baseline selection principles
- Every advanced method must beat BASE-0001 or explain clearly why not.
- Every heavier method must be compared against BASE-0003.
- If a mobility-informed method is explored, compare it against both demographic-only and empirical French baselines.
