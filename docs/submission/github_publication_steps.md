# GitHub publication steps

## Goal
Publish `french-synthetic-contact-matrices` as a standalone public repository, not as part of the wider `openclaw-workspace` repository.

## Recommended repository name
`french-synthetic-contact-matrices`

## What should be public
- source code under `src/`
- experiment configs and runners under `experiments/` and `scripts/`
- manuscript source and figures under `manuscript/`
- documentation under `docs/`
- public results JSON files under `artifacts/outputs/`

## What should stay private or be excluded
- local caches under `artifacts/cache/`
- submission bundles under `artifacts/submission/`
- local-only helper scripts for email or key handling
- any secret-bearing or environment-specific wrappers
- raw data if the license or redistribution path is unclear

## Clean publication workflow
1. Create a new empty GitHub repository named `french-synthetic-contact-matrices`.
2. Export or copy the project directory as a standalone repo.
3. Verify `.gitignore` excludes local caches, LaTeX build artifacts, and private scripts.
4. Review the tree one last time for secrets, private email tooling, and temporary wrappers.
5. Commit with a message such as `Prepare public research release`.
6. Add the new GitHub remote.
7. Push the `main` branch.
8. Enable repository topics and add a short release description.

## Suggested topics
- computational-epidemiology
- synthetic-populations
- contact-matrices
- france
- public-health
- llm-agents
- social-simulation

## Suggested first release notes
- validated structural baseline on COMES-F
- time-varying behavioral extension using CoviPrev and SocialCov
- exploratory LLM-agent scenario layer with SHS-oriented bias analysis
