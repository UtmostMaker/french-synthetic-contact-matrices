from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml

from .agent_profiles import SocioDemographicProfile
from .llm_behavioral_agent import POLICY_REGIMES


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "artifacts" / "cache" / "llm_shs_agent"
DEFAULT_AUDIT_DIR = REPO_ROOT / "artifacts" / "audits" / "exp007_shs_llm"
DEFAULT_PROTOCOL_PATH = REPO_ROOT / "experiments" / "protocols" / "exp007_shs_llm_protocol_v2.yaml"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL_CANDIDATES = (
    "openai/gpt-5.4-mini",
    "openai/gpt-5-mini",
)


@dataclass(frozen=True, slots=True)
class PromptBundle:
    protocol_id: str
    prompt_version: str
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]
    prompt_hash: str


@dataclass(frozen=True, slots=True)
class SHSBehavioralScore:
    profile_key: str
    policy_regime: str
    adherence_level: float
    risk_perception: float
    trust_in_authorities: float
    mobility_reduction: float
    compliance_capacity: float
    economic_constraint: float
    social_pressure: float
    household_pressure: float
    policy_fatigue: float
    mask_adherence: float
    isolation_propensity: float
    generation_mode: str
    protocol_id: str
    prompt_version: str
    prompt_hash: str
    audit_path: str
    raw_response_excerpt: str


