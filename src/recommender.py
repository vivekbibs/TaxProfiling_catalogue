"""Refactored recommendation engine.

The original logic lived inside catalogue_utils.py. This module splits the
concerns into smaller helpers so users can tweak matching rules without
rewriting the whole recommender.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .catalogue_utils import (
        TAXON_IRI,
        SAMPLE_FILTER,
        _flag_true,
        _release_as_int,
        _score_db_entry,
        _to_list,
        db_scope,
    )
    from .recommender_config import PREFERENCE_ALIASES, SCORE_WEIGHTS
except ImportError:  # pragma: no cover - fallback for direct execution
    from catalogue_utils import (
        TAXON_IRI,
        SAMPLE_FILTER,
        _flag_true,
        _release_as_int,
        _score_db_entry,
        _to_list,
        db_scope,
    )
    from recommender_config import PREFERENCE_ALIASES, SCORE_WEIGHTS


@dataclass
class RecommendationContext:
    envo_key: str | None
    host_key: str | None
    selected_orgs: list[str]
    reads_key: str
    pref_taxo: str
    wants_strain: bool
    wants_func: bool
    max_ram: int

    @property
    def wants_virus(self) -> bool:
        return "Virus" in self.selected_orgs

    @property
    def wants_fungi(self) -> bool:
        return "Fungi" in self.selected_orgs

    @property
    def wants_euk(self) -> bool:
        return "Eukaryota" in self.selected_orgs

    @property
    def wants_bacteria(self) -> bool:
        return "Bacteria" in self.selected_orgs

    @property
    def wants_archaea(self) -> bool:
        return "Archaea" in self.selected_orgs

    @property
    def taxon_keys(self) -> list[str]:
        return [TAXON_IRI[o] for o in self.selected_orgs]


def _normalize_pref(pref_taxo: str | None) -> str:
    if pref_taxo is None:
        return "any"
    return PREFERENCE_ALIASES.get(str(pref_taxo).strip().lower(), str(pref_taxo).strip().lower())


def tool_is_compatible(tool: dict[str, Any], ctx: RecommendationContext) -> bool:
    if ctx.reads_key == "Short Reads" and not tool.get("supports_shortreads"):
        return False
    if ctx.reads_key == "Long Reads" and not tool.get("supports_longreads"):
        return False
    if ctx.wants_strain and not _flag_true(tool.get("strain_level")):
        return False
    if ctx.wants_func and not _flag_true(tool.get("functional_profiling")):
        return False
    ram = tool.get("ram")
    if ram and isinstance(ram, (int, float)) and ram > ctx.max_ram:
        return False
    return True


def _tool_supports(tool: dict[str, Any], candidates: list[str]) -> bool:
    for k in candidates:
        if _flag_true(tool.get(k)):
            return True
    return False


def _weighted_rank_tuple(result: dict[str, Any], databases: dict[str, Any], ctx: RecommendationContext) -> tuple[Any, ...]:
    db_id = result.get("db_id")
    db_obj = databases.get(db_id, {}) if db_id else {}
    part_count = len([p for p in _to_list(db_obj.get("hasPart")) if isinstance(p, dict) and p.get("@id")])
    broad_boost = 1 if (ctx.envo_key is None and ctx.host_key is None and part_count > 0) else 0
    return (-result["score"], -broad_boost, -part_count)


def recommend(databases: dict[str, Any], tools: dict[str, Any], envo_key: str | None, host_key: str | None, selected_orgs: list[str], reads_key: str, pref_taxo: str, wants_strain: bool, wants_func: bool, max_ram: int) -> list[dict[str, Any]]:
    ctx = RecommendationContext(
        envo_key=envo_key,
        host_key=host_key,
        selected_orgs=selected_orgs,
        reads_key=reads_key,
        pref_taxo=pref_taxo,
        wants_strain=wants_strain,
        wants_func=wants_func,
        max_ram=max_ram,
    )

    results: list[dict[str, Any]] = []
    for tool_id, tool in tools.items():
        if not tool_is_compatible(tool, ctx):
            continue

        best_db_score = -1
        best_db_id = None
        best_db_ts = None
        best_db_rel = None

        for u in _to_list(tool.get("uses_databases")):
            if not isinstance(u, dict):
                continue
            db_id = u.get("@id", "")
            ts = u.get("taxonomy_system")

            pref_norm = _normalize_pref(pref_taxo)
            if pref_norm != "any":
                pref_lower = pref_norm
                if isinstance(ts, list):
                    if pref_lower not in [str(x).lower() for x in ts]:
                        continue
                elif ts and str(ts).lower() != pref_lower:
                    continue

            sc = _score_db_entry(
                db_id,
                databases,
                envo_key,
                host_key,
                ctx.taxon_keys,
                pref_taxo,
                ctx.wants_virus,
                ctx.wants_fungi,
                ctx.wants_euk,
                ctx.wants_bacteria,
                ctx.wants_archaea,
                ts,
            )
            if sc > best_db_score:
                best_db_score = sc
                best_db_id = db_id
                best_db_ts = ts
                best_db_rel = u

        if best_db_score <= 0:
            continue

        db_obj = databases.get(best_db_id, {})
        dl_info = []
        if db_obj:
            for ct in db_obj.get("compatible_tools", []):
                if isinstance(ct, dict) and ct.get("@id") == tool_id:
                    dl_info = [v for v in ct.get("DB", []) if isinstance(v, dict)]
                    break

        releases = []
        for u in _to_list(tool.get("uses_databases")):
            if isinstance(u, dict) and u.get("@id") == best_db_id:
                r = _to_list(u.get("release"))
                releases = [str(x) for x in r if x is not None]

        results.append(
            {
                "tool_id": tool_id,
                "tool": tool,
                "db_id": best_db_id,
                "db": db_obj,
                "db_ts": best_db_ts,
                "db_rel": best_db_rel,
                "score": best_db_score,
                "dl": dl_info,
                "releases": releases,
            }
        )

    return sorted(results, key=lambda r: _weighted_rank_tuple(r, databases, ctx))
