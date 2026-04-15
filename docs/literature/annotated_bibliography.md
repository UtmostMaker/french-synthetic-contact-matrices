# Annotated Bibliography

This file will store concise notes for each relevant paper or resource.

## Entry template
### Citation key
- Research question:
- Data used:
- Method:
- Assumptions:
- Evaluation:
- Strengths:
- Weaknesses:
- Compute burden:
- Reproducibility:
- Extension opportunities:

---

### LIT-0001 Mossong et al. 2008, POLYMOD
- Research question: What do large-scale empirical age-specific contact patterns look like across European countries for respiratory or close-contact infections?
- Data used: One-day paper diaries from 7,290 participants across 8 European countries, with 97,904 contacts.
- Method: Population-based prospective contact survey, weighted analysis, smoothed contact surfaces, age-structured epidemic illustration.
- Assumptions: Reported conversational or physical contacts approximate transmission-relevant mixing for directly transmitted infections.
- Evaluation: Internal descriptive analysis plus illustrative epidemic modeling.
- Strengths: Foundational empirical benchmark, clear age assortativity, rich metadata on location, duration, and physicality.
- Weaknesses: Limited geographic scope, one-day diary design, pre-smartphone era behavior, mostly European contexts.
- Compute burden: Low to moderate.
- Reproducibility: High for the paper; data are widely reused.
- Extension opportunities: Use as baseline comparator, but do not over-transfer to France without checking French-specific deviations.

### LIT-0002 Béraud et al. 2015, COMES-F
- Research question: What are the age-specific contact patterns in France, and how do weekends and holidays modify them?
- Data used: COMES-F diary survey in France, 2,033 participants, 38,881 reported contacts and 54,378 contacts when supplementary professional contacts are included.
- Method: Weighted diary survey analysis, GAM-based contact matrix smoothing, reciprocity correction, stratification by period, gender, and location.
- Assumptions: Two-day diaries and supplementary professional contact reporting recover transmission-relevant French mixing patterns.
- Evaluation: Descriptive comparison across periods and assessment of effects on relative reproduction number under holiday or weekend structure.
- Strengths: Direct French empirical benchmark, open data/code availability, explicit holiday and professional-contact treatment.
- Weaknesses: Pre-pandemic and somewhat dated; no subnational French matrix family beyond broad descriptors; only one participant per household.
- Compute burden: Low to moderate.
- Reproducibility: High, because paper, matrices, raw data, and code were reported as available.
- Extension opportunities: Primary benchmark for any France-specific synthetic matrix paper; likely the most defensible anchor for evaluation.

### LIT-0003 Prem et al. 2017
- Research question: Can contact matrices be projected to countries lacking diary studies by combining empirical contact surveys with demographic and institutional data?
- Data used: POLYMOD, DHS household data, UN population data, ILO labor-force statistics, UNESCO school indicators, and related cross-country covariates.
- Method: Bayesian hierarchical model plus demographic transfer to construct home, work, school, and other-setting matrices for 152 countries.
- Assumptions: Country similarity in demographic and institutional structure is informative for latent contact structure.
- Evaluation: Leave-one-out style validation on household age matrices and external comparisons to selected empirical contact surveys.
- Strengths: Canonical synthetic-matrix reference, transparent decomposition by setting, very influential in downstream modeling.
- Weaknesses: Transfer from limited empirical source countries, coarse geography, limited uncertainty communication at application level.
- Compute burden: Moderate.
- Reproducibility: Medium to high.
- Extension opportunities: Strong baseline family for French public-data-only methods, especially if we can improve France-specific granularity or uncertainty quantification.

