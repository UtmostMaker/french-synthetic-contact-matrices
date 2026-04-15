# French Synthetic Contact Matrices

[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

Dépôt de recherche reproductible consacré à la construction, l'évaluation et la discussion de matrices de contact synthétiques françaises, avec un manuscrit ROIA et une extension comportementale par profils socio-démographiques alimentée par de vraies générations LLM.

## Ce que contient ce dépôt

Le projet suit une progression expérimentale volontairement incrémentale :

1. une repondération démographique simple ;
2. un modèle de référence structuré par ménage, école, travail et communauté ;
3. une version optimisée de ce modèle sur COMES-F ;
4. une couche comportementale temporelle calibrée sur des séries françaises de la période Covid ;
5. une couche d'agents socio-démographiques avec 22 profils et des générations réelles Claude Sonnet 4.6 via OmniMart.

L'objectif n'est pas de remplacer les enquêtes françaises par une boîte noire. L'objectif est de rendre chaque couche de modélisation explicite, testable et auditable.

## Résultats principaux

### Résultats statiques sur les matrices de contact

- Le modèle structuré surpasse nettement la simple repondération démographique.
- L'optimisation du modèle structuré sur COMES-F améliore la MAE de **0,35** à **0,27**, soit un gain relatif de **23,8 %**.
- La réciprocité reste stable dans les variantes structurées et se dégrade dans le modèle purement démographique.

### Résultats temporels comportementaux

- La calibration améliore l'ajustement en apprentissage.
- Les performances hors échantillon restent contrastées.
- La couche comportementale calibrée reste utile pour les comportements de prévention, mais demeure plus faible que la référence statique sur les variations de contacts SocialCov.

### Résultats des agents LLM réels

Avec **22 profils socio-démographiques × 6 périodes de politique sanitaire**, les générations réelles Claude Sonnet 4.6 produisent un gradient de politique publique lisible :

- Pré-pandémie : réduction de mobilité **0,04**, adhésion au masque **0,15**
- Premier confinement : réduction de mobilité **0,68**, adhésion au masque **0,66**
- Déconfinement : réduction de mobilité **0,26**, adhésion au masque **0,57**
- Restrictions de deuxième vague : réduction de mobilité **0,45**, adhésion au masque **0,71**
- Couvre-feu : réduction de mobilité **0,55**, adhésion au masque **0,76**
- Pass sanitaire : réduction de mobilité **0,50**, adhésion au masque **0,50**

Le profil le plus réactif est **cadre 35-49 ans en couple avec enfants** avec un delta de **+0,65**. Le moins réactif est **agriculteur 50-64 ans en couple** avec **+0,26**. Cet écart constitue l'un des résultats SHS centraux du projet.

## Structure du dépôt

```text
.
├── artifacts/        Sorties générées, rapports d'expériences, résultats publics
├── data/             Notes de données et entrées françaises intermédiaires
├── docs/             Notes méthodologiques, cartographie de littérature, matériaux de soumission
├── experiments/      Configurations d'expériences enregistrées
├── manuscript/       Manuscrit ROIA et figures de publication
├── scripts/          Points d'entrée reproductibles pour expériences et figures
├── src/              Package Python implémentant modèles, métriques et couches comportementales
└── tests/            Tests unitaires et tests fumée
```

## Reproduire les résultats principaux

### 1. Préparer l'environnement

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si tu préfères utiliser la pile scientifique déjà présente dans le dépôt, plusieurs scripts de figures peuvent aussi être lancés directement avec `python3` depuis la racine du projet.

### 2. Modèles statiques et optimisation

```bash
python3 scripts/run_exp001.py
python3 scripts/generate_figures.py
python3 scripts/run_exp004.py
```

Sorties principales :

- `artifacts/outputs/exp001_results.json`
- `artifacts/outputs/exp004_optimized_baseline_results.json`
- `manuscript/figures/exp001_*.png`

### 3. Calibration temporelle comportementale

```bash
python3 scripts/run_exp003.py
python3 scripts/run_exp005.py
```

Sorties principales :

- `artifacts/outputs/exp003_results.json`
- `artifacts/outputs/exp005_calibrated_behavioral_results.json`
- `manuscript/figures/exp003_*.png`

### 4. Résultats réels des profils LLM

Si les générations réelles en cache sont déjà présentes, régénère les figures finales avec :

```bash
python3 scripts/run_exp006_final.py
python3 scripts/generate_exp006_real_figures.py
```

Si tu veux relancer la génération des profils, fournis `OMNIMART_API_KEY` puis exécute :

```bash
python3 scripts/run_exp006.py
```

Sorties principales :

- `artifacts/outputs/exp006_llm_agents_results.json`
- `manuscript/figures/exp006_llm_vs_observed_mobility_by_policy.png`
- `manuscript/figures/exp006_profile_responsiveness_ranking.png`
- `manuscript/figures/exp006_social_bias_analysis.png`

## Statut de publication

- Source du manuscrit ROIA : `manuscript/roia_manuscript.tex`
- Manuscrit compilé : `manuscript/roia_manuscript.pdf`
- Checklist de soumission : `docs/submission/roia_submission_checklist.md`
- Guide de publication GitHub : `docs/submission/github_publication_steps.md`

Pour compiler le manuscrit depuis `manuscript/` :

```bash
pdflatex roia_manuscript.tex
bibtex roia_manuscript
pdflatex roia_manuscript.tex
pdflatex roia_manuscript.tex
```

## Notes sur les données et l'interprétation

- `exp001` conserve un banc d'essai synthétique contrôlé pour valider le pipeline.
- COMES-F sert de cible empirique pour le modèle structurel optimisé.
- CoviPrev et SocialCov alimentent la couche temporelle.
- Le module LLM par profils est **descriptif et exploratoire**, pas un estimateur individuel.
- Les cibles par profil restent indirectes car les données publiques françaises pleinement stratifiées restent limitées.

## Citation

Le fichier `CITATION.cff` fournit une base de citation logicielle. Une citation plus complète pourra être figée après diffusion du manuscrit ou acceptation de l'article.

## Licence

Ce dépôt est diffusé sous licence MIT.
