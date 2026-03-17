"""
app_questionnaire.py
────────────────────
Questionnaire interactif pour orienter le choix d'outil et de base de données
de profiling taxonomique, piloté par les fichiers JSON-LD du catalogue.

Structure attendue du projet :
    app_questionnaire.py
    data/
        databases/   ← fichiers JSON des bases de données
        tools/       ← fichiers JSON des outils

Lancement :
    streamlit run app_questionnaire.py
"""

import json
import re
from pathlib import Path

import streamlit as st

# ──────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Outil de Profiling Taxonomique — Aide au choix",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR  = Path(__file__).parent / "data"
DB_DIR    = DATA_DIR / "databases"
TOOL_DIR  = DATA_DIR / "tools"

# ──────────────────────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ──────────────────────────────────────────────────────────

def _normalize(obj: dict) -> dict:
    """Force les champs potentiellement multiples en listes."""
    ARRAY_FIELDS = [
        "taxonomic_scope", "uses_databases", "hasPart",
        "isPartOf", "sequence_scope", "compatible_tools",
    ]
    result = dict(obj)
    for field in ARRAY_FIELDS:
        val = result.get(field)
        if val is None:
            result[field] = []
        elif not isinstance(val, list):
            result[field] = [val]
    return result


@st.cache_data
def load_catalogue() -> tuple[dict, dict]:
    """
    Retourne (databases, tools) sous forme de dicts indexés par @id.
    """
    databases, tools = {}, {}

    for path in sorted(DB_DIR.glob("*.json")):
        try:
            obj = _normalize(json.loads(path.read_text(encoding="utf-8")))
            key = obj.get("@id", path.stem)
            databases[key] = obj
        except Exception as e:
            st.warning(f"Impossible de charger {path.name} : {e}")

    for path in sorted(TOOL_DIR.glob("*.json")):
        try:
            obj = _normalize(json.loads(path.read_text(encoding="utf-8")))
            key = obj.get("@id", path.stem)
            tools[key] = obj
        except Exception as e:
            st.warning(f"Impossible de charger {path.name} : {e}")

    return databases, tools


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────

NCBI_LABEL = {
    "NCBITaxon_2":    "Bacteria",
    "NCBITaxon_2157": "Archaea",
    "NCBITaxon_2759": "Eukaryota",
    "NCBITaxon_10239":"Viruses",
    "NCBITaxon_4751": "Fungi",
}

ENVO_SAMPLE_LABEL = {
    "ENVO_00002003": "Fecal material (gut)",
    "ENVO_00001998": "Soil",
    "ENVO_00002006": "Liquid water (aquatic)",
    "ENVO_00002007": "Sediment",
    "ENVO_00002149": "Sea water (marine)",
    "ENVO_00002073": "Food material",
}

def taxon_labels(db: dict) -> list[str]:
    labels = []
    for t in db.get("taxonomic_scope", []):
        iri = t.get("@id", "")
        key = iri.split("obo/")[-1] if "obo/" in iri else iri.split("_obo_")[-1]
        labels.append(t.get("label") or NCBI_LABEL.get(key, key))
    return labels


def sample_label(db: dict) -> str:
    s = db.get("sample")
    if not s:
        return "—"
    if isinstance(s, dict):
        iri = s.get("@id", "")
        key = iri.split("obo/")[-1] if "obo/" in iri else ""
        return s.get("label") or ENVO_SAMPLE_LABEL.get(key, key) or "—"
    return str(s)


def origin_label(db: dict) -> str:
    o = db.get("origin")
    if not o:
        return "—"
    if isinstance(o, list):
        return ", ".join(
            x.get("label", x.get("@id", "?")) for x in o
        )
    if isinstance(o, dict):
        return o.get("label", o.get("@id", "—"))
    return str(o)


def tool_supports(tool: dict, reads_type: str) -> bool:
    if reads_type == "Short Reads":
        return bool(tool.get("supports_shortreads"))
    if reads_type == "Long Reads":
        return bool(tool.get("supports_longreads"))
    return True


def db_compatible_tools(db: dict) -> list[str]:
    """Retourne les @id des outils listés dans compatible_tools."""
    return [ct.get("@id", "") for ct in db.get("compatible_tools", [])]


def db_download_info(db: dict, tool_id: str) -> list[dict]:
    """Retourne les variantes de téléchargement pour un outil donné."""
    for ct in db.get("compatible_tools", []):
        if ct.get("@id") == tool_id:
            return ct.get("DB", [])
    return []


def db_matches_sample(db: dict, sample_envo_key: str | None) -> bool:
    if sample_envo_key is None:
        return True
    s = db.get("sample")
    if not s:
        return False
    iri = s.get("@id", "") if isinstance(s, dict) else ""
    return sample_envo_key in iri


