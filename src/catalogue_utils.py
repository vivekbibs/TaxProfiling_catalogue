"""
catalogue_utils.py  —  Logique métier du catalogue Profiling Taxonomique
─────────────────────────────────────────────────────────────────────────
Chargement des JSONs, helpers d'affichage, constantes, moteur de recommandation.
Aucune dépendance Streamlit : ce module peut être importé sans lancer une appli.

Utilisé par :
    app.py  (streamlit run app.py)
"""

import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# NORMALISATION
# ─────────────────────────────────────────────────────────────────────────────
_LIST_FIELDS = [
    "taxonomic_scope",
    "uses_databases",
    "hasPart",
    "isPartOf",
    "sequence_scope",
    "compatible_tools",
    "is_about",
]


def _to_list(val) -> list:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _normalize(obj: dict) -> dict:
    obj = dict(obj)
    for f in _LIST_FIELDS:
        obj[f] = _to_list(obj.get(f))
    obj["compatible_tools"] = [
        c for c in obj["compatible_tools"] if isinstance(c, dict)
    ]
    obj["isPartOf"] = [
        ip if isinstance(ip, dict) else {"@id": str(ip)} for ip in obj["isPartOf"]
    ]
    # rétrocompat sample_type → sample
    if obj.get("sample") is None and obj.get("sample_type"):
        obj["sample"] = obj["sample_type"]
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────────────────────────────────────
def load_catalogue(db_dir: Path, tool_dir: Path) -> tuple[dict, dict]:
    """Charge les JSONs depuis db_dir et tool_dir. Retourne (databases, tools)."""
    import streamlit as st

    databases, tools = {}, {}

    if not db_dir.exists():
        st.error(f"Dossier des bases introuvable : {db_dir}")
        return {}, {}

    for path in sorted(db_dir.glob("*.json")):
        try:
            obj = _normalize(json.loads(path.read_text(encoding="utf-8")))
            key = obj.get("@id") or path.stem
            if isinstance(key, str) and key.startswith("http"):
                key = path.stem
            databases[key] = obj
        except Exception as e:
            st.warning(f"⚠️ {path.name} : {e}")

    for path in sorted(tool_dir.glob("*.json")):
        try:
            obj = _normalize(json.loads(path.read_text(encoding="utf-8")))
            key = obj.get("@id") or path.stem
            if obj.get("type", "").lower() in ("sub-tool", "sub_tool"):
                continue
            tools[key] = obj
        except Exception as e:
            st.warning(f"⚠️ {path.name} : {e}")

    return databases, tools


# ─────────────────────────────────────────────────────────────────────────────
# CONNAISSANCE DES BDs (scope biologique) — complète les JSONs manquants
# ─────────────────────────────────────────────────────────────────────────────
_DB_SCOPE_DEBUG = os.getenv("CATALOGUE_DEBUG_DB_SCOPE", "1") == "1"
_DB_SCOPE_DEBUG_LOG = Path(__file__).parent / "debug_db_scope.log"


def _dbg_db_scope(msg: str) -> None:
    """Ecrit des traces db_scope dans un fichier si le mode debug est activé."""
    if not _DB_SCOPE_DEBUG:
        return
    with _DB_SCOPE_DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")


def db_scope(db_id: str, databases: dict) -> tuple:
    """Retourne (tag sample, tag origin) depuis sample.@id et origin[].@id (suffixe obo:)."""
    db = databases.get(db_id)
    if not db:
        _dbg_db_scope(f"db_id={db_id} missing -> return (None, None)")
        return (None, None)

    _dbg_db_scope(f"db_id={db_id}")

    s = db.get("sample")
    envo = None
    _dbg_db_scope(f"sample_type={type(s).__name__} sample_raw={s!r}")
    if isinstance(s, dict):
        iri = str(s.get("@id", "")).strip()
        sep = "obo:"
        _dbg_db_scope(f"sample_iri={iri!r} contains_sep={sep in iri}")
        if sep in iri:
            split_val = iri.split(sep)[-1]
            _dbg_db_scope(f"sample_split={split_val!r}")
            envo = split_val
    else:
        _dbg_db_scope("sample is not a dict -> envo remains None")

    origins = _to_list(db.get("origin"))
    host = None
    _dbg_db_scope(f"origin_count={len(origins)} origin_raw={origins!r}")
    for i, o in enumerate(origins):
        if not isinstance(o, dict):
            _dbg_db_scope(f"origin[{i}] skipped (not dict): {o!r}")
            continue
        iri = str(o.get("@id", "")).strip()
        sep = "obo:"
        _dbg_db_scope(f"origin[{i}] iri={iri!r} contains_sep={sep in iri}")
        if sep in iri:
            split_val = iri.split(sep)[-1]
            _dbg_db_scope(f"origin[{i}] split={split_val!r}")
            host = split_val

    _dbg_db_scope(f"result db_id={db_id} -> envo={envo!r}, host={host!r}")
    return (envo, host)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS D'AFFICHAGE
