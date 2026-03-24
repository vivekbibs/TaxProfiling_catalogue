"""
app_questionnaire.py  —  Aide au choix : Profiling Taxonomique
──────────────────────────────────────────────────────────────
Piloté par les fichiers JSON-LD du catalogue (data/databases/ + data/tools/).
Aucun outil ni BD n'est codé en dur : tout vient des JSONs.

Lancement :
    streamlit run app_questionnaire.py
"""

import json
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aide au choix — Profiling Taxonomique",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"
DB_DIR = DATA_DIR / "databases"
TOOL_DIR = DATA_DIR / "tools"

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
@st.cache_data
def load_catalogue(db_dir: Path, tool_dir: Path) -> tuple[dict, dict]:
    databases, tools = {}, {}

    # Vérification si les dossiers existent pour éviter les crashs
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
            # Ignorer les sous-outils
            if obj.get("type", "").lower() in ("sub-tool", "sub_tool"):
                continue
            tools[key] = obj
        except Exception as e:
            st.warning(f"⚠️ {path.name} : {e}")

    return databases, tools


# ─────────────────────────────────────────────────────────────────────────────
# CONNAISSANCE DES BDs (scope biologique) — complète les JSONs de BDs manquants
# ─────────────────────────────────────────────────────────────────────────────
# Pour chaque @id de BD référencé par un outil, on déclare ici sa portée
# biologique si le fichier JSON de cette BD n'existe pas encore dans data/databases/.
# Format : (envo_key | scope_tag, ncbitaxon_host_key | None)
DB_SCOPE_FALLBACK: dict[str, tuple] = {
    # ── Host-specific (meteor) ──────────────────────────────────────
    "hs_10_4_gut": ("ENVO_00002003", "NCBITaxon_9606"),
    "hs_2_9_skin": ("ENVO_00002003", "NCBITaxon_9606"),
    "hs_8_4_oral": ("ENVO_00002003", "NCBITaxon_9606"),
    "mm_5_0_gut": ("ENVO_00002003", "NCBITaxon_10090"),
    "rn_5_9_gut": ("ENVO_00002003", "NCBITaxon_10116"),
    "clf_1_0_gut": ("ENVO_00002003", "NCBITaxon_9615"),
    "fc_1_3_gut": ("ENVO_00002003", "NCBITaxon_9685"),
    "gg_13_6_caecal": ("ENVO_00002003", "NCBITaxon_9031"),
    "oc_5_7_gut": ("ENVO_00002003", "NCBITaxon_9986"),
    "ssc_9_3_gut": ("ENVO_00002003", "NCBITaxon_9825"),
    "uhgg": ("ENVO_00002003", "NCBITaxon_9606"),
    # ── Virus ───────────────────────────────────────────────────────
    "imgvr": ("virus", None),
    "uhgv": ("virus", None),
    "genbank_viruses": ("virus", None),
    "refseq_viral": ("virus", None),
    "refseq_viruses": ("virus", None),
    "rvdb": ("virus", None),
    # ── Fungi / Eukaryotes ──────────────────────────────────────────
    "refseq_fungi": ("fungi", None),
    "refseqfungi": ("fungi", None),
    "refseq_eukaryotes": ("eukaryote", None),
    "blast_nr_eukaryotes": ("eukaryote", None),
    "tara_oceans": ("ENVO_00002149", None),
    # ── Plasmides ───────────────────────────────────────────────────
    "refseq_plasmids": ("plasmid", None),
    # ── Génériques / multi-env ──────────────────────────────────────
    "gtdb": (None, None),
    "globdb": (None, None),
    "motus-db": (None, None),
    "refseq": (None, None),
    "refseq_nr": (None, None),
    "refseq_prot": (None, None),
    "progenomes": (None, None),
    "blast_nr": (None, None),
    "kraken_standard": (None, None),
    "chocophlan": (None, None),
    "tipp3_refpkg": (None, None),
}


