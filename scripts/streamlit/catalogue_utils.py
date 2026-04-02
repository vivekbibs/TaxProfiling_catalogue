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
    """Retourne (envo_key_or_tag, host_taxon_key) depuis le JSON."""
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
    "Intestinal humain (gut)": ("ENVO_00002003", "NCBITaxon_9606"),
    "Cutané humain (skin)": ("ENVO_00002003", "NCBITaxon_9606"),
    "Oral humain": ("ENVO_00002003", "NCBITaxon_9606"),
    "Intestinal Souris (Mus musculus)": ("ENVO_00002003", "NCBITaxon_10090"),
    "Intestinal Rat (Rattus norvegicus)": ("ENVO_00002003", "NCBITaxon_10116"),
    "Intestinal Chien (Canis lupus)": ("ENVO_00002003", "NCBITaxon_9615"),
    "Intestinal Chat (Felis catus)": ("ENVO_00002003", "NCBITaxon_9685"),
    "Intestinal Cochon (Sus scrofa)": ("ENVO_00002003", "NCBITaxon_9825"),
    "Intestinal Lapin (Oryctolagus cuniculus)": ("ENVO_00002003", "NCBITaxon_9986"),
    "Caecum Poulet (Gallus gallus)": ("ENVO_00002003", "NCBITaxon_9031"),
    "Intestinal Chèvre (Capra hircus)": ("ENVO_00002003", "NCBITaxon_9925"),
    "Intestinal Mouton (Ovis aries)": ("ENVO_00002003", "NCBITaxon_9940"),
    "Sol (Soil)": ("ENVO_00001998", None),
    "Océan / Eau marine": ("ENVO_00002149", None),
    "Eau douce / Lac / Rivière": ("ENVO_00002006", None),
    "Sédiment": ("ENVO_00002007", None),
    "Glacier-fed Streams": ("ENVO_00002007", "ENVO_01001529"),
    "Nourriture / Aliment": ("ENVO_00002073", None),
    "Multi-environnements / Global": (None, None),
    "Autre / Je ne sais pas": (None, None),
}

SAMPLE_CATEGORIES: dict[str, list[str]] = {
    "Humain": [
        "Intestinal humain (gut)",
        "Cutané humain (skin)",
        "Oral humain",
    ],
    "Animal": [
        "Souris (Mus musculus)",
        "Rat (Rattus norvegicus)",
        "Chien (Canis lupus)",
        "Chat (Felis catus)",
        "Cochon (Sus scrofa)",
        "Lapin (Oryctolagus cuniculus)",
        "Poulet (Gallus gallus)",
        "Chèvre (Capra hircus)",
        "Mouton (Ovis aries)",
    ],
    "Environnemental": [
        "Sol",
        "Océan / Eau marine",
        "Sédiment",
        "Nourriture / Aliment",
    ],
    "Multi-environnements / Général": ["Multi-environnements / Général"],
    "Autre": ["Autre / Je ne sais pas"],
}

TAXON_IRI: dict[str, str] = {
    "Bactéries": "NCBITaxon_2",
    "Archées": "NCBITaxon_2157",
    "Eucaryotes": "NCBITaxon_2759",
    "Virus": "NCBITaxon_10239",
    "Fungi": "NCBITaxon_4751",
}

SPECIAL_SCOPE_TAGS = {"virus", "fungi", "eukaryote", "plasmid"}


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
) -> int:
    """Score 0-6 d'une entrée uses_databases selon les critères utilisateur."""
    envo_tag, host_tag = db_scope(db_id, databases)
    score = 0

    if envo_key:
        if envo_tag == envo_key:
            score += 3
        elif envo_tag is None:
            score += 1
    else:
        if envo_tag is None:
            score += 2

    if host_key and host_tag == host_key:
        score += 3

    if envo_tag == "virus" and wants_virus:
        score += 3
    if envo_tag == "fungi" and wants_fungi:
        score += 3
    if envo_tag == "eukaryote" and wants_euk:
        score += 3

    return score


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
    wants_euk = "Eucaryotes" in selected_orgs
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

        best_db_score = 0
        best_db_id = None
        best_db_ts = None

        for u in _to_list(tool.get("uses_databases")):
            if not isinstance(u, dict):
                continue
            db_id = u.get("@id", "")
            ts = u.get("taxonomy_system")

            if pref_taxo != "Indifférent":
                pref_lower = pref_taxo.lower()
                if isinstance(ts, list):
                    if pref_lower not in [x.lower() for x in ts]:
                        continue
                elif ts and ts.lower() != pref_lower:
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
            )
            if sc > best_db_score:
                best_db_score = sc
                best_db_id = db_id
                best_db_ts = ts

        if best_db_score == 0 and (envo_key or host_key):
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
                "score": best_db_score,
                "dl": dl_info,
                "releases": releases,
            }
        )

    return sorted(results, key=lambda r: -r["score"])
