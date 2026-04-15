from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class SocioDemographicProfile:
    """Synthetic French profile with approximate joint weights.

    The weights are normalized synthetic priors, not exact joint frequencies.
    They are anchored to public French marginals from INSEE and Dares:
    age structure, broad PCS composition, household forms, retirement/student
    prevalence, and telework constraints. They are intended for transparent,
    auditable scenario design rather than microdata reconstruction.
    """

    name: str
    age_range: str
    occupation: str
    household_type: str
    typical_settings: dict[str, float]
    vulnerability_factors: str
    trust_proxy: float
    population_weight: float
    source_summary: str
    source_urls: tuple[str, ...]
    label: str | None = None
    preventive_behavior_multiplier: float = 1.0
    mobility_constraint: float = 0.5
    digital_flexibility: float = 0.5

    @property
    def key(self) -> str:
        return self.name

    @property
    def household_structure(self) -> str:
        return self.household_type

    @property
    def trust_in_authorities_proxy(self) -> float:
        return self.trust_proxy

    @property
    def work_or_school_setting(self) -> str:
        ordered = sorted(self.typical_settings.items(), key=lambda item: item[1], reverse=True)
        return ", ".join(f"{setting}={weight:.2f}" for setting, weight in ordered)

    @property
    def mobility_pattern(self) -> str:
        if self.mobility_constraint >= 0.75:
            return "Mobilité très contrainte par le présentiel ou les ressources."
        if self.mobility_constraint >= 0.55:
            return "Mobilité contrainte mais partiellement modulable selon les restrictions."
        return "Mobilité plus flexible avec marge de réduction en période restrictive."

    @property
    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()


PROFILE_SOURCE_URLS = {
    "pcs": "https://www.insee.fr/fr/statistiques/1288152",
    "households": "https://www.insee.fr/fr/statistiques/2381486",
    "retirement": "https://www.insee.fr/fr/statistiques/6432953",
    "students": "https://www.insee.fr/fr/statistiques/5432509",
    "telework": "https://dares.travail-emploi.gouv.fr/publication/le-teletravail-en-2024",
    "coviprev": "https://www.data.gouv.fr/fr/datasets/donnees-denquete-relatives-a-levolution-des-comportements-et-de-la-sante-mentale-pendant-lepidemie-de-covid-19-coviprev/",
}


COMMON_SOURCE_SUMMARY = (
    "Poids synthétiques approchés à partir des marges INSEE sur l'âge, les PCS et les ménages, "
    "complétés par Dares pour les écarts de télétravail et par CoviPrev pour le gradient de prévention."
)