def db_scope(db_id: str, databases: dict) -> tuple:
    """Retourne (envo_key_or_tag, host_taxon_key) depuis le JSON ou le fallback."""
    db = databases.get(db_id)
    if db:
        s = db.get("sample")
        envo = None
        if isinstance(s, dict):
            iri = s.get("@id", "")
            for sep in ("obo/", "obo_"):
                if sep in iri:
                    envo = iri.split(sep)[-1]
                    break
        origins = _to_list(db.get("origin"))
        host = None
        for o in origins:
            if isinstance(o, dict):
                iri = o.get("@id", "")
                for sep in ("obo/", "obo_"):
                    if sep in iri:
                        host = iri.split(sep)[-1]
                        break
        return (envo, host)
    return DB_SCOPE_FALLBACK.get(db_id, (None, None))


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
    "Souris (Mus musculus)": ("ENVO_00002003", "NCBITaxon_10090"),
    "Rat (Rattus norvegicus)": ("ENVO_00002003", "NCBITaxon_10116"),
    "Chien (Canis lupus)": ("ENVO_00002003", "NCBITaxon_9615"),
    "Chat (Felis catus)": ("ENVO_00002003", "NCBITaxon_9685"),
    "Cochon (Sus scrofa)": ("ENVO_00002003", "NCBITaxon_9825"),
    "Lapin (Oryctolagus cuniculus)": ("ENVO_00002003", "NCBITaxon_9986"),
    "Poulet (Gallus gallus)": ("ENVO_00002003", "NCBITaxon_9031"),
    "Chèvre (Capra hircus)": ("ENVO_00002003", "NCBITaxon_9925"),
    "Mouton (Ovis aries)": ("ENVO_00002003", "NCBITaxon_9940"),
    "Sol (Soil)": ("ENVO_00001998", None),
    "Océan / Eau marine": ("ENVO_00002149", None),
    "Eau douce / Lac / Rivière": ("ENVO_00002006", None),
    "Sédiment": ("ENVO_00002007", None),
    "Glacier / Streams glaciaires": ("ENVO_00002007", None),
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
        "Sol (Soil)",
        "Océan / Eau marine",
        "Eau douce / Lac / Rivière",
        "Sédiment",
        "Glacier / Streams glaciaires",
        "Nourriture / Aliment",
    ],
    "Multi-environnements / Global": ["Multi-environnements / Global"],
    "Autre": ["Autre / Je ne sais pas"],
}

TAXON_IRI: dict[str, str] = {
    "Bactéries": "NCBITaxon_2",
    "Archées": "NCBITaxon_2157",
    "Eucaryotes": "NCBITaxon_2759",
    "Virus": "NCBITaxon_10239",
    "Fungi": "NCBITaxon_4751",
}

# Tags spéciaux pour les séquences non-taxonomiques
SPECIAL_SCOPE_TAGS = {"virus", "fungi", "eukaryote", "plasmid"}


# ─────────────────────────────────────────────────────────────────────────────
# MOTEUR DE RECOMMANDATION — côté outils (uses_databases)
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

    # Correspondance sample ENVO
    if envo_key:
        if envo_tag == envo_key:
            score += 3
        elif envo_tag is None:  # BD généraliste → faible bonus
            score += 1
    else:
        # Pas de filtre précis → préférer les BDs généralistes
        if envo_tag is None:
            score += 2

    # Correspondance hôte NCBITaxon
    if host_key and host_tag == host_key:
        score += 3

    # BDs spécialisées virus/fungi/euk
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

    results = []

    for tool_id, tool in tools.items():
        # Filtre reads
        if reads_key == "Short Reads" and not tool.get("supports_shortreads"):
            continue
        if reads_key == "Long Reads" and not tool.get("supports_longreads"):
            continue

        # Filtre RAM
        ram = tool.get("ram")
        if ram and isinstance(ram, (int, float)) and ram > max_ram:
            continue

        # Filtre strain-level
        if wants_strain and not tool.get("strain_level"):
            pass  # on garde quand même mais on notera l'absence

        # Filtre profiling fonctionnel
        if wants_func and not tool.get("functional_profiling"):
            pass  # idem

        # Score sur uses_databases
        best_db_score = 0
        best_db_id = None
        best_db_ts = None

        for u in _to_list(tool.get("uses_databases")):
            if not isinstance(u, dict):
                continue
            db_id = u.get("@id", "")
            ts = u.get("taxonomy_system")

            # Filtre taxonomie préférée
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
            continue  # aucune BD ne correspond

        # Chercher les infos de téléchargement dans le JSON de la BD (si disponible)
        db_obj = databases.get(best_db_id, {})
        dl_info = download_variants(db_obj, tool_id) if db_obj else []

        # Chercher les releases compatibles
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