### LIT-0004 Prem et al. 2021
- Research question: How should the 2017 synthetic matrices be updated for the COVID-19 era, and how well do they compare to new empirical matrices?
- Data used: Updated demographic and institutional data, extended empirical comparison set, rural and urban stratification where available.
- Method: Updated synthetic matrix construction for 177 geographical regions, with empirical comparison and modeling-oriented validation.
- Assumptions: Updated demographic covariates and rural/urban separation improve transfer realism.
- Evaluation: Comparison to out-of-sample empirical matrices and scenario modeling under physical distancing interventions.
- Strengths: Broad coverage, more current inputs, rural/urban angle, stronger empirical comparison than the 2017 version.
- Weaknesses: Still mainly national or coarse regional transfer, limited country-specific custom structure for France, and not designed around French subnational public microdata.
- Compute burden: Moderate.
- Reproducibility: Medium to high.
- Extension opportunities: Sets a high bar for any claim that France-specific synthesis adds value beyond off-the-shelf global synthetic matrices.

### LIT-0005 Mistry et al. 2021
- Research question: Can high-resolution contact matrices be inferred from synthetic populations built from macro census and micro survey data?
- Data used: Detailed census and survey microdata on household composition, school structure, workplace structure, and related socio-demographic features for 35 countries and 277 subnational regions in a subset.
- Method: Synthetic population generation with setting-specific network inference, then contact-matrix extraction by age and location.
- Assumptions: Synthetic populations constructed from rich microdata can recover epidemiologically meaningful contact structure.
- Evaluation: Matrix inspection, epidemic sensitivity analysis, and comparison to diary-based data in selected settings.
- Strengths: Strong methodological relevance for a France project, explicitly supports subnational heterogeneity, grounded in synthetic populations rather than only demographic transfer.
- Weaknesses: High data appetite, greater implementation complexity, and France is not the main case study.
- Compute burden: Moderate to high.
- Reproducibility: Medium.
- Extension opportunities: Important comparator if we pursue a French synthetic-population pipeline, especially at region or territory level.

### LIT-0006 SocialCov France 2025
- Research question: How did contact patterns in France evolve during the SARS-CoV-2 pandemic across measures, occupations, and age groups?
- Data used: Repeated SocialCov survey waves in France from December 2020 to May 2022.
- Method: Survey-based estimation of time-varying contact patterns and age-mixing matrices.
- Assumptions: Online survey weighting adequately recovers population-level time-varying contacts.
- Evaluation: Temporal analysis of contacts under changing public-health measures.
- Strengths: France-specific, time-varying, behavior-sensitive, useful for dynamic validation and pandemic-era extensions.
- Weaknesses: Pandemic context differs from baseline endemic mixing; online survey biases may matter.
- Compute burden: Low to moderate.
- Reproducibility: Medium.
- Extension opportunities: Could support validation of dynamic or policy-sensitive synthetic adjustments, but should not replace pre-pandemic baseline benchmarks.

### LIT-0007 Di Domenico et al. 2026
- Research question: How well do mobility-informed synthetic contact matrices perform against empirical survey matrices for real-time epidemic modeling in France?
- Data used: French pre-pandemic empirical matrix baseline, Google workplace mobility, CoviPrev behavioral data, school schedules, SocialCov survey waves, hospitalization and serology data.
- Method: Weekly time-varying synthetic contact matrices constructed by reducing pre-pandemic matrix components using mobility and behavioral indicators, then plugged into transmission models.
- Assumptions: Real-time behavior and mobility proxies can update a baseline matrix into epidemiologically relevant effective contacts.
- Evaluation: Comparison of contact levels, age-specific patterns, hospital admissions, and serological trends.
- Strengths: Highly relevant and recent France-specific benchmark; explicitly compares synthetic versus empirical contact matrices in an operational setting.
- Weaknesses: Pandemic-focused, coarse age grouping, and oriented toward time variation rather than baseline French matrix generation from first principles.
- Compute burden: Moderate.
- Reproducibility: Medium to high.
- Extension opportunities: Important novelty guardrail. A new paper should avoid simply redoing mobility-updated matrices unless it clearly changes the scientific question.