def db_matches_origin(db: dict, ncbi_taxon_key: str | None) -> bool:
    if ncbi_taxon_key is None:
        return True
    origins = db.get("origin") or []
    if isinstance(origins, dict):
        origins = [origins]
    for o in origins:
        if ncbi_taxon_key in o.get("@id", ""):
            return True
    return False


def db_matches_taxon(db: dict, taxon_keys: list[str]) -> bool:
    if not taxon_keys:
        return True
    db_taxa = [t.get("@id", "") for t in db.get("taxonomic_scope", [])]
    return any(
        any(tk in dbt for dbt in db_taxa)
        for tk in taxon_keys
    )


# ──────────────────────────────────────────────────────────
# MAPPING : paramètres utilisateur → filtres JSON
# ──────────────────────────────────────────────────────────

# Correspondance "type d'échantillon" → (ENVO key, NCBITaxon key hôte)
SAMPLE_MAP = {
    # Humain
    "Intestinal humain (Gut)":    ("ENVO_00002003", "NCBITaxon_9606"),
    "Cutané humain (Skin)":       ("ENVO_00002003", "NCBITaxon_9606"),
    "Oral humain":                ("ENVO_00002003", "NCBITaxon_9606"),
    # Animal — gut
    "Souris (Mus musculus)":      ("ENVO_00002003", "NCBITaxon_10090"),
    "Rat (Rattus norvegicus)":    ("ENVO_00002003", "NCBITaxon_10116"),
    "Chien (Canis lupus)":        ("ENVO_00002003", "NCBITaxon_9615"),
    "Chat (Felis catus)":         ("ENVO_00002003", "NCBITaxon_9685"),
    "Cochon (Sus scrofa)":        ("ENVO_00002003", "NCBITaxon_9825"),
    "Lapin (Oryctolagus)":        ("ENVO_00002003", "NCBITaxon_9986"),
    "Poulet (Gallus gallus)":     ("ENVO_00002003", "NCBITaxon_9031"),
    "Chèvre (Capra hircus)":      ("ENVO_00002003", "NCBITaxon_9925"),
    "Mouton (Ovis aries)":        ("ENVO_00002003", "NCBITaxon_9940"),
    # Environnemental
    "Sol (Soil)":                 ("ENVO_00001998", None),
    "Océan / Eau marine":         ("ENVO_00002149", None),
    "Eau douce / Lac / Rivière":  ("ENVO_00002006", None),
    "Sédiment":                   ("ENVO_00002007", None),
    "Nourriture / Aliment":       ("ENVO_00002073", None),
    # Générique
    "Autre / Je ne sais pas":     (None, None),
}

TAXON_MAP = {
    "Bactéries":   "NCBITaxon_2",
    "Archées":     "NCBITaxon_2157",
    "Eucaryotes":  "NCBITaxon_2759",
    "Virus":       "NCBITaxon_10239",
    "Fungi":       "NCBITaxon_4751",
}

# ──────────────────────────────────────────────────────────
# INTERFACE
# ──────────────────────────────────────────────────────────

databases, tools = load_catalogue()

# ── Sidebar — résumé du catalogue chargé
with st.sidebar:
    st.markdown("### 📦 Catalogue chargé")
    st.metric("Bases de données", len(databases))
    st.metric("Outils", len(tools))
    st.markdown("---")
    st.markdown("**Bases de données**")
    for db_id, db in sorted(databases.items()):
        st.markdown(f"- `{db_id}` — {db.get('name', db_id)}")
    st.markdown("**Outils**")
    for t_id, t in sorted(tools.items()):
        st.markdown(f"- `{t_id}` — {t.get('name', t_id)}")

# ── En-tête
st.markdown("# 🧬 Aide au choix — Profiling Taxonomique")
st.markdown(
    """
Ce questionnaire vous guide vers l'**outil** et la **base de données de référence**
les mieux adaptés à votre échantillon et vos objectifs d'analyse.
Les recommandations sont générées automatiquement à partir du catalogue JSON-LD.
"""
)
st.markdown("---")

# ══════════════════════════════════════════════════════════
# SECTION 1 — Type de séquençage
# ══════════════════════════════════════════════════════════
st.markdown("## 1 · Type de séquençage")

reads_type = st.radio(
    "Type de lectures générées",
    ["Short Reads (Illumina, etc.)", "Long Reads (PacBio, Nanopore, etc.)"],
    horizontal=True,
)
reads_key = "Short Reads" if "Short" in reads_type else "Long Reads"

st.markdown("---")

# ══════════════════════════════════════════════════════════
# SECTION 2 — Nature de l'échantillon
# ══════════════════════════════════════════════════════════
st.markdown("## 2 · Nature de l'échantillon")