# ─────────────────────────────────────────────────────────────────────────────
# INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
databases, tools = load_catalogue(DB_DIR, TOOL_DIR)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📦 Catalogue")
    st.metric("Bases de données", len(databases))
    st.metric("Outils", len(tools))
    st.markdown("---")
    with st.expander("Outils chargés", expanded=False):
        for t_id, t in sorted(tools.items()):
            sr = "✅" if t.get("supports_shortreads") else "❌"
            lr = "✅" if t.get("supports_longreads") else "❌"
            st.markdown(
                f"**{t.get('name', t_id)}**  \n"
                f"SR {sr} · LR {lr} · {t.get('citations_count','?')} citations"
            )

# ── En-tête ───────────────────────────────────────────────────────────────────
st.markdown("# 🧬 Aide au choix — Profiling Taxonomique")
st.markdown(
    "Répondez aux questions ci-dessous pour obtenir les outils et bases de données "
    "adaptés à votre échantillon et vos objectifs. "
    "Les recommandations sont générées directement depuis le catalogue JSON-LD."
)
st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# Q1 — Séquençage
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 1 · Type de séquençage")
reads_choice = st.radio(
    "Type de lectures",
    ["Short Reads (Illumina, etc.)", "Long Reads (PacBio, Nanopore, etc.)"],
    horizontal=True,
)
reads_key = "Short Reads" if "Short" in reads_choice else "Long Reads"
st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# Q2 — Échantillon
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 2 · Nature de l'échantillon")
col_cat, col_detail = st.columns([1, 2])

with col_cat:
    category = st.selectbox("Catégorie principale", list(SAMPLE_CATEGORIES.keys()))

with col_detail:
    options = SAMPLE_CATEGORIES[category]
    if len(options) == 1:
        detail = options[0]
        st.info(f"Sélectionné : **{detail}**")
    elif category == "Humain":
        detail = st.radio("Site corporel", options, horizontal=True)
    elif category == "Animal":
        detail = st.selectbox("Espèce", options)
    else:
        detail = st.radio("Type", options, horizontal=True)

envo_key, host_key = SAMPLE_FILTER.get(detail, (None, None))

if envo_key or host_key:
    parts = []
    if envo_key:
        parts.append(f"sample : `{envo_key}`")
    if host_key:
        parts.append(f"hôte : `{host_key}`")
    st.caption("Filtres JSON → " + "  ·  ".join(parts))

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# Q3 — Organismes & analyses
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 3 · Organismes cibles & analyses souhaitées")
col_org, col_extra = st.columns(2)

with col_org:
    selected_orgs = st.multiselect(
        "Groupes taxonomiques à identifier",
        list(TAXON_IRI.keys()),
        default=["Bactéries", "Archées"],
        help="Sélectionnez tous les groupes que vous souhaitez profiler.",
    )
    if not selected_orgs:
        st.warning("Sélectionnez au moins un groupe.")