# ─────────────────────────────────────────────────────────────────────────────
def _iri_key(iri: str) -> str:
    for sep in ("obo/", "obo_"):
        if sep in iri:
            return iri.split(sep)[-1]
    return iri.split("/")[-1].split("#")[-1]


def taxon_labels(obj: dict) -> list[str]:
    return [
        t.get("label") or _iri_key(t.get("@id", ""))
        for t in obj.get("taxonomic_scope", [])
        if isinstance(t, dict)
    ]


def sample_label(db: dict) -> str:
    s = db.get("sample")
    if not isinstance(s, dict):
        return "—"
    return s.get("label") or _iri_key(s.get("@id", "")) or "—"


def origin_label(db: dict) -> str:
    parts = []
    for o in _to_list(db.get("origin")):
        if isinstance(o, dict):
            parts.append(o.get("label") or _iri_key(o.get("@id", "")))
        elif o:
            parts.append(str(o))
    return ", ".join(parts) or "—"


def is_about_label(db: dict) -> str:
    parts = []
    for item in _to_list(db.get("is_about")):
        if isinstance(item, dict):
            parts.append(item.get("label") or _iri_key(item.get("@id", "")))
        elif item:
            parts.append(str(item))
    return ", ".join(parts) or "—"


def seq_scope_label(db: dict) -> str:
    parts = []
    for item in _to_list(db.get("sequence_scope")):
        if isinstance(item, dict):
            parts.append(item.get("label") or _iri_key(item.get("@id", "")))
        elif item:
            parts.append(str(item))
    return ", ".join(parts) or "—"


def taxonomy_badge(ts) -> str:
    """Retourne un badge lisible pour taxonomy_system (str ou list)."""
    if ts is None:
        return "—"
    if isinstance(ts, list):
        return " + ".join(str(x).upper() for x in ts)
    return str(ts).upper()


def db_release_str(db: dict) -> str:
    return db.get("latest_release") or db.get("release") or "—"


def compatible_tool_ids(db: dict) -> list[str]:
    return [
        ct["@id"]
        for ct in db.get("compatible_tools", [])
        if isinstance(ct, dict) and ct.get("@id")
    ]


def download_variants(db: dict, tool_id: str) -> list[dict]:
    for ct in db.get("compatible_tools", []):
        if isinstance(ct, dict) and ct.get("@id") == tool_id:
            return [v for v in ct.get("DB", []) if isinstance(v, dict)]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# CORRESPONDANCES  question → filtres
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_FILTER: dict[str, tuple] = {
    "Human gut": ("ENVO_00002003", "NCBITaxon_9606"),
    "Human skin": ("ENVO_2100003", "NCBITaxon_9606"),
    "Human mouth": ("ENVO_08000002", "NCBITaxon_9606"),
    "Mouse gut (Mus musculus)": ("ENVO_00002003", "NCBITaxon_10090"),
    "Rat gut (Rattus norvegicus)": ("ENVO_00002003", "NCBITaxon_10116"),
    "Dog gut (Canis lupus)": ("ENVO_00002003", "NCBITaxon_9615"),
    "Cat gut(Felis catus)": ("ENVO_00002003", "NCBITaxon_9685"),
    "Pig gut (Sus scrofa)": ("ENVO_00002003", "NCBITaxon_9825"),
    "Rabbit gut (Oryctolagus cuniculus)": ("ENVO_00002003", "NCBITaxon_9986"),
    "Chicken caecum (Gallus gallus)": ("ENVO_00002003", "NCBITaxon_9031"),
    "Goat gut (Capra hircus)": ("ENVO_00002003", "NCBITaxon_9925"),
    "Sheep gut (Ovis aries)": ("ENVO_00002003", "NCBITaxon_9940"),
    "Soil": ("ENVO_00001998", None),
    "Ocean / Marine water": ("ENVO_00002006", "ENVO_00002149"),
    "Fresh water / Lake / River": ("ENVO_00002006", None),
    "Sediment": ("ENVO_00002007", None),
    "Glacier-fed Streams": ("ENVO_00002007", "ENVO_00001529"),
    "Food": ("FOODON_00002403", None),
    "Multi-environments / Global": (None, None),
    "Other/ I don't know": (None, None),
}