col_cat, col_detail = st.columns([1, 2])

with col_cat:
    sample_category = st.selectbox(
        "Catégorie principale",
        ["Humain", "Animal", "Environnemental", "Autre"],
    )

with col_detail:
    if sample_category == "Humain":
        detail = st.radio(
            "Site corporel",
            ["Intestinal humain (Gut)", "Cutané humain (Skin)", "Oral humain"],
            horizontal=True,
        )
    elif sample_category == "Animal":
        detail = st.selectbox(
            "Espèce",
            [
                "Souris (Mus musculus)", "Rat (Rattus norvegicus)",
                "Chien (Canis lupus)", "Chat (Felis catus)",
                "Cochon (Sus scrofa)", "Lapin (Oryctolagus)",
                "Poulet (Gallus gallus)", "Chèvre (Capra hircus)",
                "Mouton (Ovis aries)",
            ],
        )
    elif sample_category == "Environnemental":
        detail = st.radio(
            "Type d'environnement",
            ["Sol (Soil)", "Océan / Eau marine", "Eau douce / Lac / Rivière",
             "Sédiment", "Nourriture / Aliment"],
            horizontal=True,
        )
    else:
        detail = "Autre / Je ne sais pas"
        st.info("Nous utiliserons GlobDB comme base de référence généraliste.")

envo_key, host_taxon_key = SAMPLE_MAP.get(detail, (None, None))

st.markdown("---")

# ══════════════════════════════════════════════════════════
# SECTION 3 — Organismes cibles
# ══════════════════════════════════════════════════════════
st.markdown("## 3 · Organismes cibles")

col_org, col_analysis = st.columns(2)

with col_org:
    selected_organisms = st.multiselect(
        "Organismes à identifier",
        list(TAXON_MAP.keys()),
        default=["Bactéries", "Archées"],
        help="Sélectionnez les groupes taxonomiques que vous souhaitez profiler.",
    )
    if "Virus" in selected_organisms or "Eucaryotes" in selected_organisms:
        st.warning(
            "⚠️ Peu d'outils de profiling couvrent les Virus et Eucaryotes. "
            "Les recommandations ci-dessous peuvent être limitées."
        )

with col_analysis:
    extra_analyses = st.multiselect(
        "Analyses complémentaires souhaitées",
        ["Profiling fonctionnel", "Strain-level profiling"],
        help="En plus du profiling taxonomique de base.",
    )
    if "Profiling fonctionnel" in extra_analyses:
        st.info("💡 Le profiling fonctionnel est disponible via meteor / HUMAnN3.")
    if "Strain-level profiling" in extra_analyses:
        st.info("💡 Le strain-level profiling est disponible via MetaPhlAn / StrainPhlAn.")

taxon_keys = [TAXON_MAP[o] for o in selected_organisms]

st.markdown("---")

# ══════════════════════════════════════════════════════════
# MOTEUR DE RECOMMANDATION
# ══════════════════════════════════════════════════════════

def score_db(db: dict) -> int:
    """Score de pertinence 0-3 d'une base de données."""
    score = 0
    if envo_key and db_matches_sample(db, envo_key):
        score += 1
    if host_taxon_key and db_matches_origin(db, host_taxon_key):
        score += 1
    if taxon_keys and db_matches_taxon(db, taxon_keys):
        score += 1
    return score


# Filtrer et trier les bases de données
scored_dbs = [
    (db_id, db, score_db(db))
    for db_id, db in databases.items()
]
scored_dbs.sort(key=lambda x: -x[2])

# Garder celles avec score > 0 ou toutes si rien ne correspond
best_dbs = [(db_id, db, sc) for db_id, db, sc in scored_dbs if sc > 0]
if not best_dbs:
    best_dbs = scored_dbs[:3]  # fallback : top 3 génériques

# Trouver les outils compatibles avec ces BDs ET le type de reads
recommended = []
for db_id, db, sc in best_dbs:
    compat_tool_ids = db_compatible_tools(db)
    for tool_id in compat_tool_ids:
        tool = tools.get(tool_id)
        if tool is None:
            continue
        if not tool_supports(tool, reads_key):
            continue
        dl_variants = db_download_info(db, tool_id)
        recommended.append({
            "db_id":      db_id,
            "db":         db,
            "db_score":   sc,
            "tool_id":    tool_id,
            "tool":       tool,
            "dl_variants": dl_variants,
        })

# Dédoublonner (même outil avec plusieurs BDs → garder le meilleur score)
seen_tools: dict[str, dict] = {}
for rec in recommended:
    tid = rec["tool_id"]
    if tid not in seen_tools or rec["db_score"] > seen_tools[tid]["db_score"]:
        seen_tools[tid] = rec
