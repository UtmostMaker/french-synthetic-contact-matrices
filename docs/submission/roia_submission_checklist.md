# ROIA submission checklist

## 1. Manuscript source and compilation

- [ ] `manuscript/roia_manuscript.tex` compiles from a clean checkout
- [ ] `pdflatex -> biber -> pdflatex -> pdflatex` runs without fatal errors
- [ ] No unresolved references remain in the `.log` or PDF
- [ ] No missing figure files remain in the LaTeX build
- [ ] French typography and accents render correctly in the final PDF
- [ ] Page layout, title block, abstract, keywords, and section order match ROIA requirements
- [ ] Replace the temporary class and front-matter macros if ROIA provides a mandatory template

## 2. Bibliography

- [ ] Every citation in the text has an entry in `manuscript/roia_manuscript.bib`
- [ ] Every `.bib` entry is actually cited or intentionally kept for near-final use
- [ ] DOI, URL, publisher, and year fields are complete where relevant
- [ ] French institutional sources are consistently formatted
- [ ] Dataset citations are complete for COMES-F, Google Mobility, CoviPrev, and SocialCov
- [ ] No duplicate bibliography keys remain
- [ ] Biber output is clean enough for submission

## 3. Figures and tables

- [ ] All manuscript figures are present under `manuscript/figures/`
- [ ] Final exp006 figures reflect archived real LLM outputs
- [ ] Figure filenames match the LaTeX includes exactly
- [ ] Resolution is sufficient for journal review and print export
- [ ] Axis labels, legends, and captions are readable in grayscale and on screen
- [ ] Tables fit the page and use journal-consistent formatting
- [ ] Numeric values in tables match the corresponding JSON outputs

## 4. Scientific consistency check

- [ ] Static results in the manuscript match `exp001` and `exp004` artifacts
- [ ] Temporal calibration results match `exp005` artifacts
- [ ] LLM profile results match `artifacts/outputs/exp006_llm_agents_results.json`
- [ ] Claims about cadres versus agriculteurs stay descriptive and proportionate
- [ ] Limitations are explicit about indirect profile targets and social bias risks
- [ ] No sentence implies individual-level validation that the data do not support

## 5. Author and metadata block

- [ ] Author names are final
- [ ] Affiliations are final
- [ ] Contact email is final
- [ ] ORCID identifiers are added if required
- [ ] Funding statement is complete
- [ ] Conflict of interest statement is included if required
- [ ] Data and code availability statement is present
- [ ] Acknowledgements are final

## 6. Cover letter package

- [ ] Short cover letter drafted for ROIA
- [ ] Cover letter explains the methodological contribution clearly
- [ ] Cover letter states why the paper fits ROIA and SHS / IA discussions
- [ ] Cover letter summarizes the empirical grounding and the honest limitations
- [ ] Suggested reviewers are prepared if the journal asks for them

## 7. Supplementary materials

- [ ] Decide whether robustness checks belong in the main paper or supplement
- [ ] Prepare a supplement for additional calibration details if needed
- [ ] Include profile construction notes if reviewers need more transparency
- [ ] Include experiment configuration references or an appendix table if useful
- [ ] Make sure supplementary files are cited consistently from the manuscript

## 8. Repository readiness

- [ ] `README.md` reflects the final project scope and core results
- [ ] Reproduction commands in the README were tested once from a clean shell
- [ ] Sensitive keys or local-only secrets are absent from the repository
- [ ] Large generated artifacts are either tracked intentionally or excluded cleanly
- [ ] Output paths used in the paper exist and are reproducible
- [ ] `.gitignore` is aligned with the final submission package
- [ ] License file is added before public release
- [ ] Final commit is tagged or otherwise frozen for submission

## 9. Final pre-submission pass

- [ ] Proofread the PDF once as a reader, not as the author
- [ ] Check that the abstract, introduction, results, discussion, and conclusion tell the same story
- [ ] Verify that limitations are honest but not self-undermining
- [ ] Export the final PDF with a stable filename
- [ ] Archive the exact submission package used for ROIA