class SHSLLMBehavioralAgent:
    def __init__(
        self,
        *,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        audit_dir: str | Path = DEFAULT_AUDIT_DIR,
        protocol_path: str | Path = DEFAULT_PROTOCOL_PATH,
        backend: str = "openai_compatible",
        model: str = DEFAULT_MODEL_CANDIDATES[0],
        fallback_models: tuple[str, ...] = DEFAULT_MODEL_CANDIDATES[1:],
        base_url: str = DEFAULT_BASE_URL,
        api_key_env: str = "OPENROUTER_API_KEY",
        provider_label: str = "OpenRouter",
        temperature: float = 0.2,
        max_tokens: int = 280,
        request_pause_seconds: float = 0.8,
        timeout_seconds: int = 90,
        abort_on_fallback: bool = False,
        abort_on_auth_error: bool = True,
        cli_command: str = "claude",
        cli_max_budget_usd: float | None = None,
        cli_permission_mode: str = "bypassPermissions",
        cli_output_format: str = "json",
        cli_tools: str | None = "",
        auto_wait_on_rate_limit: bool = True,
        rate_limit_reset_buffer_seconds: int = 20,
        rate_limit_poll_seconds: int = 30,
        rate_limit_max_wait_seconds: int = 6 * 3600,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.protocol_path = Path(protocol_path)
        self.protocol = _load_protocol(self.protocol_path)
        self.backend = str(backend)
        self.model = model
        self.fallback_models = tuple(model_name for model_name in fallback_models if model_name)
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.provider_label = provider_label
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.request_pause_seconds = float(request_pause_seconds)
        self.timeout_seconds = int(timeout_seconds)
        self.abort_on_fallback = bool(abort_on_fallback)
        self.abort_on_auth_error = bool(abort_on_auth_error)
        self.cli_command = str(cli_command)
        self.cli_max_budget_usd = cli_max_budget_usd if cli_max_budget_usd is None else float(cli_max_budget_usd)
        self.cli_permission_mode = str(cli_permission_mode)
        self.cli_output_format = str(cli_output_format)
        self.cli_tools = cli_tools
        self.auto_wait_on_rate_limit = bool(auto_wait_on_rate_limit)
        self.rate_limit_reset_buffer_seconds = int(rate_limit_reset_buffer_seconds)
        self.rate_limit_poll_seconds = max(5, int(rate_limit_poll_seconds))
        self.rate_limit_max_wait_seconds = max(0, int(rate_limit_max_wait_seconds))
        self._last_request_at = 0.0

    def generate(self, profile: SocioDemographicProfile, policy_regime: str, *, force_refresh: bool = False) -> SHSBehavioralScore:
        if policy_regime not in POLICY_REGIMES:
            raise ValueError(f"Unsupported policy regime: {policy_regime}")

        bundle = self.build_prompt_bundle(profile, policy_regime)
        cache_path = self._cache_path(profile.key, policy_regime, bundle)
        if cache_path.exists() and not force_refresh:
            cached = SHSBehavioralScore(**json.loads(cache_path.read_text(encoding="utf-8")))
            cache_is_compatible = (
                cached.prompt_version == bundle.prompt_version
                and cached.protocol_id == bundle.protocol_id
                and cached.prompt_hash == bundle.prompt_hash
            )
            if cache_is_compatible and not (self.abort_on_fallback and _is_fallback_mode(cached.generation_mode)):
                return cached

        payload, mode, raw_response, audit_metadata = self._call_model(profile, policy_regime, bundle)
        parsed = self._parse_score_payload(payload)
        audit_path = self._write_audit_record(profile, policy_regime, bundle, parsed, raw_response, mode, audit_metadata)
        score = SHSBehavioralScore(
            profile_key=profile.key,
            policy_regime=policy_regime,
            adherence_level=_clip01(parsed["adherence_level"]),
            risk_perception=_clip01(parsed["risk_perception"]),
            trust_in_authorities=_clip01(parsed["trust_in_authorities"]),
            mobility_reduction=_clip01(parsed["mobility_reduction"]),
            compliance_capacity=_clip01(parsed["compliance_capacity"]),
            economic_constraint=_clip01(parsed["economic_constraint"]),
            social_pressure=_clip01(parsed["social_pressure"]),
            household_pressure=_clip01(parsed["household_pressure"]),
            policy_fatigue=_clip01(parsed["policy_fatigue"]),
            mask_adherence=_clip01(parsed["mask_adherence"]),
            isolation_propensity=_clip01(parsed["isolation_propensity"]),
            generation_mode=mode,
            protocol_id=bundle.protocol_id,
            prompt_version=bundle.prompt_version,
            prompt_hash=bundle.prompt_hash,
            audit_path=str(audit_path.relative_to(REPO_ROOT)),
            raw_response_excerpt=str(raw_response)[:320],
        )
        cache_path.write_text(json.dumps(asdict(score), indent=2, ensure_ascii=False), encoding="utf-8")
        return score

    def generate_heuristic(self, profile: SocioDemographicProfile, policy_regime: str) -> SHSBehavioralScore:
        bundle = self.build_prompt_bundle(profile, policy_regime)
        payload = self._heuristic_payload(profile, policy_regime)
        parsed = self._parse_score_payload(payload)
        return SHSBehavioralScore(
            profile_key=profile.key,
            policy_regime=policy_regime,
            adherence_level=_clip01(parsed["adherence_level"]),
            risk_perception=_clip01(parsed["risk_perception"]),
            trust_in_authorities=_clip01(parsed["trust_in_authorities"]),
            mobility_reduction=_clip01(parsed["mobility_reduction"]),
            compliance_capacity=_clip01(parsed["compliance_capacity"]),
            economic_constraint=_clip01(parsed["economic_constraint"]),
            social_pressure=_clip01(parsed["social_pressure"]),
            household_pressure=_clip01(parsed["household_pressure"]),
            policy_fatigue=_clip01(parsed["policy_fatigue"]),
            mask_adherence=_clip01(parsed["mask_adherence"]),
            isolation_propensity=_clip01(parsed["isolation_propensity"]),
            generation_mode="profile_heuristic",
            protocol_id=bundle.protocol_id,
            prompt_version=bundle.prompt_version,
            prompt_hash=bundle.prompt_hash,
            audit_path="",
            raw_response_excerpt=str(payload)[:320],
        )

    def build_prompt_bundle(self, profile: SocioDemographicProfile, policy_regime: str) -> PromptBundle:
        regime = POLICY_REGIMES[policy_regime]
        protocol_id = str(self.protocol["protocol_id"])
        prompt_version = str(self.protocol["prompt_version"])
        settings = ", ".join(f"{name}:{weight:.2f}" for name, weight in sorted(profile.typical_settings.items()))
        variable_rubric_block = _render_variable_rubric(dict(self.protocol["latent_variables"]))
        user_prompt = str(self.protocol["user_prompt_template"]).format(
            protocol_id=protocol_id,
            prompt_version=prompt_version,
            research_objective=str(self.protocol["research_objective"]),
            scientific_rationale_block=_render_list_block(list(self.protocol.get("scientific_rationale", []))),
            scoring_principles_block=_render_list_block(list(self.protocol.get("scoring_principles", []))),
            anti_bias_rules_block=_render_list_block(list(self.protocol.get("anti_bias_rules", []))),
            profile_label=profile.display_label,
            age_range=profile.age_range,
            occupation=profile.occupation,
            household_type=profile.household_type,
            settings=settings,
            vulnerability_factors=profile.vulnerability_factors,
            trust_proxy=f"{profile.trust_proxy:.2f}",
            preventive_multiplier=f"{profile.preventive_behavior_multiplier:.2f}",
            mobility_constraint=f"{profile.mobility_constraint:.2f}",
            digital_flexibility=f"{profile.digital_flexibility:.2f}",
            policy_regime=policy_regime,
            policy_label=str(regime["label"]),
            policy_severity=f"{float(regime['severity']):.2f}",
            variable_rubric_block=variable_rubric_block,
        )
        system_prompt = str(self.protocol["system_prompt_template"])
        response_schema = dict(self.protocol["response_schema"])
        prompt_hash = hashlib.sha256(f"{system_prompt}\n\n{user_prompt}".encode("utf-8")).hexdigest()[:16]
        return PromptBundle(
            protocol_id=protocol_id,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            prompt_hash=prompt_hash,
        )

    def protocol_metadata(self) -> dict[str, Any]:
        return {
            "protocol_id": str(self.protocol["protocol_id"]),
            "prompt_version": str(self.protocol["prompt_version"]),
            "protocol_path": str(self.protocol_path.relative_to(REPO_ROOT)),
            "audit_dir": str(self.audit_dir.relative_to(REPO_ROOT)),
            "backend": self.backend,
            "auto_wait_on_rate_limit": self.auto_wait_on_rate_limit,
            "rate_limit_reset_buffer_seconds": self.rate_limit_reset_buffer_seconds,
            "rate_limit_poll_seconds": self.rate_limit_poll_seconds,
            "rate_limit_max_wait_seconds": self.rate_limit_max_wait_seconds,
            "response_schema": dict(self.protocol["response_schema"]),
        }

    def _call_model(
        self,
        profile: SocioDemographicProfile,
        policy_regime: str,
        bundle: PromptBundle,
    ) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        if self.backend == "claude_cli":
            return self._call_claude_cli(bundle)
        return self._call_openai_compatible(profile, policy_regime, bundle)

    def _call_claude_cli(self, bundle: PromptBundle) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        last_error: str | None = None
        for model_name in self._model_candidates():
            while True:
                now = time.monotonic()
                wait_time = self.request_pause_seconds - (now - self._last_request_at)
                if wait_time > 0:
                    time.sleep(wait_time)

                command = [
                    self.cli_command,
                    "--permission-mode",
                    self.cli_permission_mode,
                    "--print",
                    "--model",
                    model_name,
                    "--system-prompt",
                    bundle.system_prompt,
                    "--output-format",
                    self.cli_output_format,
                    "--json-schema",
                    json.dumps(bundle.response_schema, ensure_ascii=False),
                    "--no-session-persistence",
                    "--disable-slash-commands",
                ]
                if self.cli_tools:
                    command.extend(["--tools", self.cli_tools])
                command.append(bundle.user_prompt)
                if self.cli_max_budget_usd is not None:
                    command.extend(["--max-budget-usd", f"{self.cli_max_budget_usd:.4f}"])

                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    last_error = f"claude_cli timeout after {self.timeout_seconds}s"
                    if self.abort_on_auth_error:
                        raise RuntimeError(last_error) from exc
                    break

                stdout = completed.stdout.strip()
                stderr = completed.stderr.strip()
                raw_response = stdout or stderr
                payload = _try_parse_json(stdout) or _try_parse_json(stderr)

                rate_limit_plan = _extract_claude_rate_limit_plan(payload, raw_response)
                if rate_limit_plan and self.auto_wait_on_rate_limit:
                    self._wait_for_claude_rate_limit(rate_limit_plan, model_name)
                    last_error = rate_limit_plan["message"]
                    continue

                if completed.returncode != 0:
                    last_error = stderr or stdout or f"claude_cli exited with code {completed.returncode}"
                    if self.abort_on_auth_error:
                        raise RuntimeError(last_error)
                    break

                if not isinstance(payload, dict):
                    last_error = f"claude_cli invalid json: {stdout[:240]}"
                    if self.abort_on_auth_error:
                        raise RuntimeError(last_error)
                    break

                self._last_request_at = time.monotonic()
                structured_output = payload.get("structured_output")
                if payload.get("is_error"):
                    last_error = raw_response or "claude_cli returned error payload"
                    if self.abort_on_auth_error:
                        raise RuntimeError(last_error)
                    break
                if not isinstance(structured_output, dict):
                    last_error = f"claude_cli missing structured_output: {stdout[:240]}"
                    if self.abort_on_auth_error:
                        raise RuntimeError(last_error)
                    break

                metadata = {
                    "provider": "claude_cli",
                    "model": model_name,
                    "command": _redact_command(command),
                    "usage": payload.get("usage", {}),
                    "modelUsage": payload.get("modelUsage", {}),
                    "session_id": payload.get("session_id"),
                    "total_cost_usd": payload.get("total_cost_usd"),
                    "duration_ms": payload.get("duration_ms"),
                }
                return structured_output, f"claude_cli:{model_name}", raw_response, metadata

        if self.abort_on_fallback:
            raise RuntimeError(last_error or "Claude CLI failed and fallback is disabled")
        mode = "heuristic_fallback_after_error"
        if last_error:
            mode = f"{mode}:{last_error[:80]}"
        return {}, mode, last_error or "", {"provider": "claude_cli", "error": last_error}

    def _wait_for_claude_rate_limit(self, plan: dict[str, Any], model_name: str) -> None:
        wait_seconds = int(plan["wait_seconds"]) + self.rate_limit_reset_buffer_seconds
        if self.rate_limit_max_wait_seconds and wait_seconds > self.rate_limit_max_wait_seconds:
            raise RuntimeError(
                f"claude_cli rate limit wait {wait_seconds}s exceeds configured max {self.rate_limit_max_wait_seconds}s"
            )

        reset_at = datetime.fromisoformat(str(plan["reset_at_iso"])) + timedelta(seconds=self.rate_limit_reset_buffer_seconds)
        reset_label = reset_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        print(
            f"[claude_cli] limit hit for model={model_name}. Waiting {wait_seconds}s until {reset_label}.",
            flush=True,
        )
        remaining = wait_seconds
        while remaining > 0:
            chunk = min(self.rate_limit_poll_seconds, remaining)
            print(
                f"[claude_cli] resume countdown for model={model_name}: {remaining}s remaining",
                flush=True,
            )
            time.sleep(chunk)
            remaining -= chunk
        print(f"[claude_cli] retrying model={model_name} now.", flush=True)

    def _call_openai_compatible(
        self,
        profile: SocioDemographicProfile,
        policy_regime: str,
        bundle: PromptBundle,
    ) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            if self.abort_on_fallback:
                raise RuntimeError(f"Missing API key env: {self.api_key_env}")
            return self._heuristic_payload(profile, policy_regime), "heuristic_fallback:no_api_key", "", {"provider": self.provider_label}

        last_error: str | None = None
        for model_name in self._model_candidates():
            now = time.monotonic()
            wait_time = self.request_pause_seconds - (now - self._last_request_at)
            if wait_time > 0:
                time.sleep(wait_time)

            body = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": bundle.system_prompt},
                    {"role": "user", "content": bundle.user_prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if "openrouter.ai" in self.base_url:
                headers["HTTP-Referer"] = "https://openclaw.local"
                headers["X-Title"] = "French synthetic contact matrices"
            request = Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self._last_request_at = time.monotonic()
                message = _extract_message_content(payload)
                return self._parse_embedded_json(message), f"chat_completion:{self.provider_label}:{model_name}", message, {
                    "provider": self.provider_label,
                    "model": model_name,
                    "response_id": payload.get("id"),
                    "usage": payload.get("usage", {}),
                }
            except HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {body_text[:240]}"
                if exc.code in {401, 402, 403} and self.abort_on_auth_error:
                    raise RuntimeError(last_error) from exc
                if exc.code in {400, 404, 422}:
                    continue
                if exc.code in {429, 500, 502, 503, 504}:
                    time.sleep(min(3.0, self.request_pause_seconds + 1.0))
                    continue
            except (URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                continue

        if self.abort_on_fallback:
            raise RuntimeError(last_error or "Model calls failed and fallback is disabled")
        mode = "heuristic_fallback_after_error"
        if last_error:
            mode = f"{mode}:{last_error[:80]}"
        return self._heuristic_payload(profile, policy_regime), mode, last_error or "", {"provider": self.provider_label, "error": last_error}

    def _model_candidates(self) -> tuple[str, ...]:
        seen: list[str] = []
        for name in (self.model, *self.fallback_models):
            if name and name not in seen:
                seen.append(name)
        return tuple(seen)

    def _cache_path(self, profile_key: str, policy_regime: str, bundle: PromptBundle) -> Path:
        return self.cache_dir / f"{profile_key}__{policy_regime}__{bundle.prompt_hash}.json"

    def _write_audit_record(
        self,
        profile: SocioDemographicProfile,
        policy_regime: str,
        bundle: PromptBundle,
        parsed_payload: dict[str, float],
        raw_response: str,
        generation_mode: str,
        metadata: dict[str, Any],
    ) -> Path:
        audit_path = self.audit_dir / f"{profile.key}__{policy_regime}__{bundle.prompt_hash}.json"
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "profile_key": profile.key,
            "policy_regime": policy_regime,
            "generation_mode": generation_mode,
            "protocol_id": bundle.protocol_id,
            "prompt_version": bundle.prompt_version,
            "prompt_hash": bundle.prompt_hash,
            "system_prompt": bundle.system_prompt,
            "user_prompt": bundle.user_prompt,
            "response_schema": bundle.response_schema,
            "raw_response": raw_response,
            "parsed_payload": parsed_payload,
            "backend_metadata": metadata,
        }
        audit_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return audit_path

    def _heuristic_payload(self, profile: SocioDemographicProfile, policy_regime: str) -> dict[str, float]:
        severity = float(POLICY_REGIMES[policy_regime]["severity"])
        age_senior = 1.0 if any(token in profile.age_range for token in ("65", "75")) else 0.0
        student_bonus = 1.0 if profile.occupation == "etudiant" else 0.0
        childload_bonus = 1.0 if profile.household_type in {"famille_monoparentale", "couple_avec_enfants", "chez_parents"} else 0.0
        work_presentiel = float(profile.typical_settings.get("work", 0.0))
        other_social = float(profile.typical_settings.get("other", 0.0))
        home_load = float(profile.typical_settings.get("home", 0.0))

        compliance_capacity = _clip01(0.55 + 0.35 * profile.digital_flexibility - 0.30 * profile.mobility_constraint - 0.08 * childload_bonus)
        economic_constraint = _clip01(0.20 + 0.55 * profile.mobility_constraint + 0.15 * work_presentiel + 0.08 * (1.0 - profile.digital_flexibility))
        social_pressure = _clip01(0.18 + 0.45 * other_social + 0.14 * student_bonus + 0.08 * (1.0 - severity))
        household_pressure = _clip01(0.18 + 0.38 * home_load + 0.22 * childload_bonus)
        policy_fatigue = _clip01(0.05 + 0.55 * max(0.0, severity - 0.35) + 0.18 * social_pressure + 0.10 * economic_constraint)

        adherence_level = _clip01(
            0.10
            + 0.34 * severity
            + 0.20 * profile.preventive_behavior_multiplier
            + 0.20 * profile.trust_proxy
            + 0.12 * compliance_capacity
            - 0.16 * policy_fatigue
        )
        risk_perception = _clip01(0.16 + 0.44 * severity + 0.18 * age_senior + 0.12 * (1.0 - profile.mobility_constraint))
        trust_in_authorities = _clip01(0.62 * profile.trust_proxy + 0.16 * severity + 0.08 * compliance_capacity - 0.10 * policy_fatigue)
        mobility_reduction = _clip01(0.06 + 0.78 * severity + 0.10 * compliance_capacity - 0.32 * economic_constraint - 0.12 * social_pressure)
        mask_adherence = _clip01(0.12 + 0.52 * severity + 0.18 * trust_in_authorities + 0.10 * risk_perception - 0.08 * policy_fatigue)
        isolation_propensity = _clip01(0.10 + 0.28 * adherence_level + 0.24 * risk_perception + 0.10 * compliance_capacity - 0.14 * economic_constraint)

        if policy_regime == "deconfinement_summer_2020":
            mobility_reduction = _clip01(mobility_reduction - 0.10)
            adherence_level = _clip01(adherence_level - 0.07)
            mask_adherence = _clip01(mask_adherence - 0.04)
        elif policy_regime == "pass_sanitaire":
            mask_adherence = _clip01(mask_adherence + 0.08)
            trust_in_authorities = _clip01(trust_in_authorities - 0.04 * economic_constraint)
            policy_fatigue = _clip01(policy_fatigue + 0.06)

        return {
            "adherence_level": adherence_level,
            "risk_perception": risk_perception,
            "trust_in_authorities": trust_in_authorities,
            "mobility_reduction": mobility_reduction,
            "compliance_capacity": compliance_capacity,
            "economic_constraint": economic_constraint,
            "social_pressure": social_pressure,
            "household_pressure": household_pressure,
            "policy_fatigue": policy_fatigue,
            "mask_adherence": mask_adherence,
            "isolation_propensity": isolation_propensity,
        }

    def _parse_score_payload(self, payload: dict[str, Any]) -> dict[str, float]:
        required = {
            "adherence_level",
            "risk_perception",
            "trust_in_authorities",
            "mobility_reduction",
            "compliance_capacity",
            "economic_constraint",
            "social_pressure",
            "household_pressure",
            "policy_fatigue",
            "mask_adherence",
            "isolation_propensity",
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing keys in SHS payload: {sorted(missing)}")
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


def _load_protocol(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Protocol file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError(f"Protocol file is empty or malformed: {path}")
    return data


def _render_list_block(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_variable_rubric(latent_variables: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    for key, spec in latent_variables.items():
        lines.extend(
            [
                f"- {key}",
                f"  definition: {spec['definition']}",
                f"  anchor_0: {spec['anchor_0']}",
                f"  anchor_05: {spec['anchor_05']}",
                f"  anchor_1: {spec['anchor_1']}",
            ]
        )
    return "\n".join(lines)


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


def _try_parse_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_claude_rate_limit_plan(payload: dict[str, Any] | None, raw_response: str) -> dict[str, Any] | None:
    message_parts: list[str] = []
    if isinstance(payload, dict):
        if payload.get("api_error_status") == 429:
            message_parts.append(str(payload.get("result", "")))
        errors = payload.get("errors")
        if isinstance(errors, list):
            message_parts.extend(str(item) for item in errors)
    if raw_response:
        message_parts.append(raw_response)
    message = "\n".join(part for part in message_parts if part).strip()
    lowered = message.lower()
    if "hit your limit" not in lowered and "api_error_status\":429" not in lowered and "rate limit" not in lowered:
        return None

    reset_at = _parse_reset_datetime(message)
    if reset_at is None:
        return None
    wait_seconds = max(1, int((reset_at - datetime.now(timezone.utc)).total_seconds()))
    return {
        "message": message,
        "reset_at_iso": reset_at.isoformat(),
        "wait_seconds": wait_seconds,
    }


def _parse_reset_datetime(message: str) -> datetime | None:
    match = re.search(
        r"resets?\s+(?:at\s+)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>[ap]m)?(?:\s*\((?P<tz>[^)]+)\))?",
        message,
        re.IGNORECASE,
    )
    if not match:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").lower()
    timezone_name = (match.group("tz") or "Europe/Paris").strip()

    if ampm:
        hour = hour % 12
        if ampm == "pm":
            hour += 12
    if hour > 23 or minute > 59:
        return None

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = datetime.now().astimezone().tzinfo or timezone.utc

    now_local = datetime.now(tz)
    reset_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if reset_local <= now_local:
        reset_local += timedelta(days=1)
    return reset_local.astimezone(timezone.utc)


def _is_fallback_mode(mode: str) -> bool:
    lowered = str(mode).lower()
    return "fallback" in lowered or lowered == "profile_heuristic"


def _redact_command(command: list[str]) -> list[str]:
    return [item if len(item) < 400 else item[:397] + "..." for item in command]


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
