from __future__ import annotations
from dataclasses import dataclass, field
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


@dataclass(slots=True)
class CatalogDatabase:
    id: str
    raw: dict[str, Any]
    sample: list[dict[str, Any]] = field(default_factory=list)
    origin: list[dict[str, Any]] = field(default_factory=list)
    taxonomic_scope: list[dict[str, Any]] = field(default_factory=list)
    has_part: list[dict[str, Any]] = field(default_factory=list)
    is_part_of: list[dict[str, Any]] = field(default_factory=list)
    compatible_tools: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, db_id: str, payload: dict[str, Any]) -> "CatalogDatabase":
        return cls(
            id=db_id,
            raw=payload,
            sample=_to_list(payload.get("sample")),
            origin=_to_list(payload.get("origin")),
            taxonomic_scope=_to_list(payload.get("taxonomic_scope")),
            has_part=_to_list(payload.get("hasPart")),
            is_part_of=_to_list(payload.get("isPartOf")),
            compatible_tools=_to_list(payload.get("compatible_tools")),
        )


@dataclass(slots=True)
class CatalogTool:
    id: str
    raw: dict[str, Any]
    supports_shortreads: bool = False
    supports_longreads: bool = False
    strain_level: bool = False
    functional_profiling: bool = False
    ram: int | None = None
    uses_databases: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, tool_id: str, payload: dict[str, Any]) -> "CatalogTool":
        return cls(
            id=tool_id,
            raw=payload,
            supports_shortreads=bool(payload.get("supports_shortreads", False)),
            supports_longreads=bool(payload.get("supports_longreads", False)),
            strain_level=bool(payload.get("strain_level", False)),
            functional_profiling=bool(payload.get("functional_profiling", False)),
            ram=payload.get("ram"),
            uses_databases=_to_list(payload.get("uses_databases")),
        )

    def supports_reads(self, reads_key: str) -> bool:
        if reads_key == "Short Reads":
            return self.supports_shortreads
        if reads_key == "Long Reads":
            return self.supports_longreads
        return False


@dataclass(slots=True)
class RecommendationContext:
    sample_key: str | None #formerly envo_key
    origin_key: str | None #formerly host_key
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


def tool_is_compatible(tool: dict[str, Any] | CatalogTool, ctx: RecommendationContext) -> bool:
    if isinstance(tool, CatalogTool):
        if ctx.reads_key == "Short Reads" and not tool.supports_shortreads:
            return False
        if ctx.reads_key == "Long Reads" and not tool.supports_longreads:
            return False
        if ctx.wants_strain and not tool.strain_level:
            return False
        if ctx.wants_func and not tool.functional_profiling:
            return False
        if tool.ram and isinstance(tool.ram, (int, float)) and tool.ram > ctx.max_ram:
            return False
        return True

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


def _to_catalog_wrapper(databases: dict[str, Any], tools: dict[str, Any]) -> tuple[dict[str, CatalogDatabase], dict[str, CatalogTool]]:
    wrapped_databases = {k: CatalogDatabase.from_dict(k, v) for k, v in databases.items()}
    wrapped_tools = {k: CatalogTool.from_dict(k, v) for k, v in tools.items()}
    return wrapped_databases, wrapped_tools


def _weighted_rank_tuple(result: dict[str, Any], databases: dict[str, Any], ctx: RecommendationContext) -> tuple[Any, ...]:
    db_id = result.get("db_id")
    db_obj = databases.get(db_id, {}) if db_id else {}
    part_count = len([p for p in _to_list(db_obj.get("hasPart")) if isinstance(p, dict) and p.get("@id")])
    broad_boost = 1 if (ctx.sample_key is None and ctx.origin_key is None and part_count > 0) else 0
    return (-result["score"], -broad_boost, -part_count)


def recommend(databases: dict[str, Any], tools: dict[str, Any], sample_key: str | None, origin_key: str | None, selected_orgs: list[str], reads_key: str, pref_taxo: str, wants_strain: bool, wants_func: bool, max_ram: int) -> list[dict[str, Any]]:
    ctx = RecommendationContext(
        sample_key=sample_key,
        origin_key=origin_key,
        selected_orgs=selected_orgs,
        reads_key=reads_key,
        pref_taxo=pref_taxo,
        wants_strain=wants_strain,
        wants_func=wants_func,
        max_ram=max_ram,
    )

    wrapped_databases, wrapped_tools = _to_catalog_wrapper(databases, tools)
    results: list[dict[str, Any]] = []
    for tool_id, tool in wrapped_tools.items():
        if not tool_is_compatible(tool, ctx):
            continue

        best_db_score = -1
        best_db_id = None
        best_db_ts = None
        best_db_rel = None

        for u in _to_list(tool.uses_databases):
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
                sample_key,
                origin_key,
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

        db_obj = wrapped_databases.get(best_db_id, None)
        dl_info = []
        if db_obj:
            for ct in db_obj.compatible_tools:
                if isinstance(ct, dict) and ct.get("@id") == tool_id:
                    dl_info = [v for v in ct.get("DB", []) if isinstance(v, dict)]
                    break

        releases = []
        for u in _to_list(tool.uses_databases):
            if isinstance(u, dict) and u.get("@id") == best_db_id:
                r = _to_list(u.get("release"))
                releases = [str(x) for x in r if x is not None]

        results.append(
            {
                "tool_id": tool_id,
                "tool": tool.raw,
                "db_id": best_db_id,
                "db": db_obj.raw if db_obj else {},
                "db_ts": best_db_ts,
                "db_rel": best_db_rel,
                "score": best_db_score,
                "dl": dl_info,
                "releases": releases,
            }
        )

    return sorted(results, key=lambda r: _weighted_rank_tuple(r, databases, ctx))