SAMPLE_CATEGORIES: dict[str, list[str]] = {
    "Human": [
        "Human gut",
        "Human skin",
        "Human mouth",
    ],
    "Animal": [
        "Mouse gut (Mus musculus)",
        "Rat gut (Rattus norvegicus)",
        "Dog gut (Canis lupus)",
        "Cat gut (Felis catus)",
        "Pig gut (Sus scrofa)",
        "Rabbit gut (Oryctolagus cuniculus)",
        "Chicken caecum (Gallus gallus)",
        "Goat gut (Capra hircus)",
        "Sheep gut (Ovis aries)",
    ],
    "Environmental": [
        "Soil",
        "Ocean / Marine water",
        "Fresh water / Lake / River",
        "Sediment",
        "Glacier-fed streams",
        "Food",
    ],
    "Multi-environments / Global": ["Multi-environments / Global"],
    "Other": ["Other / I don't know"],
}

TAXON_IRI: dict[str, str] = {
    "Bacteria": "NCBITaxon_2",
    "Archaea": "NCBITaxon_2157",
    "Eukaryota": "NCBITaxon_2759",
    "Virus": "NCBITaxon_10239",
    "Fungi": "NCBITaxon_4751",
}

SPECIAL_SCOPE_TAGS = {"virus", "fungi", "eukaryota", "plasmid"}


# ─────────────────────────────────────────────────────────────────────────────
# MOTEUR DE RECOMMANDATION
# ─────────────────────────────────────────────────────────────────────────────
def _score_db_entry(
    db_id: str,
    databases: dict,
    envo_key: str | None,
    host_key: str | None,
    orgs: list[str],
    pref_taxo: str,
    wants_virus: bool,
    wants_fungi: bool,
    wants_euk: bool,
    wants_bacteria: bool,
    wants_archaea: bool,
    rel_taxonomy_system=None,
) -> int:
    """Score d'une entrée uses_databases avec contraintes strictes."""

    def _scope_labels(db_obj: dict | None) -> list[str]:
        labels = []
        if isinstance(db_obj, dict):
            for t in _to_list(db_obj.get("taxonomic_scope")):
                if isinstance(t, dict):
                    labels.append(str(t.get("label", "")).strip().lower())
        return labels

    def _matches_constraints(
        envo_tag: str | None, host_tag: str | None, db_obj: dict | None
    ) -> bool:
        is_global_scope = envo_tag is None and host_tag is None

        # Strict environment/host constraints from questionnaire.
        if envo_key and envo_tag != envo_key and not is_global_scope:
            return False
        if host_key and host_tag != host_key and not is_global_scope:
            return False

        labels = _scope_labels(db_obj)
        has_virus = ("virus" in str(envo_tag).lower()) or any(
            "virus" in lbl for lbl in labels
        )
        has_fungi = ("fungi" in str(envo_tag).lower()) or any(
            "fung" in lbl for lbl in labels
        )
        has_euk = ("eukaryota" in str(envo_tag).lower()) or any(
            ("eukary" in lbl) or ("eucary" in lbl) for lbl in labels
        )

        # Strict taxonomic group constraints from questionnaire.
        if wants_virus and not has_virus:
            return False
        if wants_fungi and not has_fungi:
            return False
        if wants_euk and not has_euk:
            return False
        return True

    def _score_scope(
        envo_tag: str | None, host_tag: str | None, db_obj: dict | None
    ) -> int:
        score = 0
        if envo_key and envo_tag == envo_key:
            score += 4
        if host_key and host_tag == host_key:
            score += 4
        # Keep truly global catalogues as fallback when user asks a specific context.
        if (envo_key or host_key) and envo_tag is None and host_tag is None:
            score += 1
        if envo_key is None and host_key is None and envo_tag is None:
            score += 1

        # Slightly prefer composite catalogues (e.g. GlobDB) over a single
        # contained catalogue when both satisfy constraints similarly.
        if isinstance(db_obj, dict):
            part_count = len(
                [
                    p
                    for p in _to_list(db_obj.get("hasPart"))
                    if isinstance(p, dict) and p.get("@id")
                ]
            )
            if part_count > 0:
                score += 1

        # GTDB is particularly relevant for Bacteria/Archaea profiling.
        wants_ba = wants_bacteria or wants_archaea
        if wants_ba:
            ts_vals = _to_list(rel_taxonomy_system)
            ts_lower = [str(x).strip().lower() for x in ts_vals if x is not None]
            if "gtdb" in ts_lower:
                score += 2
        return score

    db_obj = databases.get(db_id, {})
    envo_tag, host_tag = db_scope(db_id, databases)

    # Broad survey (multi-env / "autre"): do not rank host-specific
    # catalogues (meteor animal guts, human gut, etc.) — their sample may not
    # be ENVO/FOODON so envo_tag is None, which used to wrongly get a +2 "broad"
    # bonus via _score_scope.
    if envo_key is None and host_key is None and host_tag is not None:
        return -1

    best_score = (
        _score_scope(envo_tag, host_tag, db_obj)
        if _matches_constraints(envo_tag, host_tag, db_obj)
        else -1
    )
    parts = _to_list(db_obj.get("hasPart")) if isinstance(db_obj, dict) else []

    # If a composite DB (e.g. GlobDB) contains a very specific matching sub-DB
    # (e.g. SHGO for goats/sheep), let the parent inherit most of that score.
    best_part_score = -1
    for p in parts:
        if not isinstance(p, dict) or not p.get("@id"):
            continue
        part_db = databases.get(p["@id"], {})
        p_envo, p_host = db_scope(p["@id"], databases)
        if envo_key is None and host_key is None and p_host is not None:
            continue
        if not _matches_constraints(p_envo, p_host, part_db):
            continue
        part_score = _score_scope(p_envo, p_host, part_db)
        if part_score > best_part_score:
            best_part_score = part_score

    if best_part_score >= 0:
        inherited = max(best_part_score - 1, 0)
        if inherited > best_score:
            best_score = inherited

    # Prefer GlobDB for broad/no-specific-context selections.
    if db_id == "globdb" and envo_key is None and host_key is None:
        best_score += 3

    return best_score


