from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .agent_profiles import SocioDemographicProfile


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "cache" / "llm_behavioral_agent"
DEFAULT_OMNIMART_BASE_URL = "https://www.omnimartapi.store/v1"
DEFAULT_MODEL_CANDIDATES = (
    "claude-sonnet-4.6",
    "claude-sonnet-4.6-20260415",
    "claude-sonnet-4.5",
    "claude-sonnet-4",
)
POLICY_REGIMES: dict[str, dict[str, Any]] = {
    "pre_pandemic_baseline": {"severity": 0.0, "label": "pre-pandemic baseline"},
    "first_lockdown": {"severity": 0.95, "label": "first confinement, March to May 2020"},
    "deconfinement_summer_2020": {"severity": 0.30, "label": "deconfinement, summer 2020"},
    "second_wave_restrictions": {"severity": 0.58, "label": "second-wave restrictions, fall 2020"},
    "curfew_winter_2020_2021": {"severity": 0.72, "label": "curfew and winter restrictions, 2020-2021"},
    "pass_sanitaire": {"severity": 0.44, "label": "pass sanitaire period, summer 2021"},
}


@dataclass(frozen=True, slots=True)
class BehavioralScore:
    profile_key: str
    policy_regime: str
    mobility_reduction: float
    social_distancing: float
    mask_adherence: float
    risk_perception: float
    trust_in_measures: float
    generation_mode: str
    prompt_version: str
    raw_response_excerpt: str


