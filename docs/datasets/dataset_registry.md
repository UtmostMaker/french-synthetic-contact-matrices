# Dataset Registry

## Entry template
- Dataset ID:
- Name:
- Source:
- URL:
- Geography:
- Temporal coverage:
- Variables:
- Access method:
- License:
- Expected role in project:
- Risks or caveats:

---

## DATA-0001
- Dataset ID: DATA-0001
- Name: COMES-F raw data and contact matrices
- Source: contactmatrix.fr and linked Figshare archive referenced by Béraud et al. 2015
- URL: https://contactmatrix.fr/ and https://doi.org/10.6084/m9.figshare.1466917
- Geography: France
- Temporal coverage: 2012 fieldwork, published 2015
- Variables: Individual contacts by age, gender, location, duration, frequency, physicality, supplementary professional contacts
- Access method: Public website plus direct Figshare archival download of `RawData_ComesF.xlsx`
- License: CC BY 4.0 according to the public Figshare article metadata
- Expected role in project: Primary empirical benchmark for French contact structure
- Risks or caveats: Pre-pandemic; national rather than fine-grained subnational benchmark; public workbook exposes listed diary contacts but not fully expanded supplementary professional contacts

## DATA-0002
- Dataset ID: DATA-0002
- Name: Population by sex and five-year age groups
- Source: INSEE census publication
- URL: https://www.insee.fr/fr/statistiques/1893204
- Geography: France, departments, communes
- Temporal coverage: 1968 to 2022, latest release published 2025
- Variables: Population counts by sex and 20 five-year age groups
- Access method: Download from INSEE
- License: Open French public statistics reuse terms, exact statement to verify on download page
- Expected role in project: Core demographic marginal constraints for matrix generation and territorial heterogeneity
- Risks or caveats: Current public table is aggregated by five-year age bins; may require harmonization with contact age bins

## DATA-0003
- Dataset ID: DATA-0003
- Name: Professional mobility microdata, residence commune to work commune, 2022
- Source: INSEE census detail file
- URL: https://www.insee.fr/fr/statistiques/8589904
- Geography: France, commune-level origin and destination
- Temporal coverage: 2022
- Variables: Residence commune, work commune, individual and household characteristics, 32 variables, 7,388,023 observations reported by INSEE
- Access method: Download from INSEE as CSV or Parquet
- License: Open French public statistics reuse terms, exact statement to verify
- Expected role in project: Work-related mixing proxies and territorial connectivity features
- Risks or caveats: Commute flows are not direct contacts; ecological interpretation must stay modest

## DATA-0004
- Dataset ID: DATA-0004
- Name: School enrolment rates by age
- Source: INSEE annual statistics
- URL: https://www.insee.fr/fr/statistiques/2383587
- Geography: France
- Temporal coverage: 2000 to 2023, latest release published 2025
- Variables: Enrolment rates by age across primary, secondary, apprenticeship, higher education, and total schooling
- Access method: Download from INSEE
- License: Open French public statistics reuse terms, exact statement to verify
- Expected role in project: School-setting population exposure constraints by age
- Risks or caveats: Rates rather than direct school contact structure; may need Ministry of Education complements for school sizes or class distributions

## DATA-0005
- Dataset ID: DATA-0005
- Name: Activity by sex and age
- Source: INSEE Employment Survey long series
- URL: https://www.insee.fr/fr/statistiques/2489758
- Geography: France
- Temporal coverage: 1975 to 2024, latest release published 2025
- Variables: Active population counts and activity rates by sex and broad age groups
- Access method: Download from INSEE
- License: Open French public statistics reuse terms, exact statement to verify
- Expected role in project: Work participation priors or constraints in workplace matrix construction
- Risks or caveats: Broad age bands may be too coarse for fine contact-matrix estimation without supplementary sources

