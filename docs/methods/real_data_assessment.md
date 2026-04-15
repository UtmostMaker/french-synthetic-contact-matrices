# Real-data assessment on COMES-F

## What was actually evaluated

We replaced the in-memory placeholder reference with a real public COMES-F source:

- paper: Béraud et al. 2015, *The French Connection*
- raw-data page: https://www.contactmatrix.fr/index.php/raw-data
- archival DOI: https://doi.org/10.6084/m9.figshare.1466917
- downloaded file: `data/raw/comes_f/RawData_ComesF.xlsx`

The project now parses the public workbook directly and rebuilds a 17x17 age-contact matrix using the explicitly listed diary contacts.

This benchmark is real, but it is **not** a perfect reproduction of the published matrices. Three caveats matter:

1. the public workbook does not fully expand the supplementary professional contacts for high-contact workers,
2. the current parser does not apply the original survey re-weighting,
3. the reference used here is an arithmetic symmetrization of the reconstructed matrix, not the exact reciprocity correction from the paper.

So the present exercise is scientifically useful, but still a partial validation step.

## Empirical summary of the real benchmark

Parsed public workbook summary:

- participants: 2033
- observation days: 4066
- age-resolved listed contacts retained by the parser: 38,752
- reference diagonal share: 0.2113
- reference near-diagonal share: 0.3983

The real matrix is strongly age-assortative, with visible parent-child structure and lower symmetry than the handcrafted placeholder target.

## What works well on real data

### 1. The household rule-based baseline remains credible

Against the real COMES-F benchmark, the `household_rule_based` baseline is clearly better than the `demographic_scaling` baseline:

- `household_rule_based`: MAE = 0.3506, Frobenius = 8.8166
- `demographic_scaling`: MAE = 6.4761, Frobenius = 198.4165

This is a meaningful result. Even with a still-frugal setup, the rule-based generator captures enough of the age structure to land in the right qualitative regime.

### 2. The model still recovers a plausible contact shape

The real reference has diagonal share 0.2113, while the rule-based baseline reaches 0.1387. This is too diffuse, but not absurd. The generator does preserve age structure, intergenerational mixing, and broad life-stage separation.

### 3. The project now has a defensible real-data benchmark

This is a major improvement over the synthetic placeholder stage. The pipeline is no longer self-referential. It now tests a synthetic generator against a public French contact survey.

## What does not work

### 1. The benchmark is still incomplete relative to the published COMES-F analysis

The missing fully expanded supplementary professional contacts matter. They are exactly the kind of information that can reshape work-related mixing. As a result, the current benchmark is real but somewhat conservative, especially for adult working-age mixing.

### 2. The demographic-scaling baseline is not competitive

Its error remains extremely large. On this benchmark, it is not a serious baseline for a PhD contribution except as a deliberately weak comparator.

### 3. The rule-based baseline is still under-assortative

Relative to the real matrix, the rule-based generator spreads too much contact mass away from the diagonal:

- reference diagonal share: 0.2113
- rule-based diagonal share: 0.1387

So it captures the broad structure, but not the sharpness of age sorting.

### 4. The current real-data setup is not yet population-calibrated

The baseline currently uses respondent age counts from COMES-F as a proxy age distribution. That was acceptable for a bounded validation run, but it is not the right final calibration target. A proper next step would use INSEE marginals and a cleaner reciprocity correction.

## Does the behavioral layer add value on real data?

Short answer: **not as a benchmark-improving layer in its current form**.

The base rule-based matrix is the best performer among the tested variants:

- base rule-based baseline: MAE = 0.3506
- behavioral aggregate state: MAE = 0.3609
- evolved states: MAE = 0.3580 to 0.3585
- best generated scenario (`scenario_1`): MAE = 0.3581
- confinement scenario: MAE = 0.4135

So the behavioral layer does **not** improve fit to the real pre-pandemic COMES-F matrix. It usually makes the fit slightly worse, and the stronger intervention scenarios make it clearly worse.

That is not a failure of honesty. It is exactly what one should expect from a bounded behavioral perturbation layer applied to a pre-pandemic baseline survey. COMES-F is primarily a structural contact benchmark, not a behavioral-policy perturbation target.

## What the real contribution could be for a PhD

The defensible contribution is **not**: “the behavioral layer improves reconstruction of the static French contact matrix.”

The defensible contribution is closer to this:

1. build a transparent French synthetic baseline that reproduces broad empirical contact structure,
2. validate that baseline against real French contact survey data,
3. use the behavioral layer as a scenario generator for deviations from the baseline, rather than as a fit-improving estimator of the baseline itself.

That is a much stronger scientific position.

## Recommended pivot

### Recommended pivot: from “better static reconstruction” to “behaviorally interpretable perturbation around a validated baseline”

Concretely:

1. keep COMES-F as the structural pre-pandemic benchmark,
2. improve the structural generator first, especially diagonal sharpness and work-age mixing,
3. integrate the missing professional-contact information as far as the public data allow,
4. calibrate dynamic behavioral effects on pandemic-era sources such as SocialCov and CoviPrev instead of expecting gains on static COMES-F,
5. present the behavioral layer as a sensitivity-analysis and scenario-analysis module.

## What supervisors would find defensible

A defensible supervisor-facing message would be:

- the project now benchmarks against real French contact data,
- the heuristic household-aware baseline survives contact with real data and strongly outperforms a weak demographic baseline,
- the behavioral layer does not improve fit to the static COMES-F benchmark,
- therefore the behavioral layer should be repositioned as a dynamic scenario module, not sold as a better estimator of the baseline contact matrix,
- the next scientific step is better structural calibration plus pandemic-period validation on behavior-sensitive datasets.

That story is honest, methodologically coherent, and much easier to defend than an overclaim.
