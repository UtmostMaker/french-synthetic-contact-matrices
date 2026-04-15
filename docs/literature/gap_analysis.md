# Gap Analysis

This is an initial synthesis, not a claim of novelty.

## What appears well-covered already
1. Cross-country synthetic contact matrix projection from demographic and institutional covariates.
2. France-specific empirical contact measurement at the national level through COMES-F.
3. Pandemic-era time-varying French contact matrices through survey and mobility-informed updates.
4. High-resolution synthetic-population methods in several non-French settings.

## What may still be underdeveloped for a defensible France paper
1. **France-first public-data pipeline**: a reproducible pipeline tailored to French public data sources rather than global transfer defaults.
2. **Subnational French heterogeneity**: region, department, or territorial-context variation appears much less established than national French matrices.
3. **Transparent uncertainty quantification**: many matrix products are used as point estimates; uncertainty propagation appears less standard in practical open pipelines.
4. **Benchmarking against the real French survey**: there is room for a disciplined France-specific benchmark framework comparing synthetic matrices to COMES-F and possibly pandemic-era matrices under controlled settings.
5. **Frugal reproducible methods**: there may be room for a method that is more lightweight and easier to reproduce than high-resolution synthetic-population systems while still outperforming naive demographic scaling.

## Reviewer-sensitive caution points
- A paper that only reproduces Prem-style transfer with French inputs will likely look incremental.
- A paper that claims strong epidemiological realism without careful validation against COMES-F will be weak.
- A complex synthetic-population method without clear gains over simpler baselines may be hard to defend.
- Pandemic-era adaptive matrices are already an active French line of work, so baseline novelty should probably focus elsewhere unless the contribution is explicitly dynamic.

## Initial recommendation
The most promising direction appears to be a **modest France-specific contribution** that combines:
- French public demographic and mobility or territorial data,
- a transparent, reproducible matrix-generation pipeline,
- explicit uncertainty or robustness analysis,
- and disciplined comparison against COMES-F plus simple and strong baselines.