with col_extra:
    wants_strain = st.checkbox(
        "🔬 Strain-level profiling",
        help="Résolution au niveau de la souche (ex. MetaPhlAn + StrainPhlAn).",
    )
    wants_func = st.checkbox(
        "⚙️ Profiling fonctionnel",
        help="Annotation fonctionnelle en plus du profiling taxonomique (ex. HUMAnN3).",
    )
    if wants_func:
        st.info("💡 Profiling fonctionnel : recommande meteor / HUMAnN3.")
    if wants_strain:
        st.info("💡 Strain-level : MetaPhlAn (StrainPhlAn), Metabuli.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# Q4 — Paramètres avancés
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("⚙️ Paramètres avancés", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        pref_taxo = st.radio(
            "Taxonomie de la base de référence",
            ["Indifférent", "GTDB", "NCBI"],
            horizontal=True,
            help=(
                "GTDB : taxonomie phylogénomique révisée.  \n"
                "NCBI : taxonomie standard.  \n"
                "Certains outils (MetaPhlAn) supportent les deux."
            ),
        )
    with col_b:
        max_ram = st.slider(
            "RAM disponible (GB)",
            min_value=2,
            max_value=512,
            value=512,
            step=2,
            help="Filtre les outils selon leur RAM requise (si renseignée).",
        )

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# RECOMMANDATIONS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 4 · Recommandations")

if not selected_orgs:
    st.warning("Sélectionnez au moins un groupe d'organismes (section 3).")
    st.stop()

recs = recommend(
    databases,
    tools,
    envo_key,
    host_key,
    selected_orgs,
    reads_key,
    pref_taxo,
    wants_strain,
    wants_func,
    max_ram,
)

if not recs:
    st.warning(
        "Aucun outil ne correspond exactement à vos critères.  \n"
        "Essayez de relâcher les filtres (taxonomie, RAM) ou vérifiez vos JSONs."
    )
else:
    st.success(f"**{len(recs)} outil(s)** trouvé(s).")

    for i, rec in enumerate(recs):
        tool = rec["tool"]
        db = rec["db"]
        db_id = rec["db_id"] or "—"
        t_name = tool.get("name", rec["tool_id"])
        db_name = db.get("name", db_id) if db else db_id
        ts = rec["db_ts"]
        score = rec["score"]
        releases = rec["releases"]

        # Badge strain/func
        badges = []
        if tool.get("strain_level"):
            badges.append("🔬 strain-level")
        if tool.get("functional_profiling"):
            badges.append("⚙️ fonctionnel")
        badge_str = "  ·  ".join(badges) if badges else ""

        with st.expander(
            f"{'⭐ ' if i == 0 else ''}"
            f"**{t_name}**  +  **{db_name}**"
            f"{'  ·  ' + badge_str if badge_str else ''}",
            expanded=(i == 0),
        ):
            col_t, col_d = st.columns(2)

            # ── Outil ──────────────────────────────────────────────────────
            with col_t:
                st.markdown(f"### 🔧 {t_name}")
                desc = tool.get("description") or tool.get("approach_detail") or ""
                if desc:
                    st.markdown(f"*{desc}*")
                st.markdown("")

                # Propriétés clés
                strain_v = "✅" if tool.get("strain_level") else "❌"
                func_v = "✅" if tool.get("functional_profiling") else "❌"
                sr_v = "✅" if tool.get("supports_shortreads") else "❌"
                lr_v = "✅" if tool.get("supports_longreads") else "❌"
                ram_v = f"{tool['ram']} GB" if tool.get("ram") else "—"

                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown(f"**Version** : {tool.get('latest_release') or '—'}")
                    st.markdown(f"**Short reads** : {sr_v}")
                    st.markdown(f"**Long reads** : {lr_v}")
                    st.markdown(f"**RAM requise** : {ram_v}")
                with col_p2:
                    st.markdown(f"**Strain-level** : {strain_v}")
                    st.markdown(f"**Profiling fonctionnel** : {func_v}")
                    st.markdown(f"**Type** : {tool.get('type','—')}")
                    st.markdown(f"**Citations** : {tool.get('citations_count','—')}")

                # Approche algorithmique
                if tool.get("approach_detail") and tool.get("approach_detail") != desc:
                    st.markdown(f"**Approche** : {tool['approach_detail']}")

                # Sous-module
                sm = tool.get("sub_module")
                if sm and isinstance(sm, dict):
                    st.markdown(
                        f"📦 **Sous-module** : {sm.get('name', sm.get('@id',''))}"
                    )

                # Liens
                links = []
                if tool.get("repo"):
                    links.append(f"[GitHub]({tool['repo']})")
                if tool.get("doc"):
                    links.append(f"[Documentation]({tool['doc']})")
                if tool.get("bio_tools"):
                    links.append(f"[bio.tools]({tool['bio_tools']})")
                if tool.get("doi"):
                    links.append(f"[Publication]({tool['doi']})")
                if links:
                    st.markdown("🔗 " + "  ·  ".join(links))

            # ── Base de données ────────────────────────────────────────────
            with col_d:
                st.markdown(f"### 🗄️ {db_name}")

                # Taxonomie — info la plus demandée
                ts_display = taxonomy_badge(ts)
                if ts_display != "—":
                    color = "#1D9E75" if "GTDB" in ts_display else "#534AB7"
                    st.markdown(
                        f"<span style='background:{color};color:white;"
                        f"padding:2px 10px;border-radius:12px;font-weight:bold;"
                        f"font-size:13px'>{ts_display}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")

                # Versions compatibles
                if releases:
                    st.markdown(f"**Releases compatibles** : {', '.join(releases)}")

                # Portée biologique de la BD
                if db:
                    taxa = taxon_labels(db)
                    if taxa:
                        st.markdown(f"**Taxons couverts** : {', '.join(taxa)}")

                    smpl = sample_label(db)
                    orig = origin_label(db)
                    seq = seq_scope_label(db)
                    abt = is_about_label(db)

                    if smpl != "—":
                        st.markdown(f"**Échantillon** : {smpl}")
                    if orig != "—":
                        st.markdown(f"**Origine** : {orig}")
                    if seq != "—":
                        st.markdown(f"**Séquences** : {seq}")
                    if abt != "—":
                        st.markdown(f"**Processus** : {abt}")

                    st.markdown(f"**Release BD** : {db_release_str(db)}")
                    parents = [
                        ip.get("@id", "")
                        for ip in db.get("isPartOf", [])
                        if isinstance(ip, dict)
                    ]
                    if parents:
                        st.markdown(f"**Fait partie de** : {', '.join(parents)}")
                    if db.get("homepage"):
                        st.markdown(f"🌐 [Site officiel]({db['homepage']})")
                    if db.get("doi"):
                        st.markdown(f"📄 [Publication]({db['doi']})")
                else:
                    # BD pas encore dans data/databases/ — afficher ce qu'on sait
                    envo_fb, host_fb = DB_SCOPE_FALLBACK.get(db_id, (None, None))
                    if envo_fb:
                        st.markdown(f"**Scope** : `{envo_fb}`")
                    if host_fb:
                        st.markdown(f"**Hôte** : `{host_fb}`")
                    st.caption(
                        f"ℹ️ Fichier JSON `{db_id}.json` absent de `data/databases/` "
                        "— ajoutez-le pour afficher les détails complets."
                    )

                # Téléchargement (si dispo dans le JSON de la BD)
                dl = rec["dl"]
                if dl:
                    st.markdown("#### 💾 Téléchargement")
                    for v in dl:
                        v_name = v.get("name", "default")
                        v_size = v.get("size")
                        v_url = v.get("download", "")
                        v_ifb = v.get("ifb_server")
                        v_access = v.get("access_method", "url")
                        size_str = f" — **{v_size} GB**" if v_size else ""
                        st.markdown(f"**{v_name}**{size_str}")
                        if v_access == "cli" or (
                            v_url and not v_url.startswith("http")
                        ):
                            st.code(v_url, language="bash")
                        elif v_url:
                            st.markdown(f"⬇️ [Télécharger]({v_url})")
                        if v_ifb and isinstance(v_ifb, dict):
                            st.markdown(
                                f"🖥️ **IFB {v_ifb.get('name','')}** :  \n"
                                f"`{v_ifb.get('path','')}`"
                            )

# ══════════════════════════════════════════════════════════════════════════════
# TABLEAUX COMPARATIFS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")

with st.expander("🔧 Tableau comparatif — tous les outils", expanded=False):
    rows_t = []
    for t_id, t in sorted(tools.items()):
        dbs_all = _to_list(t.get("uses_databases"))
        db_names = ", ".join(
            u.get("name") or u.get("@id", "") for u in dbs_all if isinstance(u, dict)
        )
        taxo_systems = list(
            {
                taxonomy_badge(u.get("taxonomy_system"))
                for u in dbs_all
                if isinstance(u, dict)
            }
        )
        rows_t.append(
            {
                "Outil": t.get("name", t_id),
                "Type": t.get("type", "—"),
                "Version": t.get("latest_release") or "—",
                "Short reads": "✅" if t.get("supports_shortreads") else "❌",
                "Long reads": "✅" if t.get("supports_longreads") else "❌",
                "Strain-level": "✅" if t.get("strain_level") else "❌",
                "Fonctionnel": "✅" if t.get("functional_profiling") else "❌",
                "RAM (GB)": t.get("ram") or "—",
                "Taxonomie(s) BD": ", ".join(taxo_systems),
                "BDs": db_names,
                "Citations": t.get("citations_count") or "—",
            }
        )
    st.dataframe(rows_t, use_container_width=True)

with st.expander("📊 Tableau comparatif — bases de données", expanded=False):
    rows_d = []
    for db_id, db in sorted(databases.items()):
        rows_d.append(
            {
                "ID": db_id,
                "Nom": db.get("name", db_id),
                "Taxons": ", ".join(taxon_labels(db)) or "—",
                "Échantillon": sample_label(db),
                "Origine": origin_label(db),
                "Séquences (SO)": seq_scope_label(db),
                "is_about": is_about_label(db),
                "Release": db_release_str(db),
                "Outils": ", ".join(compatible_tool_ids(db)) or "—",
            }
        )
    st.dataframe(rows_d, use_container_width=True)

st.markdown("---")
if st.button("🔄 Réinitialiser"):
    st.rerun()