PROFILES: tuple[SocioDemographicProfile, ...] = (
    SocioDemographicProfile(
        name="etudiant_18_24_parents",
        label="Étudiant 18-24 vivant chez ses parents",
        age_range="18-24",
        occupation="etudiant",
        household_type="chez_parents",
        typical_settings={"home": 0.38, "school": 0.34, "work": 0.08, "other": 0.20},
        vulnerability_factors="Dépendance aux décisions universitaires, santé mentale, promiscuité familiale variable, revenus faibles.",
        trust_proxy=0.50,
        population_weight=0.06,
        preventive_behavior_multiplier=0.97,
        mobility_constraint=0.46,
        digital_flexibility=0.80,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["students"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="etudiant_18_24_colocation",
        label="Étudiant 18-24 en colocation ou studio",
        age_range="18-24",
        occupation="etudiant",
        household_type="colocation_ou_studio",
        typical_settings={"home": 0.30, "school": 0.36, "work": 0.10, "other": 0.24},
        vulnerability_factors="Logement souvent exigu, petits emplois, sociabilité étudiante forte, dépendance aux transports.",
        trust_proxy=0.47,
        population_weight=0.04,
        preventive_behavior_multiplier=0.95,
        mobility_constraint=0.50,
        digital_flexibility=0.84,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["students"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="employe_25_34_seul",
        label="Employé 25-34 vivant seul",
        age_range="25-34",
        occupation="employe",
        household_type="seul",
        typical_settings={"home": 0.34, "school": 0.00, "work": 0.42, "other": 0.24},
        vulnerability_factors="Présentiel fréquent, contacts avec le public, logement urbain parfois petit.",
        trust_proxy=0.49,
        population_weight=0.09,
        preventive_behavior_multiplier=0.99,
        mobility_constraint=0.74,
        digital_flexibility=0.32,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="employe_35_49_monoparent",
        label="Employé 35-49 en famille monoparentale",
        age_range="35-49",
        occupation="employe",
        household_type="famille_monoparentale",
        typical_settings={"home": 0.40, "school": 0.06, "work": 0.34, "other": 0.20},
        vulnerability_factors="Charge domestique élevée, arbitrages emploi-enfants, faible marge pour s'isoler.",
        trust_proxy=0.46,
        population_weight=0.05,
        preventive_behavior_multiplier=0.98,
        mobility_constraint=0.78,
        digital_flexibility=0.26,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="ouvrier_25_34_couple_enfants",
        label="Ouvrier 25-34 en couple avec enfants",
        age_range="25-34",
        occupation="ouvrier",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.36, "school": 0.04, "work": 0.42, "other": 0.18},
        vulnerability_factors="Présentiel peu télétravaillable, trajets contraints, budget serré, exposition via enfants.",
        trust_proxy=0.43,
        population_weight=0.06,
        preventive_behavior_multiplier=0.96,
        mobility_constraint=0.84,
        digital_flexibility=0.16,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="ouvrier_35_49_couple_enfants",
        label="Ouvrier 35-49 en couple avec enfants",
        age_range="35-49",
        occupation="ouvrier",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.38, "school": 0.04, "work": 0.40, "other": 0.18},
        vulnerability_factors="Présentiel durable, cohabitation familiale, moindre autonomie sur horaires et protection au travail.",
        trust_proxy=0.41,
        population_weight=0.08,
        preventive_behavior_multiplier=0.96,
        mobility_constraint=0.85,
        digital_flexibility=0.14,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="employe_35_49_couple_enfants",
        label="Employé 35-49 en couple avec enfants",
        age_range="35-49",
        occupation="employe",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.38, "school": 0.04, "work": 0.36, "other": 0.22},
        vulnerability_factors="Contacts professionnels réguliers, transports, arbitrages familiaux, exposition via enfants.",
        trust_proxy=0.50,
        population_weight=0.08,
        preventive_behavior_multiplier=1.00,
        mobility_constraint=0.72,
        digital_flexibility=0.36,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="profession_intermediaire_35_49_couple_enfants",
        label="Profession intermédiaire 35-49 en couple avec enfants",
        age_range="35-49",
        occupation="profession_intermediaire",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.36, "school": 0.04, "work": 0.38, "other": 0.22},
        vulnerability_factors="Mixte présentiel-distanciel, exposition persistante dans l'enseignement, la santé et la technique.",
        trust_proxy=0.58,
        population_weight=0.08,
        preventive_behavior_multiplier=1.02,
        mobility_constraint=0.58,
        digital_flexibility=0.56,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="cadre_25_34_seul",
        label="Cadre 25-34 vivant seul",
        age_range="25-34",
        occupation="cadre",
        household_type="seul",
        typical_settings={"home": 0.42, "school": 0.00, "work": 0.28, "other": 0.30},
        vulnerability_factors="Exposition physique plus faible mais fatigue numérique et isolement possibles.",
        trust_proxy=0.65,
        population_weight=0.05,
        preventive_behavior_multiplier=1.05,
        mobility_constraint=0.34,
        digital_flexibility=0.88,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="cadre_35_49_couple_enfants",
        label="Cadre 35-49 en couple avec enfants",
        age_range="35-49",
        occupation="cadre",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.40, "school": 0.04, "work": 0.28, "other": 0.28},
        vulnerability_factors="Exposition limitée par le télétravail mais tensions d'organisation familiale lors des fermetures scolaires.",
        trust_proxy=0.68,
        population_weight=0.07,
        preventive_behavior_multiplier=1.06,
        mobility_constraint=0.38,
        digital_flexibility=0.90,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="independant_35_49_couple_enfants",
        label="Indépendant 35-49 en couple avec enfants",
        age_range="35-49",
        occupation="artisan_commercant",
        household_type="couple_avec_enfants",
        typical_settings={"home": 0.34, "school": 0.04, "work": 0.40, "other": 0.22},
        vulnerability_factors="Dépendance à l'ouverture des commerces, exposition clients, forte incertitude économique.",
        trust_proxy=0.42,
        population_weight=0.04,
        preventive_behavior_multiplier=0.95,
        mobility_constraint=0.70,
        digital_flexibility=0.28,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="agriculteur_50_64_couple",
        label="Agriculteur 50-64 en couple",
        age_range="50-64",
        occupation="agriculteur",
        household_type="couple",
        typical_settings={"home": 0.38, "school": 0.00, "work": 0.42, "other": 0.20},
        vulnerability_factors="Activité peu interrompable, accès aux soins plus distant, isolement territorial relatif.",
        trust_proxy=0.48,
        population_weight=0.02,
        preventive_behavior_multiplier=0.98,
        mobility_constraint=0.72,
        digital_flexibility=0.18,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="inactif_50_64_seul",
        label="Inactif 50-64 vivant seul",
        age_range="50-64",
        occupation="inactive_au_foyer",
        household_type="seul",
        typical_settings={"home": 0.54, "school": 0.00, "work": 0.00, "other": 0.46},
        vulnerability_factors="Ressources parfois fragiles, isolement, exposition via démarches et sociabilités locales.",
        trust_proxy=0.51,
        population_weight=0.05,
        preventive_behavior_multiplier=1.01,
        mobility_constraint=0.44,
        digital_flexibility=0.38,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"], PROFILE_SOURCE_URLS["pcs"]),
    ),
    SocioDemographicProfile(
        name="chomeur_25_49_seul",
        label="Chômeur 25-49 vivant seul ou chez un proche",
        age_range="25-49",
        occupation="chomeur",
        household_type="seul_ou_heberge",
        typical_settings={"home": 0.50, "school": 0.00, "work": 0.00, "other": 0.50},
        vulnerability_factors="Précarité matérielle, santé mentale, dépendance administrative, confiance institutionnelle plus basse.",
        trust_proxy=0.39,
        population_weight=0.05,
        preventive_behavior_multiplier=0.94,
        mobility_constraint=0.40,
        digital_flexibility=0.34,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="retraite_65_74_couple",
        label="Retraité 65-74 en couple",
        age_range="65-74",
        occupation="retraite",
        household_type="couple",
        typical_settings={"home": 0.58, "school": 0.00, "work": 0.00, "other": 0.42},
        vulnerability_factors="Risque médical accru, vigilance sanitaire élevée, sociabilités de proximité et familiales.",
        trust_proxy=0.64,
        population_weight=0.10,
        preventive_behavior_multiplier=1.08,
        mobility_constraint=0.42,
        digital_flexibility=0.42,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["retirement"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="retraite_75_plus_seul",
        label="Retraité 75+ vivant seul",
        age_range="75+",
        occupation="retraite",
        household_type="seul",
        typical_settings={"home": 0.68, "school": 0.00, "work": 0.00, "other": 0.32},
        vulnerability_factors="Forte vulnérabilité médicale, dépendance possible aux proches ou aux soins, risque d'isolement.",
        trust_proxy=0.66,
        population_weight=0.08,
        preventive_behavior_multiplier=1.10,
        mobility_constraint=0.34,
        digital_flexibility=0.30,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["retirement"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["coviprev"]),
    ),
    SocioDemographicProfile(
        name="employe_50_64_couple",
        label="Employé 50-64 en couple",
        age_range="50-64",
        occupation="employe",
        household_type="couple",
        typical_settings={"home": 0.42, "school": 0.00, "work": 0.36, "other": 0.22},
        vulnerability_factors="Présentiel encore fréquent, vigilance accrue avec l'âge, marge de télétravail limitée.",
        trust_proxy=0.54,
        population_weight=0.06,
        preventive_behavior_multiplier=1.03,
        mobility_constraint=0.66,
        digital_flexibility=0.34,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
    SocioDemographicProfile(
        name="ouvrier_50_64_couple",
        label="Ouvrier 50-64 en couple",
        age_range="50-64",
        occupation="ouvrier",
        household_type="couple",
        typical_settings={"home": 0.44, "school": 0.00, "work": 0.38, "other": 0.18},
        vulnerability_factors="Présentiel prolongé, risque sanitaire accru avec l'âge, usure physique et trajets contraints.",
        trust_proxy=0.44,
        population_weight=0.04,
        preventive_behavior_multiplier=0.99,
        mobility_constraint=0.80,
        digital_flexibility=0.16,
        source_summary=COMMON_SOURCE_SUMMARY,
        source_urls=(PROFILE_SOURCE_URLS["pcs"], PROFILE_SOURCE_URLS["households"], PROFILE_SOURCE_URLS["telework"]),
    ),
)


def load_profiles() -> list[SocioDemographicProfile]:
    total_weight = sum(profile.population_weight for profile in PROFILES)
    if total_weight <= 0:
        return list(PROFILES)
    return [replace(profile, population_weight=profile.population_weight / total_weight) for profile in PROFILES]


def profile_lookup() -> dict[str, SocioDemographicProfile]:
    return {profile.key: profile for profile in PROFILES}
