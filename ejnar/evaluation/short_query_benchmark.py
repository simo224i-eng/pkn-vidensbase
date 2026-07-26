"""Datasæt- og poolingværktøjer til Ejnars korte praksissøgninger.

Modulet holder tre ting adskilt:

* behandlede, korte søgninger hvor Query Planner forventes at blive brugt;
* korte OOV/fallback-søgninger som ikke må forringes;
* præcisionsfølsomme guardrails som aldrig må ændres.

Kandidatpuljer kan blindes deterministisk, så relevans ikke bedømmes ud fra
systemnavn eller placering. En AI-bedømt pulje skal fortsat kaldes ``silver``;
``gold`` forudsætter juridisk menneskevalidering.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from .metrics import EvaluationCase

try:
    from query_planner import MAX_PLANNABLE_TOKENS, plan_query
except ImportError:
    from ejnar.query_planner import MAX_PLANNABLE_TOKENS, plan_query


TREATED_COHORT = "treated"
FALLBACK_COHORT = "fallback"
GUARDRAIL_COHORT = "guardrail"
VALID_COHORTS = {TREATED_COHORT, FALLBACK_COHORT, GUARDRAIL_COHORT}
VALID_VARIANTS = {"A", "B", "single"}
VALID_SPLITS = {"development", "validation", "holdout", "guardrail"}
VALID_PLANNER_POLICIES = {"eligible", "fallback", "forbidden"}
_TOKEN_RE = re.compile(r"[a-zæøå0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class ShortQuerySpec:
    question_id: str
    topic_id: str
    variant: str
    query: str
    intent: str
    category: str
    cohort: str
    split: str
    information_need: str
    inclusion_criteria: str
    exclusion_criteria: str
    planner_policy: str
    notes: str = ""

    def to_evaluation_case(self) -> EvaluationCase:
        return EvaluationCase(
            question_id=self.question_id,
            query=self.query,
            intent=self.intent,
            expected_decision_ids=(),
            expected_terms=(),
            expected_phrase="",
            notes=self.notes,
        )


def token_count(query: str) -> int:
    return len(_TOKEN_RE.findall(query or ""))


def load_specs(path: str | Path) -> list[ShortQuerySpec]:
    specs: list[ShortQuerySpec] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            question_id = str(row.get("question_id") or "").strip()
            query = str(row.get("query") or "").strip()
            if not question_id and not query:
                continue
            if not question_id or not query:
                raise ValueError(
                    f"Række {row_number} mangler question_id eller query"
                )
            specs.append(
                ShortQuerySpec(
                    question_id=question_id,
                    topic_id=str(row.get("topic_id") or "").strip(),
                    variant=str(row.get("variant") or "").strip(),
                    query=query,
                    intent=str(row.get("intent") or "").strip(),
                    category=str(row.get("category") or "").strip(),
                    cohort=str(row.get("cohort") or "").strip(),
                    split=str(row.get("split") or "").strip(),
                    information_need=str(
                        row.get("information_need") or ""
                    ).strip(),
                    inclusion_criteria=str(
                        row.get("inclusion_criteria") or ""
                    ).strip(),
                    exclusion_criteria=str(
                        row.get("exclusion_criteria") or ""
                    ).strip(),
                    planner_policy=str(
                        row.get("planner_policy") or ""
                    ).strip(),
                    notes=str(row.get("notes") or "").strip(),
                )
            )
    return specs


def validate_specs(
    specs: Sequence[ShortQuerySpec],
    *,
    minimum_treated_cohort_size: int = 1,
) -> dict[str, Any]:
    """Validér integritet og at ``planner_expected`` svarer til runtime."""
    errors: list[str] = []
    ids = [item.question_id for item in specs]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"Dublerede question_id: {', '.join(duplicates)}")

    treated_topics: dict[str, list[ShortQuerySpec]] = {}
    category_counts: dict[str, int] = {}
    cohort_counts: dict[str, int] = {}
    planner_applications = 0
    for spec in specs:
        if spec.cohort not in VALID_COHORTS:
            errors.append(
                f"{spec.question_id}: ukendt cohort {spec.cohort!r}"
            )
        if spec.variant not in VALID_VARIANTS:
            errors.append(
                f"{spec.question_id}: ukendt variant {spec.variant!r}"
            )
        if spec.split not in VALID_SPLITS:
            errors.append(
                f"{spec.question_id}: ukendt split {spec.split!r}"
            )
        if spec.planner_policy not in VALID_PLANNER_POLICIES:
            errors.append(
                f"{spec.question_id}: ukendt planner_policy "
                f"{spec.planner_policy!r}"
            )
        if not spec.topic_id:
            errors.append(f"{spec.question_id}: topic_id mangler")
        if not spec.category:
            errors.append(f"{spec.question_id}: category mangler")
        if not spec.information_need:
            errors.append(f"{spec.question_id}: information_need mangler")

        count = token_count(spec.query)
        if spec.cohort in {TREATED_COHORT, FALLBACK_COHORT} and not (
            1 <= count <= MAX_PLANNABLE_TOKENS
        ):
            errors.append(
                f"{spec.question_id}: {spec.cohort}-query har {count} tokens"
            )

        plan = plan_query(spec.query)
        if spec.intent != plan.intent.value:
            errors.append(
                f"{spec.question_id}: declared intent {spec.intent!r}, "
                f"men runtime registrerer {plan.intent.value!r}"
            )
        if plan.applied:
            planner_applications += 1
        if spec.cohort == TREATED_COHORT and spec.planner_policy != "eligible":
            errors.append(
                f"{spec.question_id}: treated-query skal være eligible"
            )
        expected_control_policy = {
            FALLBACK_COHORT: "fallback",
            GUARDRAIL_COHORT: "forbidden",
        }.get(spec.cohort)
        if expected_control_policy and spec.planner_policy != expected_control_policy:
            errors.append(
                f"{spec.question_id}: {spec.cohort} skal have policy "
                f"{expected_control_policy}"
            )
        if spec.planner_policy in {"fallback", "forbidden"} and plan.applied:
            errors.append(
                f"{spec.question_id}: kontrol-query aktiverede planneren"
            )
        if (
            spec.planner_policy == "fallback"
            and plan.skipped_reason != "no_known_concepts"
        ):
            errors.append(
                f"{spec.question_id}: fallback skal være no_known_concepts, "
                f"ikke {plan.skipped_reason!r}"
            )
        if (
            spec.planner_policy == "forbidden"
            and plan.skipped_reason
            not in {"precision_sensitive_intent", "informative_query_preserved"}
        ):
            errors.append(
                f"{spec.question_id}: forbidden-query har uventet skip-årsag "
                f"{plan.skipped_reason!r}"
            )

        if spec.cohort == TREATED_COHORT:
            treated_topics.setdefault(spec.topic_id, []).append(spec)
        category_counts[spec.category] = category_counts.get(spec.category, 0) + 1
        cohort_counts[spec.cohort] = cohort_counts.get(spec.cohort, 0) + 1

    treated_count = cohort_counts.get(TREATED_COHORT, 0)
    if treated_count < max(0, minimum_treated_cohort_size):
        errors.append(
            f"Kun {treated_count} behandlede queries; kræver mindst "
            f"{max(0, minimum_treated_cohort_size)}"
        )
    for topic_id, variants in sorted(treated_topics.items()):
        names = {item.variant for item in variants}
        if names != {"A", "B"} or len(variants) != 2:
            errors.append(
                f"{topic_id}: treated-topic skal have præcis variant A og B"
            )

    if errors:
        raise ValueError("\n".join(errors))
    return {
        "questions": len(specs),
        "topics": len({item.topic_id for item in specs}),
        "treated_topics": len(treated_topics),
        "planner_applications": planner_applications,
        "cohorts": dict(sorted(cohort_counts.items())),
        "categories": dict(sorted(category_counts.items())),
    }


def canonical_specs_payload(specs: Sequence[ShortQuerySpec]) -> str:
    rows = [
        {
            "question_id": item.question_id,
            "topic_id": item.topic_id,
            "variant": item.variant,
            "query": item.query,
            "intent": item.intent,
            "category": item.category,
            "cohort": item.cohort,
            "split": item.split,
            "information_need": item.information_need,
            "inclusion_criteria": item.inclusion_criteria,
            "exclusion_criteria": item.exclusion_criteria,
            "planner_policy": item.planner_policy,
            "notes": item.notes,
        }
        for item in sorted(specs, key=lambda value: value.question_id)
    ]
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def specs_sha256(specs: Sequence[ShortQuerySpec]) -> str:
    return hashlib.sha256(
        canonical_specs_payload(specs).encode("utf-8")
    ).hexdigest()


def query_hashes(specs: Sequence[ShortQuerySpec]) -> dict[str, str]:
    return {
        item.question_id: hashlib.sha256(item.query.encode("utf-8")).hexdigest()
        for item in sorted(specs, key=lambda value: value.question_id)
    }


def _result_identity(result: Mapping[str, Any]) -> str:
    for key in (
        "Sagsnummer",
        "decision_id",
        "case_number",
        "Link",
        "link",
        "url",
    ):
        value = str(result.get(key) or "").strip().casefold()
        if value:
            return value
    title = str(result.get("Titel") or result.get("title") or "").strip()
    text = str(result.get("Tekst") or result.get("text") or "").strip()
    if not title and not text:
        return ""
    return hashlib.sha256(f"{title}\n{text}".encode("utf-8")).hexdigest()


def _payloads_by_id(
    payloads: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("question_id") or "").strip(): item
        for item in payloads
        if str(item.get("question_id") or "").strip()
    }


def build_blind_pool(
    specs: Sequence[ShortQuerySpec],
    systems: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    pool_depth: int = 30,
    seed: str = "ejnar-short-query-v1",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Byg blind bedømmelsespulje og separat provenance for flere systemer."""
    indexed = {
        system: _payloads_by_id(payloads)
        for system, payloads in systems.items()
    }
    blind_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    for spec in specs:
        candidates: dict[str, dict[str, Any]] = {}
        sources: dict[str, list[dict[str, Any]]] = {}
        for system, payload_by_id in indexed.items():
            payload = payload_by_id.get(spec.question_id) or {}
            for rank, result in enumerate(
                (payload.get("results") or [])[: max(1, pool_depth)],
                start=1,
            ):
                if not isinstance(result, Mapping):
                    continue
                identity = _result_identity(result)
                if not identity:
                    continue
                candidates.setdefault(identity, dict(result))
                sources.setdefault(identity, []).append(
                    {"system": system, "rank": rank}
                )

        ordered = sorted(
            candidates,
            key=lambda identity: hashlib.sha256(
                f"{seed}:{spec.question_id}:{identity}".encode("utf-8")
            ).hexdigest(),
        )
        for position, identity in enumerate(ordered, start=1):
            result = candidates[identity]
            identity_digest = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:12]
            judgment_id = f"{spec.question_id}-{identity_digest}"
            blind_rows.append(
                {
                    "judgment_id": judgment_id,
                    "blind_order": position,
                    "question_id": spec.question_id,
                    "query": spec.query,
                    "information_need": spec.information_need,
                    "inclusion_criteria": spec.inclusion_criteria,
                    "exclusion_criteria": spec.exclusion_criteria,
                    "case_number": str(result.get("Sagsnummer") or ""),
                    "title": str(result.get("Titel") or ""),
                    "text": str(result.get("Tekst") or ""),
                    "link": str(result.get("Link") or ""),
                }
            )
            provenance_rows.append(
                {
                    "judgment_id": judgment_id,
                    "question_id": spec.question_id,
                    "candidate_identity": identity,
                    "sources": sources.get(identity) or [],
                }
            )
    return blind_rows, provenance_rows


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