class LLMBehavioralAgent:
    def __init__(
        self,
        *,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        model: str = "claude-sonnet-4.6",
        fallback_models: tuple[str, ...] = DEFAULT_MODEL_CANDIDATES,
        base_url: str = DEFAULT_OMNIMART_BASE_URL,
        api_key_env: str = "OMNIMART_API_KEY",
        thinking: str = "low",
        request_pause_seconds: float = 0.8,
        timeout_seconds: int = 90,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.fallback_models = tuple(model_name for model_name in fallback_models if model_name)
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.thinking = thinking
        self.request_pause_seconds = float(request_pause_seconds)
        self.timeout_seconds = int(timeout_seconds)
        self._last_request_at = 0.0

    def generate(self, profile: SocioDemographicProfile, policy_regime: str, *, force_refresh: bool = False) -> BehavioralScore:
        if policy_regime not in POLICY_REGIMES:
            raise ValueError(f"Unsupported policy regime: {policy_regime}")
        cache_path = self.cache_dir / f"{profile.key}__{policy_regime}.json"
        if cache_path.exists() and not force_refresh:
            return BehavioralScore(**json.loads(cache_path.read_text(encoding="utf-8")))

        prompt = self.build_prompt(profile, policy_regime)
        payload, mode = self._call_model(profile, policy_regime, prompt)
        parsed = self._parse_score_payload(payload)
        score = BehavioralScore(
            profile_key=profile.key,
            policy_regime=policy_regime,
            mobility_reduction=_clip01(parsed["mobility_reduction"]),
            social_distancing=_clip01(parsed["social_distancing"]),
            mask_adherence=_clip01(parsed["mask_adherence"]),
            risk_perception=_clip01(parsed["risk_perception"]),
            trust_in_measures=_clip01(parsed["trust_in_measures"]),
            generation_mode=mode,
            prompt_version="v2_short_json_claude",
            raw_response_excerpt=str(payload)[:240],
        )
        cache_path.write_text(json.dumps(asdict(score), indent=2, ensure_ascii=False), encoding="utf-8")
        return score

    def build_prompt(self, profile: SocioDemographicProfile, policy_regime: str) -> str:
        regime = POLICY_REGIMES[policy_regime]
        settings = ", ".join(f"{name}:{weight:.2f}" for name, weight in sorted(profile.typical_settings.items()))
        return (
            "JSON only. "
            f"France, profile={profile.name}. "
            f"age={profile.age_range}; occupation={profile.occupation}; household={profile.household_type}. "
            f"settings={settings}. "
            f"vulnerability={profile.vulnerability_factors} "
            f"trust_proxy={profile.trust_proxy:.2f}; flex={profile.digital_flexibility:.2f}; mobility_constraint={profile.mobility_constraint:.2f}. "
            f"period={regime['label']}; severity={regime['severity']:.2f}. "
            "Return numbers in [0,1] for mobility_reduction, social_distancing, mask_adherence, risk_perception, trust_in_measures. "
            "Be plausible for France, keep social inequality visible only when justified, no stereotype, no explanation."
        )

    def _call_model(self, profile: SocioDemographicProfile, policy_regime: str, prompt: str) -> tuple[dict[str, Any], str]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            return self._heuristic_payload(profile, policy_regime), "heuristic_fallback:no_api_key"

        last_error: str | None = None
        for model_name in self._model_candidates():
            now = time.monotonic()
            wait_time = self.request_pause_seconds - (now - self._last_request_at)
            if wait_time > 0:
                time.sleep(wait_time)

            body = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a careful social-science coding assistant. Return one strict JSON object only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            }
            request = Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self._last_request_at = time.monotonic()
                message = _extract_message_content(payload)
                return self._parse_embedded_json(message), f"omnimart_chat_completion:{model_name}"
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {body[:240]}"
                if exc.code in {400, 404, 422}:
                    continue
                if exc.code in {429, 500, 502, 503, 504}:
                    time.sleep(min(3.0, self.request_pause_seconds + 1.0))
                    continue
            except (URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                continue

        mode = "heuristic_fallback_after_error"
        if last_error:
            mode = f"{mode}:{last_error[:80]}"
        return self._heuristic_payload(profile, policy_regime), mode

    def _model_candidates(self) -> tuple[str, ...]:
        seen: list[str] = []
        for name in (self.model, *self.fallback_models):
            if name and name not in seen:
                seen.append(name)
        return tuple(seen)

    def _heuristic_payload(self, profile: SocioDemographicProfile, policy_regime: str) -> dict[str, Any]:
        severity = float(POLICY_REGIMES[policy_regime]["severity"])
        trait_map = {
            "ouvrier": (0.84, 0.43, 0.97),
            "employe": (0.74, 0.49, 1.00),
            "cadre": (0.36, 0.66, 1.06),
            "profession_intermediaire": (0.58, 0.58, 1.02),
            "retraite": (0.40, 0.64, 1.08),
            "etudiant": (0.48, 0.48, 0.96),
            "inactive_au_foyer": (0.46, 0.51, 1.01),
            "artisan_commercant": (0.70, 0.42, 0.95),
            "agriculteur": (0.72, 0.48, 0.98),
            "chomeur": (0.40, 0.39, 0.94),
        }
        mobility_constraint, trust_proxy, prevention_multiplier = trait_map.get(
            profile.occupation,
            (profile.mobility_constraint, profile.trust_proxy, profile.preventive_behavior_multiplier),
        )
        age_bonus = 0.06 if "65" in profile.age_range or "75" in profile.age_range else 0.0
        home_bonus = 0.04 if profile.typical_settings.get("home", 0.0) >= 0.55 else 0.0
        work_bonus = 0.05 if profile.typical_settings.get("work", 0.0) >= 0.38 else 0.0
        school_bonus = 0.04 if profile.typical_settings.get("school", 0.0) >= 0.25 else 0.0

        mobility_reduction = _clip01(severity * (1.12 - 0.72 * mobility_constraint) + 0.03 * age_bonus - 0.02 * work_bonus)
        social_distancing = _clip01(0.16 + 0.70 * severity * prevention_multiplier + age_bonus + 0.02 * home_bonus)
        mask_adherence = _clip01(0.18 + 0.58 * severity + 0.24 * trust_proxy + 0.02 * school_bonus)
        risk_perception = _clip01(0.22 + 0.54 * severity + 0.16 * (1.0 - mobility_constraint) + age_bonus)
        trust_in_measures = _clip01(0.64 * trust_proxy + 0.18 * severity + 0.05)
        if policy_regime == "pass_sanitaire":
            mask_adherence = _clip01(mask_adherence + 0.05)
            trust_in_measures = _clip01(trust_in_measures - 0.04 * mobility_constraint)
        if policy_regime == "deconfinement_summer_2020":
            mobility_reduction = _clip01(mobility_reduction - 0.06)
            social_distancing = _clip01(social_distancing - 0.07)
        if profile.household_type in {"famille_monoparentale", "couple_avec_enfants", "chez_parents"}:
            mobility_reduction = _clip01(mobility_reduction - 0.02)
            risk_perception = _clip01(risk_perception + 0.02)
        return {
            "mobility_reduction": mobility_reduction,
            "social_distancing": social_distancing,
            "mask_adherence": mask_adherence,
            "risk_perception": risk_perception,
            "trust_in_measures": trust_in_measures,
        }

    def _parse_score_payload(self, payload: dict[str, Any]) -> dict[str, float]:
        required = {
            "mobility_reduction",
            "social_distancing",
            "mask_adherence",
            "risk_perception",
            "trust_in_measures",
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing keys in LLM payload: {sorted(missing)}")
        return {key: float(payload[key]) for key in required}

    def _parse_embedded_json(self, content: str) -> dict[str, Any]:
        return self._parse_score_payload(self._parse_embedded_json_loose(content))

    def _parse_embedded_json_loose(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))


def _extract_message_content(payload: dict[str, Any]) -> str:
    message = payload["choices"][0]["message"]["content"]
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(message)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