def recommend(
    databases: dict,
    tools: dict,
    envo_key: str | None,
    host_key: str | None,
    selected_orgs: list[str],
    reads_key: str,
    pref_taxo: str,
    wants_strain: bool,
    wants_func: bool,
    max_ram: int,
) -> list[dict]:
    wants_virus = "Virus" in selected_orgs
    wants_fungi = "Fungi" in selected_orgs
    wants_euk = "Eukaryota" in selected_orgs
    wants_bacteria = "Bacteria" in selected_orgs
    wants_archaea = "Archaea" in selected_orgs
    taxon_keys = [TAXON_IRI[o] for o in selected_orgs]

    def _flag_true(v) -> bool:
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "y", "supported", "ok")

    def _tool_supports(tool: dict, candidates: list[str]) -> bool:
        for k in candidates:
            if _flag_true(tool.get(k)):
                return True
        return False

    # candidate keys to detect capability flags in tool JSONs
    STRAIN_KEY = "strain_level"
    FUNC_KEY = "functional_profiling"

    results = []

    for tool_id, tool in tools.items():
        if reads_key == "Short Reads" and not tool.get("supports_shortreads"):
            continue
        if reads_key == "Long Reads" and not tool.get("supports_longreads"):
            continue

        # respect user's required analysis capabilities
        if wants_strain and not _tool_supports(tool, [STRAIN_KEY]):
            continue
        if wants_func and not _tool_supports(tool, [FUNC_KEY]):
            continue

        ram = tool.get("ram")
        if ram and isinstance(ram, (int, float)) and ram > max_ram:
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

            # Allow several synonyms for "no preference" so the UI can be
            # localized to English without breaking the recommender.
            # Treat values like 'Any', 'indifferent' or the original 'Indifférent'
            # as meaning no taxonomy preference.
            pref_norm = str(pref_taxo or "").strip().lower()
            if pref_norm not in ("indifférent", "indifferent", "any"):
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
                taxon_keys,
                pref_taxo,
                wants_virus,
                wants_fungi,
                wants_euk,
                wants_bacteria,
                wants_archaea,
                ts,
            )
            if sc > best_db_score:
                best_db_score = sc
                best_db_id = db_id
                best_db_ts = ts
                best_db_rel = u

        # Reject irrelevant matches. score=0 means no useful alignment.
        if best_db_score <= 0:
            continue

        db_obj = databases.get(best_db_id, {})
        dl_info = download_variants(db_obj, tool_id) if db_obj else []

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

    def _rank_tuple(r: dict) -> tuple:
        db_id = r.get("db_id")
        db_obj = databases.get(db_id, {}) if db_id else {}
        part_count = len(
            [
                p
                for p in _to_list(db_obj.get("hasPart"))
                if isinstance(p, dict) and p.get("@id")
            ]
        )
        # In broad contexts (Autre / Multi-env), prefer exhaustive composite DBs.
        broad_boost = (
            1 if (envo_key is None and host_key is None and part_count > 0) else 0
        )
        return (-r["score"], -broad_boost, -part_count)

    return sorted(results, key=_rank_tuple)


def inject_jsonld_schemas(*schema_paths: Path):
    """Injecte les fichiers JSON-LD dans le <head> HTML via st.html."""
    for path in schema_paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        st.html(
            f'<script type="application/ld+json">\n'
            f"{json.dumps(data, indent=2, ensure_ascii=False)}\n"
            f"</script>",
            unsafe_allow_javascript=True,  # ← nécessaire pour que le <script> ne soit pas strippé
        )