## DATA-0006
- Dataset ID: DATA-0006
- Name: Household size and composition statistics
- Source: INSEE household statistics and France et ses territoires synthesis
- URL: https://www.insee.fr/fr/statistiques/5039855
- Geography: France, with territorial variation in published summaries
- Temporal coverage: Core synthesis around 2017, publication 2021
- Variables: Household size, single-person households, households with children, larger-family shares, territorial variation indicators
- Access method: Download tables from INSEE
- License: Open French public statistics reuse terms, exact statement to verify
- Expected role in project: Household contact structure priors and territorial heterogeneity covariates
- Risks or caveats: Summary tables may be insufficient; more granular census microstructure may still be needed

## DATA-0007
- Dataset ID: DATA-0007
- Name: COVID-19 hospital data in France
- Source: Santé publique France via data.gouv.fr
- URL: https://www.data.gouv.fr/fr/datasets/donnees-hospitalieres-relatives-a-lepidemie-de-covid-19-en-france/
- Geography: France, with department, sex, age-class and region breakdowns depending on file
- Temporal coverage: Daily series during the epidemic, dataset page last crawled and metadata updated in 2025, core resources updated through 30 June 2023
- Variables: Hospitalized patients, intensive care or critical care, deaths, returns home, new admissions, regional age-class series
- Access method: Public CSV download from data.gouv.fr
- License: Open public data reuse, exact statement to verify on resource page
- Expected role in project: Outcome-level validation for epidemic realism of the simulator
- Risks or caveats: Hospital outcomes are delayed and policy-sensitive; they validate epidemiological consequences, not raw contacts directly

## DATA-0008
- Dataset ID: DATA-0008
- Name: Emergency departments and SOS Médecins COVID-19 data
- Source: Santé publique France via data.gouv.fr
- URL: https://www.data.gouv.fr/fr/datasets/donnees-des-urgences-hospitalieres-et-de-sos-medecins-relatives-a-lepidemie-de-covid-19/
- Geography: France
- Temporal coverage: Public dataset page metadata updated 1 January 2025
- Variables: Emergency visits and SOS Médecins indicators related to COVID-19
- Access method: Public CSV download from data.gouv.fr
- License: Open public data reuse, exact statement to verify on resource page
- Expected role in project: Faster epidemic-response validation signal, complementary to hospitalization data
- Risks or caveats: Syndrome-based urgent-care indicators are noisy and may reflect healthcare-seeking behavior as well as transmission

## DATA-0009
- Dataset ID: DATA-0009
- Name: CoviPrev repeated survey
- Source: Santé publique France
- URL: https://www.santepubliquefrance.fr/etudes-et-enquetes/coviprev-une-enquete-pour-suivre-l-evolution-des-comportements-et-de-la-sante-mentale-pendant-l-epidemie-de-covid-19
- Geography: France métropolitaine, with some regional outputs
- Temporal coverage: Repeated waves from 23 March 2020 to wave 37, page updated 15 October 2024
- Variables: Self-reported preventive behavior, mask use, distancing, vaccination intent, risk perception, mental health, social inequalities indicators
- Access method: Public reports and figures from Santé publique France
- License: Needs verification for machine-readable reuse of tabulated results
- Expected role in project: Behavioral calibration and validation target for trust, adherence, and prevention-behavior modules
- Risks or caveats: Quota-based online survey, self-reported behavior, and not a direct contact diary

## DATA-0010
- Dataset ID: DATA-0010
- Name: SocialCov France contact survey
- Source: BMC Infectious Diseases article and associated supplementary material
- URL: https://bmcinfectdis.biomedcentral.com/articles/10.1186/s12879-025-10611-4
- Geography: France
- Temporal coverage: Survey waves from December 2020 to May 2022, article published 14 February 2025
- Variables: Time-varying contact patterns under non-pharmaceutical interventions
- Access method: Article and supplementary material; exact downloadable data path to verify
- License: Needs verification from article and supplementary files
- Expected role in project: Dynamic contact-validation target for pandemic-period simulations
- Risks or caveats: Pandemic-only context and different measurement conditions from pre-pandemic baseline contact surveys
