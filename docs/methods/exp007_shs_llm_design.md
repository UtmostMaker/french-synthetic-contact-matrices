# Exp007, protocole SHS-LLM auditable pour la diffusion épidémique

## Positionnement

Exp007 fait de la couche LLM le médiateur principal entre :
1. profils socio-demographiques français,
2. régimes sanitaires,
3. modificateurs de diffusion utiles au modèle épidémique.

Le LLM n'est pas présenté comme producteur de « vrais contacts ». Il sert à estimer un vecteur de **variables latentes SHS** ensuite projetées dans la couche comportementale calibrée d'`exp005`.

## Protocole scientifique

Le protocole versionné vit dans :
- `experiments/protocols/exp007_shs_llm_protocol_v2.yaml`

Il fixe explicitement :
- l'objectif de recherche,
- la rationalité scientifique,
- les principes de scoring,
- les règles anti-biais,
- la définition et les ancres de chaque variable latente,
- le schéma JSON de réponse attendu.

## Variables latentes demandées au modèle

- `adherence_level`
- `risk_perception`
- `trust_in_authorities`
- `mobility_reduction`
- `compliance_capacity`
- `economic_constraint`
- `social_pressure`
- `household_pressure`
- `policy_fatigue`
- `mask_adherence`
- `isolation_propensity`

Chaque variable est scorée sur `[0,1]` avec des ancres textuelles explicites pour `0`, `0.5` et `1`.

## Auditabilité

Chaque appel modèle génère un artefact d'audit versionné sous :
- `artifacts/audits/exp007_shs_llm/`

Chaque fichier d'audit contient :
- `protocol_id`
- `prompt_version`
- `prompt_hash`
- le `system_prompt`
- le `user_prompt`
- le schéma JSON imposé
- la réponse brute du modèle
- le payload parsé
- les métadonnées backend, modèle, coût et durée si disponibles

Ainsi, un score LLM dans les résultats renvoie vers un prompt exact et une réponse exacte.

## Protocole de reprise automatique sur limite Claude CLI

Quand `claude-cli` répond une limite de quota ou de rate limit avec une heure de reprise explicite, la couche LLM :
- détecte la réponse `429` ou le message `You've hit your limit`,
- extrait l'heure de reset annoncée,
- attend automatiquement jusqu'à cette heure avec une marge de sécurité configurable,
- émet un log périodique pendant l'attente pour éviter qu'un superviseur externe tue le run pour silence,
- relance ensuite exactement le même appel sans demander une intervention humaine.

La configuration est pilotée dans `experiments/configs/exp007_shs_llm.yaml` via :
- `auto_wait_on_rate_limit`
- `rate_limit_reset_buffer_seconds`
- `rate_limit_poll_seconds`
- `rate_limit_max_wait_seconds`

Ce protocole permet de finir les runs longs malgré des fenêtres de quota quotidiennes, sans glisser vers un fallback heuristique ni nécessiter un re-run manuel.

## Backend expérimental retenu

Pour cette passe, le backend demandé est :
- `claude-cli/haiku-4-5`

Implémentation retenue :
- `claude --print`
- `--model claude-haiku-4-5`
- `--system-prompt` fixe et versionné
- `--json-schema` pour forcer une sortie structurée
- pas de fallback automatique de modèle
- arrêt immédiat si le run tombe sur une erreur au lieu de glisser vers un fallback heuristique

## Projection vers la diffusion

Les sorties LLM sont transformées en :
- indice de prévention,
- ratio de contact via la couche calibrée d'`exp005`,
- pression de transmission.

Cela évite une chaîne opaque de type « LLM in, résultat épidémique out ».

## Comparaisons expérimentales

Exp007 compare :
- la couche **LLM SHS**,
- une **baseline heuristique** utilisant la même projection,
- les observations externes issues de **Google Mobility** et **CoviPrev**.

## Garde-fous méthodologiques

- mêmes profils, mêmes régimes, même schéma de sortie pour tous les appels
- variables latentes définies avant le run, pas après coup
- prompt hashé et journalisé
- pas de chaîne de pensée demandée ni exploitée
- inégalités acceptées uniquement si elles dérivent de contraintes fournies dans le prompt
- arrêt immédiat si le backend réel échoue

## Motivation scientifique

Cette direction s'appuie sur trois idées :
- utiliser le LLM comme simulateur de régularités comportementales plutôt que comme oracle individuel,
- formaliser les médiateurs SHS qui relient politiques publiques et comportements,
- garder une couche épidémiologique explicite entre sorties LLM et diffusion.

## Sources de cadrage

- Park et al. 2023, Generative Agents
- Xi et al. 2023, survey sur les agents LLM
- Aher et al. 2023, Turing Experiments
- Cheng et al. 2024, survey LLM + agent-based modeling
- Han et al. 2022, confiance, risque et comportements COVID
- bibliographie interne du projet sur COMES-F, SocialCov et CoviPrev