best_recommendations = sorted(seen_tools.values(), key=lambda r: -r["db_score"])

# ══════════════════════════════════════════════════════════
# SECTION 4 — Résultats
# ══════════════════════════════════════════════════════════
st.markdown("## 4 · Recommandations")

if not best_recommendations:
    st.warning(
        "Aucun outil ne correspond exactement à vos critères dans le catalogue actuel. "
        "Consultez l'équipe ou utilisez GlobDB avec SingleM/Sylph comme point de départ."
    )
else:
    st.success(
        f"**{len(best_recommendations)} outil(s)** compatible(s) trouvé(s) "
        f"pour votre configuration."
    )

    for i, rec in enumerate(best_recommendations):
        tool   = rec["tool"]
        db     = rec["db"]
        db_id  = rec["db_id"]
        t_name = tool.get("name", rec["tool_id"])
        db_name= db.get("name", db_id)

        with st.expander(f"{'⭐ ' if i == 0 else ''}**{t_name}** avec **{db_name}**", expanded=(i == 0)):

            col_tool, col_db = st.columns(2)

            # ── Colonne outil ──────────────────────────
            with col_tool:
                st.markdown(f"### 🔧 {t_name}")
                st.markdown(f"*{tool.get('description', tool.get('approach_detail', '—'))}*")

                props = {
                    "Version":          tool.get("latest_release", "—"),
                    "Short reads":      "✅" if tool.get("supports_shortreads") else "❌",
                    "Long reads":       "✅" if tool.get("supports_longreads")  else "❌",
                    "Profiling fonctionnel": "✅" if tool.get("functional_profiling") else "❌",
                    "Strain-level":     "✅" if tool.get("strain_level") else "❌",
                    "RAM estimée":      f"{tool.get('ram', '—')} GB" if tool.get("ram") else "—",
                    "Citations":        tool.get("citations_count", "—"),
                }
                for k, v in props.items():
                    st.markdown(f"**{k}** : {v}")

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

                if tool.get("sub_module"):
                    sm = tool["sub_module"]
                    st.markdown(
                        f"📦 **Sous-module** : {sm.get('name', sm.get('@id', '?'))}"
                    )

            # ── Colonne base de données ────────────────
            with col_db:
                st.markdown(f"### 🗄️ {db_name}")

                taxa = taxon_labels(db)
                st.markdown(f"**Taxons couverts** : {', '.join(taxa) if taxa else '—'}")
                st.markdown(f"**Échantillon** : {sample_label(db)}")
                st.markdown(f"**Origine** : {origin_label(db)}")
                st.markdown(f"**Release** : {db.get('latest_release') or db.get('release') or '—'}")

                if db.get("homepage"):
                    st.markdown(f"🌐 [Site officiel]({db['homepage']})")
                if db.get("doi"):
                    st.markdown(f"📄 [Publication]({db['doi']})")

                # Variantes de téléchargement
                dl = rec["dl_variants"]
                if dl:
                    st.markdown("#### 💾 Téléchargement")
                    for variant in dl:
                        v_name = variant.get("name", "default")
                        v_size = variant.get("size")
                        v_dl   = variant.get("download", "")
                        v_ifb  = variant.get("ifb_server")
                        access = variant.get("access_method", "url")

                        size_str = f" — {v_size} GB" if v_size else ""
                        st.markdown(f"**{v_name}**{size_str}")

                        if access == "cli":
                            st.code(v_dl, language="bash")
                        elif v_dl and v_dl.startswith("http"):
                            st.markdown(f"⬇️ [Télécharger]({v_dl})")
                        elif v_dl:
                            st.code(v_dl, language="bash")

                        if v_ifb:
                            st.markdown(
                                f"🖥️ **IFB {v_ifb['name']}** : `{v_ifb['path']}`"
                            )

# ──────────────────────────────────────────────────────────
# SECTION 5 — Tableau comparatif de toutes les BDs
# ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📊 Voir toutes les bases de données du catalogue", expanded=False):
    rows = []
    for db_id, db in databases.items():
        rows.append({
            "ID":           db_id,
            "Nom":          db.get("name", db_id),
            "Taxons":       ", ".join(taxon_labels(db)) or "—",
            "Échantillon":  sample_label(db),
            "Origine":      origin_label(db),
            "Release":      db.get("latest_release") or db.get("release") or "—",
            "Outils compat.": ", ".join(db_compatible_tools(db)) or "—",
        })
    st.dataframe(rows, use_container_width=True)

# ──────────────────────────────────────────────────────────
# RESET
# ──────────────────────────────────────────────────────────
st.markdown("---")
if st.button("🔄 Réinitialiser"):
    st.rerun()
