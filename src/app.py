""" """

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Helper: display images only if the file exists to avoid Streamlit media errors
def _maybe_logo(path: str, *args, **kwargs):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return st.logo(str(p), *args, **kwargs)
    except Exception:
        # fall back silently
        return None


def _maybe_image(path: str, *args, **kwargs):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return st.image(str(p), *args, **kwargs)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — doit être le premier appel Streamlit
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_DIR = Path(__file__).parent.parent / "data" / "schemas"
try:
    from src.catalogue_utils import inject_jsonld_schemas  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - fallback for streamlit run src/app.py
    from catalogue_utils import inject_jsonld_schemas  # noqa: E402

st.set_page_config(
    page_title="Profiling Taxonomique — Catalogue",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_jsonld_schemas(
    SCHEMA_DIR / "database_schema.json",
    SCHEMA_DIR / "tool_schema.json",
)


_maybe_logo(
    str(Path(__file__).parent.parent / "data" / "images" / "logos-ifb-elixir.png"),
    size="large",
)
_maybe_image(
    str(Path(__file__).parent.parent / "data" / "images" / "logos-ifb-elixir.png"),
    caption=None,
    width=800,
)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DB_DIR = PROJECT_ROOT / "data" / "databases"
TOOLS_DIR = PROJECT_ROOT / "data" / "tools"

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
try:
    from src.catalogue_utils import (SAMPLE_CATEGORIES, SAMPLE_FILTER,  # noqa: E402
                                 TAXON_IRI, _to_list, db_release_str,
                                 is_about_label, load_catalogue, origin_label,
                                 recommend, sample_label, seq_scope_label,
                                 taxon_labels, taxonomy_badge)
except ModuleNotFoundError:  # pragma: no cover - fallback for streamlit run src/app.py
    from catalogue_utils import (SAMPLE_CATEGORIES, SAMPLE_FILTER,  # noqa: E402
                                 TAXON_IRI, _to_list, db_release_str,
                                 is_about_label, load_catalogue, origin_label,
                                 recommend, sample_label, seq_scope_label,
                                 taxon_labels, taxonomy_badge)

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────
databases, tools = load_catalogue(DB_DIR, TOOLS_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigation")
    page = st.radio(
        "",
        ["🏠 Home", "🔍 Survey", "📊 Catalog"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.metric("Databases", len(databases))
    st.metric("Tools", len(tools))


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — SURVEY
# ═════════════════════════════════════════════════════════════════════════════
def render_home():
    st.markdown("# 🏠 Home — Taxonomic Profiling")
    # Optional PDF preview (kept if file exists in your data/images or data root)
    try:
        st.pdf(
            str(Path(__file__).parent.parent / "data" / "homepage_catalogue.pdf"),
            height="stretch",
        )
    except Exception:
        pass
    st.markdown(
        "Welcome to the catalogue and recommendation assistant for taxonomic profiling. "
        "Use the navigation menu at the top-left to go to the Survey or the Catalog."
    )
    st.markdown("---")
    st.markdown("Quick facts:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Databases", len(databases))
    with col2:
        st.metric("Tools", len(tools))
    with col3:
        st.markdown("\n")
        st.caption("Select '🔍 Survey' to get personalized recommendations.")


def render_questionnaire():
    st.markdown("# 🧬 Recommendation Assistant — Taxonomic Profiling")
    st.markdown(
        "Answer the questions below to get tools and databases suited to your sample and goals."
    )
    st.markdown("---")

    # Q1 — Séquençage
    st.markdown("## 1 Sequencing method")
    reads_choice = st.radio(
        "Type of reads",
        ["Short Reads (Illumina, etc.)", "Long Reads (PacBio, Nanopore, etc.)"],
        horizontal=True,
    )
    reads_key = "Short Reads" if "Short" in reads_choice else "Long Reads"
    st.markdown("---")

    # Q2 — Sample
    st.markdown("## 2 · Sample type")
    col_cat, col_detail = st.columns([1, 2])
    with col_cat:
        category = st.selectbox("Main category", list(SAMPLE_CATEGORIES.keys()))
    with col_detail:
        options = SAMPLE_CATEGORIES[category]
        if len(options) == 1:
            detail = options[0]
            st.info(f"Selected: **{detail}**")
        elif category == "Humain":
            detail = st.radio("Body site", options, horizontal=True)
        elif category == "Animal":
            detail = st.selectbox("Species", options)
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

    # Q3 — Organisms & analyses
    st.markdown("## 3 · Target organisms & desired analyses")
    col_org, col_extra = st.columns(2)
    with col_org:
        selected_orgs = st.multiselect(
            "Taxons to identify",
            list(TAXON_IRI.keys()),
            default=["Bacteria", "Archaea"],
        )
        if not selected_orgs:
            st.warning("Select at least one organism group to get recommendations.")
        if "Virus" in selected_orgs or "Eukaryota" in selected_orgs:
            st.warning(
                "⚠️ Few tools support virus or eukaryote profiling — expect limited recommendations."
            )
    with col_extra:
        wants_strain = st.checkbox("🔬 Strain-level profiling")
        wants_func = st.checkbox("⚙️ Functional profiling")
        if wants_func:
            func_tools = [
                t.get("name", tid)
                for tid, t in tools.items()
                if t.get("functional_profiling")
            ]
            if func_tools:
                st.info(
                    f"💡 Functional profiling supported by: {', '.join(func_tools)}."
                )
            else:
                st.info(
                    "💡 No tool in the catalogue currently supports functional profiling with your filters."
                )
        if wants_strain:
            strain_tools = [
                t.get("name", tid) for tid, t in tools.items() if t.get("strain_level")
            ]
            if strain_tools:
                st.info(f"💡 Strain-level supported by: {', '.join(strain_tools)}.")
            else:
                st.info(
                    "💡 No tool in the catalogue currently supports strain-level profiling with your filters."
                )
    st.markdown("---")

    # Q4 — Advanced parameters
    with st.expander("⚙️ Advanced settings", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            pref_taxo = st.radio(
                "Reference database taxonomy",
                ["Any", "GTDB", "NCBI"],
                horizontal=True,
            )
        with col_b:
            max_ram = st.slider("Available RAM (GB)", 2, 512, 512, 2)
    st.markdown("---")

    # Recommendations
    st.markdown("## 4 · Recommendations")

    if not selected_orgs:
        st.warning("Please select at least one organism group (section 3).")
        return

    # Map English UI value for 'Any' back to the recommender's expected French token
    # (the recommendation engine was written to check for "Indifférent").
    pref_taxo_for_reco = (
        "Indifférent"
        if str(pref_taxo).strip().lower() in ("any", "indifferent", "indifférent")
        else pref_taxo
    )

    recs = recommend(
        databases,
        tools,
        envo_key,
        host_key,
        selected_orgs,
        reads_key,
        pref_taxo_for_reco,
        wants_strain,
        wants_func,
        max_ram,
    )

    if not recs:
        st.warning(
            "No tool matches your criteria exactly.\n"
            "Try loosening filters or check your JSON files."
        )
        # Diagnostic help: show inputs passed to the recommender and dataset sizes
        try:
            st.markdown("---")
            st.markdown("**Debug: recommendation inputs**")
            st.write(
                {
                    "envo_key": envo_key,
                    "host_key": host_key,
                    "selected_orgs": selected_orgs,
                    "reads_key": reads_key,
                    "pref_taxo": pref_taxo,
                    "wants_strain": wants_strain,
                    "wants_func": wants_func,
                    "max_ram": max_ram,
                }
            )
            st.markdown("**Loaded counts**")
            st.write({"databases": len(databases), "tools": len(tools)})
        except Exception:
            pass
        return

    st.success(f"**{len(recs)} outil(s)** trouvé(s).")

    for i, rec in enumerate(recs):
        tool = rec["tool"]
        db = rec["db"]
        db_id = rec["db_id"] or "—"
        t_name = tool.get("name", rec["tool_id"])
        db_name = db.get("name", db_id) if db else db_id
        rel = rec.get("db_rel") or {}
        releases = rec["releases"]

        ext_of = rec.get("extension_of")
        ext_level = rec.get("extension_level")

        badges = []
        if tool.get("strain_level"):
            badges.append("🔬 strain-level")
        if tool.get("functional_profiling"):
            badges.append("⚙️ functional")
        if ext_of:
            badges.append(
                "🔗 extension (parent)" if ext_level == "parent" else "🔗🔗 extension (grand-parent)"
            )
        badge_str = "  ·  ".join(badges)

        with st.expander(
            f"{'⭐ ' if i == 0 else ''}"
            f"**{t_name}**  +  **{db_name}**"
            f"{'  ·  ' + badge_str if badge_str else ''}",
            expanded=(i == 0),
        ):
            col_t, col_d = st.columns(2)
            with col_t:
                st.markdown(f"### 🔧 {t_name}")
                desc = tool.get("description") or tool.get("approach_detail") or ""
                if desc:
                    st.markdown(f"*{desc}*")
                sr_v = "✅" if tool.get("supports_shortreads") else "❌"
                lr_v = "✅" if tool.get("supports_longreads") else "❌"
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown(f"**Version** : {tool.get('latest_release') or '—'}")
                    st.markdown(f"**Short reads** : {sr_v}")
                    st.markdown(f"**Long reads** : {lr_v}")
                    st.markdown(f"**RAM** : {tool.get('ram') or '—'} GB")
                with col_p2:
                    st.markdown(
                        f"**Strain-level** : {'✅' if tool.get('strain_level') else '❌'}"
                    )
                    st.markdown(
                        f"**Functional profiling** : {'✅' if tool.get('functional_profiling') else '❌'}"
                    )
                    st.markdown(f"**Citations** : {tool.get('citations_count') or '—'}")
                    st.markdown(f"**Taxonomy** : {tool.get('taxonomy') or '—'}")
                links = []
                if tool.get("repo"):
                    links.append(f"[GitHub]({tool['repo']})")
                if tool.get("doc"):
                    links.append(f"[Doc]({tool['doc']})")
                if tool.get("bio_tools"):
                    links.append(f"[bio.tools]({tool['bio_tools']})")
                if tool.get("doi"):
                    links.append(f"[Publication]({tool['doi']})")
                if links:
                    st.markdown("🔗 " + "  ·  ".join(links))

            with col_d:
                st.markdown(f"### 🗄️ {db_name}")
                ts_display = taxonomy_badge(rel.get("taxonomy_system"))
                if ts_display != "—":
                    color = "#1D9E75" if "GTDB" in ts_display else "#534AB7"
                    st.markdown(
                        f"<span style='background:{color};color:white;"
                        f"padding:2px 10px;border-radius:12px;font-weight:bold;"
                        f"font-size:13px'>{ts_display}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")
                if releases:
                    st.markdown(f"**Compatible releases**: {', '.join(releases)}")
                if db:
                    taxa = taxon_labels(db)
                    if taxa:
                        st.markdown(f"**Taxons** : {', '.join(taxa)}")
                    for label, fn in [
                        ("Sample", sample_label),
                        ("Origin", origin_label),
                        ("Sequences", seq_scope_label),
                        ("is_about", is_about_label),
                    ]:
                        val = fn(db)
                        if val != "—":
                            st.markdown(f"**{label}** : {val}")
                    st.markdown(f"**Release** : {db_release_str(db)}")
                    if db.get("homepage"):
                        st.markdown(f"🌐 [Official site]({db['homepage']})")
                    if db.get("doi"):
                        st.markdown(f"📄 [Publication]({db['doi']})")
                else:
                    st.caption(
                        f"ℹ️ `{db_id}.json` absent from `data/databases/` "
                        "— add it for more complete details."
                    )
                if ext_of:
                    child_name = databases.get(ext_of, {}).get("name", ext_of)
                    level_txt = "parent" if ext_level == "parent" else "grand-parent"
                    st.info(
                        f"ℹ️ La base **{child_name}** est comprise dans **{db_name}**, "
                        f"et l'outil **{t_name}** peut aussi utiliser **{db_name}** ({level_txt})."
                    )
                dl = rec["dl"]
                if dl:
                    st.markdown("#### 💾 Downloads")
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
                            st.markdown(f"⬇️ [Download]({v_url})")
                        if v_ifb and isinstance(v_ifb, dict):
                            st.markdown(
                                f"🖥️ **IFB {v_ifb.get('name','')}** :  \n"
                                f"`{v_ifb.get('path','')}`"
                            )

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION IFB — Scripts SLURM et Notebooks Jupyter
    # ═══════════════════════════════════════════════════════════════════════
    if recs:
        st.markdown("---")
        st.markdown("## 5 · Run on IFB cluster")
        st.markdown(
            "Generate a SLURM sbatch script or a Jupyter notebook to run the analysis "
            "on the IFB core-cluster."
        )

        # Choisir le couple outil/BD à exporter
        rec_labels = [
            f"{r['tool'].get('name', r['tool_id'])}  +  "
            f"{r['db'].get('name', r['db_id']) if r['db'] else r['db_id']}"
            for r in recs
        ]
        chosen_idx = st.selectbox(
            "Tool / database pair",
            range(len(recs)),
            format_func=lambda i: rec_labels[i],
            key="ifb_rec_sel",
        )
        rec_sel = recs[chosen_idx]

        # Paramètres utilisateur
        with st.expander("⚙️ Execution parameters", expanded=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                input_fastq = st.text_input(
                    "Input FASTQ path",
                    value="/path/to/sample.fastq.gz",
                    key="ifb_fq",
                )
                db_path_override = st.text_input(
                    "Database path (leave empty = auto-detect IFB path)",
                    value="",
                    key="ifb_db",
                    placeholder="Auto-detected from the JSON",
                )
            with col_i2:
                tool_key_sel = (
                    rec_sel["tool_id"].lower().replace("-", "").replace("_", "")
                )
                _defaults = {
                    "sylph": (8, 32, "02:00:00"),
                    "singlem": (8, 8, "04:00:00"),
                    "meteor": (16, 64, "08:00:00"),
                    "kraken": (16, 128, "04:00:00"),
                    "kraken2": (16, 128, "04:00:00"),
                    "metaphlan": (8, 32, "04:00:00"),
                    "metabuli": (16, 64, "06:00:00"),
                }.get(tool_key_sel, (8, 32, "04:00:00"))
                n_cpus = st.slider("CPUs", 1, 64, _defaults[0], key="ifb_cpu")
                n_mem = st.slider("RAM (GB)", 4, 512, _defaults[1], key="ifb_mem")
                walltime = st.text_input(
                    "Walltime (HH:MM:SS)", _defaults[2], key="ifb_time"
                )

        user_params = {
            "input_fastq": input_fastq,
            "cpus": n_cpus,
            "mem": n_mem,
            "time": walltime,
        }
        if db_path_override.strip():
            user_params["db_path"] = db_path_override.strip()

        tab_sbatch, tab_nb = st.tabs(
            ["📄 SLURM script (sbatch)", "📓 Jupyter Notebook"]
        )

        # ── Tab SLURM ──────────────────────────────────────────────────────
        with tab_sbatch:
            try:
                from ifb_export import make_sbatch

                script = make_sbatch(
                    tool=rec_sel["tool"],
                    db=rec_sel["db"],
                    db_id=rec_sel["db_id"],
                    db_rel=rec_sel.get("db_rel") or {},
                    user_params=user_params,
                )
                st.code(script, language="bash")
                fname = f"{rec_sel['tool_id']}_{rec_sel['db_id']}.sh"
                st.download_button(
                    label="⬇️ Download .sh script",
                    data=script,
                    file_name=fname,
                    mime="text/x-sh",
                    key="dl_sbatch",
                )
                st.markdown(
                    """
**How to use this script on IFB:**
```bash
# 1. Copy the script to the cluster
scp """
                    + fname
                    + """ login@core.cluster.france-bioinformatique.fr:~/

# 2. Connect and submit the job
ssh login@core.cluster.france-bioinformatique.fr
sbatch """
                    + fname
                    + """
```
"""
                )
            except ImportError:
                st.error(
                    "Module `ifb_export.py` introuvable — placez-le dans le même dossier que `app.py`."
                )

        # ── Tab Notebook ───────────────────────────────────────────────────
        with tab_nb:
            try:
                from ifb_export import make_notebook, notebook_to_json

                nb = make_notebook(
                    tool=rec_sel["tool"],
                    db=rec_sel["db"],
                    db_id=rec_sel["db_id"],
                    db_rel=rec_sel.get("db_rel") or {},
                    user_params=user_params,
                )
                nb_json = notebook_to_json(nb)
                tool_name_nb = rec_sel["tool"].get("name", rec_sel["tool_id"])
                db_name_nb = (
                    rec_sel["db"].get("name", rec_sel["db_id"])
                    if rec_sel["db"]
                    else rec_sel["db_id"]
                )
                nb_fname = f"tutorial_{rec_sel['tool_id']}_{rec_sel['db_id']}.ipynb"

                st.download_button(
                    label=f"⬇️ Download notebook {nb_fname}",
                    data=nb_json,
                    file_name=nb_fname,
                    mime="application/x-ipynb+json",
                    key="dl_nb",
                )
                st.markdown(f"""
**How to open this notebook on IFB OpenOnDemand:**

1. Download the file `{nb_fname}` above
2. Log in to https://ondemand.cluster.france-bioinformatique.fr
3. Go to **Files** → upload `{nb_fname}` into your home directory
4. Open **Jupyter Notebook** from the menu and navigate to the file
5. Activate your conda environment/kernel before running the notebook

> **Tip:** Edit the `INPUT_FASTQ` and `DB_PATH` cells to your paths before executing.
""")
                # Aperçu des cellules
                with st.expander("👁️ Notebook preview", expanded=False):
                    for cell in nb.get("cells", []):
                        if cell["cell_type"] == "markdown":
                            src = cell["source"]
                            if src.startswith("#"):
                                st.markdown(src.split("\n")[0])
                        elif cell["cell_type"] == "code":
                            st.code(
                                cell["source"][:300]
                                + ("..." if len(cell["source"]) > 300 else ""),
                                language="python",
                            )

            except ImportError:
                st.error(
                    "Module `ifb_export.py` not found — place it in the same directory as `app.py`."
                )

    st.markdown("---")
    if st.button("🔄 Reset"):
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CATALOGUE
# ═════════════════════════════════════════════════════════════════════════════

_C = {
    "tool": "#534AB7",
    "db": "#1D9E75",
    "db_miss": "#555566",
    "edge_gtdb": "#1D9E75",
    "edge_ncbi": "#534AB7",
    "edge_part": "#888780",
    "text": "#FFFFFF",
    "bg": "#1A1A2E",
}


def render_catalogue():
    st.markdown("# 📊 Catalog — Tools & Databases")
    st.markdown(f"**{len(tools)} tools** · **{len(databases)} databases**")
    st.markdown("---")

    tab_graph, tab_tools, tab_dbs = st.tabs(
        [
            "🕸️ Relations graph",
            "🔧 Tools",
            "🗄️ Databases",
        ]
    )

    with tab_graph:
        _tab_graph()
    with tab_tools:
        _tab_tools()
    with tab_dbs:
        _tab_databases()


# ─────────────────────────────────────────────────────────────────────────────
# TAB GRAPHE
# ─────────────────────────────────────────────────────────────────────────────
def _tab_graph():
    import math

    import networkx as nx
    import numpy as np
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    v_ego, v_matrix,v_cards = st.tabs(
        [
            "🕸️ Ego-graph",
            "🔲 Matrix",
            "🃏 Cards",
        ]
    )

    # ── VUE 1 : EGO-GRAPH ─────────────────────────────────────────────────────
    with v_ego:
        st.markdown("Select a tool or database to see **its direct connections**.")
        BG = "#0D1117"

        all_names = {t.get("name", tid): ("tool", tid) for tid, t in tools.items()} | {
            db.get("name", did): ("db", did) for did, db in databases.items()
        }
        chosen = st.selectbox("Central node", ["—"] + sorted(all_names), key="ego_sel")
        if chosen == "—":
            st.info("Choose a tool or database above.")
        else:
            kind, node_id = all_names[chosen]

            nodes: dict[str, dict] = {}
            edges: list[tuple] = []

            def add_tool_node(tid):
                t = tools.get(tid, {})
                nodes[tid] = dict(
                    kind="tool",
                    label=t.get("name", tid),
                    cit=t.get("citations_count") or 0,
                    version=t.get("latest_release") or "—",
                    sr="✅" if t.get("supports_shortreads") else "❌",
                    lr="✅" if t.get("supports_longreads") else "❌",
                )

            def add_db_node(did):
                db = databases.get(did)
                nodes[did] = dict(
                    kind="db" if db else "db_missing",
                    label=db.get("name", did) if db else did,
                    release=db_release_str(db) if db else "—",
                    taxa=", ".join(taxon_labels(db)) if db else "—",
                    sample=sample_label(db) if db else "—",
                )

            if kind == "tool":
                add_tool_node(node_id)
                for u in _to_list(tools[node_id].get("uses_databases")):
                    if isinstance(u, dict) and u.get("@id"):
                        did = u["@id"]
                        add_db_node(did)
                        ts = taxonomy_badge(u.get("taxonomy_system"))
                        edges.append((node_id, did, ts))
            else:
                add_db_node(node_id)
                for tid, tool in tools.items():
                    for u in _to_list(tool.get("uses_databases")):
                        if isinstance(u, dict) and u.get("@id") == node_id:
                            add_tool_node(tid)
                            ts = taxonomy_badge(u.get("taxonomy_system"))
                            edges.append((tid, node_id, ts))
                db = databases.get(node_id, {})
                for part in _to_list(db.get("hasPart")):
                    if isinstance(part, dict) and part.get("@id"):
                        add_db_node(part["@id"])
                        edges.append((node_id, part["@id"], "hasPart"))

            pos = {}
            others = [nid for nid in nodes if nid != node_id]
            pos[node_id] = (0.0, 0.0)
            for i, nid in enumerate(others):
                angle = 2 * math.pi * i / max(len(others), 1)
                pos[nid] = (math.cos(angle) * 2.2, math.sin(angle) * 2.2)

            traces = []
            ECOL = {"GTDB": "#17C3B2", "NCBI": "#AFA9EC", "hasPart": "#888780"}
            for u, v, ts in edges:
                x0, y0 = pos.get(u, (0, 0))
                x1, y1 = pos.get(v, (0, 0))
                col = (
                    ECOL.get(ts, "#17C3B2")
                    if "GTDB" in ts
                    else (ECOL.get("hasPart") if ts == "hasPart" else "#AFA9EC")
                )
                traces.append(
                    go.Scatter(
                        x=[x0, x1, None],
                        y=[y0, y1, None],
                        mode="lines",
                        line=dict(color=col, width=2),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                traces.append(
                    go.Scatter(
                        x=[mx],
                        y=[my],
                        mode="text",
                        text=[ts],
                        textfont=dict(color=col, size=10),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

            for nid, nd in nodes.items():
                x, y = pos.get(nid, (0, 0))
                is_center = nid == node_id
                if nd["kind"] == "tool":
                    col = "#7B5EA7" if not is_center else "#BBA3E8"
                    shape = "circle"
                    size = 28 if is_center else 20
                    hover = (
                        f"<b>{nd['label']}</b><br>"
                        f"Citations: {nd['cit']}<br>"
                        f"Version: {nd['version']}<br>"
                        f"SR : {nd['sr']}  LR : {nd['lr']}"
                    )
                else:
                    col = "#1D9E75" if nd["kind"] == "db" else "#444"
                    col = "#2ECC8A" if is_center else col
                    shape = "square"
                    size = 28 if is_center else 18
                    hover = (
                        f"<b>{nd['label']}</b><br>"
                        f"Release: {nd['release']}<br>"
                        f"Taxa: {nd['taxa']}<br>"
                        f"Sample: {nd['sample']}"
                    )
                traces.append(
                    go.Scatter(
                        x=[x],
                        y=[y],
                        mode="markers+text",
                        marker=dict(
                            symbol=shape,
                            size=size,
                            color=col,
                            line=dict(color="#FFFFFF", width=1.5),
                        ),
                        text=[nd["label"]],
                        textposition="top center",
                        textfont=dict(
                            color="#FFFFFF" if is_center else "#CCCCCC",
                            size=13 if is_center else 11,
                        ),
                        hovertemplate=hover + "<extra></extra>",
                        showlegend=False,
                    )
                )

            fig = go.Figure(traces)
            fig.update_layout(
                paper_bgcolor=BG,
                plot_bgcolor=BG,
                height=520,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[-3.2, 3.2],
                ),
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[-3.2, 3.2],
                ),
                hovermode="closest",
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config=dict(scrollZoom=True),
                key="ego_fig",
            )
            st.caption(f"{len(nodes)-1} direct connection(s) from « {chosen} »")

    # ── VUE 2 : MATRICE ───────────────────────────────────────────────────────
    with v_matrix:
        st.markdown(
            "Each cell shows the **taxonomy** (GTDB / NCBI) "
            "of the tool ↔ database relationship."
        )

        all_db_ids: set[str] = set()
        for t in tools.values():
            for u in _to_list(t.get("uses_databases")):
                if isinstance(u, dict) and u.get("@id"):
                    all_db_ids.add(u["@id"])

        tool_ids = sorted(
            tools.keys(), key=lambda k: -(tools[k].get("citations_count") or 0)
        )
        db_ids = sorted(all_db_ids)
        tool_labels = [tools[k].get("name", k) for k in tool_ids]
        db_labels = [
            databases[d].get("name", d) if d in databases else d for d in db_ids
        ]

        Z = np.zeros((len(tool_ids), len(db_ids)), dtype=int)
        hover = [["" for _ in db_ids] for _ in tool_ids]

        for ti, tid in enumerate(tool_ids):
            tool = tools[tid]
            for u in _to_list(tool.get("uses_databases")):
                if not isinstance(u, dict) or not u.get("@id"):
                    continue
                did = u["@id"]
                if did not in db_ids:
                    continue
                di = db_ids.index(did)
                ts = u.get("taxonomy_system", "")
                has_gtdb = "gtdb" in str(ts).lower()
                has_ncbi = "ncbi" in str(ts).lower()
                if has_gtdb and has_ncbi:
                    Z[ti, di] = 3
                elif has_gtdb:
                    Z[ti, di] = 1
                elif has_ncbi:
                    Z[ti, di] = 2
                else:
                    Z[ti, di] = 1
                ts_str = taxonomy_badge(ts)
                rels = ", ".join(str(r) for r in _to_list(u.get("release")) if r)
                hover[ti][di] = (
                    f"<b>{tool_labels[ti]}</b> → <b>{db_labels[di]}</b><br>"
                    f"Taxonomie : {ts_str}<br>"
                    f"Releases : {rels or '—'}"
                )

        colorscale = [
            [0, "#1A1F2E"],
            [0.16, "#1A1F2E"],
            [0.16, "#17C3B2"],
            [0.5, "#17C3B2"],
            [0.5, "#AFA9EC"],
            [0.83, "#AFA9EC"],
            [0.83, "#F5A623"],
            [1.0, "#F5A623"],
        ]

        fig = go.Figure(
            go.Heatmap(
                z=Z,
                x=db_labels,
                y=tool_labels,
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
                colorscale=colorscale,
                zmin=0,
                zmax=3,
                showscale=False,
                xgap=2,
                ygap=2,
            )
        )
        fig.update_layout(
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            height=max(300, len(tool_ids) * 38 + 120),
            margin=dict(l=10, r=10, t=10, b=120),
            xaxis=dict(
                tickangle=-45, tickfont=dict(color="#9FE1CB", size=11), side="bottom"
            ),
            yaxis=dict(tickfont=dict(color="#AFA9EC", size=12), autorange="reversed"),
            font=dict(color="#CCC"),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config=dict(displayModeBar=False),
            key="matrix_fig",
        )
        st.markdown(
            "<div style='font-size:12px;color:#888'>"
            "<span style='background:#17C3B2;padding:2px 10px;border-radius:4px;color:#000'>GTDB</span> &nbsp;"
            "<span style='background:#AFA9EC;padding:2px 10px;border-radius:4px;color:#000'>NCBI</span> &nbsp;"
            "<span style='background:#F5A623;padding:2px 10px;border-radius:4px;color:#000'>GTDB + NCBI</span> &nbsp;"
            "<span style='background:#1A1F2E;padding:2px 10px;border-radius:4px;border:1px solid #444;color:#888'>—</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── VUE 4 : CARDS ─────────────────────────────────────────────────────────
    with v_cards:
        st.markdown("Tools sorted by citations, with their databases.")

        sort_by = st.selectbox(
            "Sort by",
            ["Citations (↓)", "Name (A→Z)", "Version"],
            key="cards_sort",
        )

        sorted_tools = list(tools.items())
        if sort_by == "Citations (↓)":
            sorted_tools.sort(key=lambda x: -(x[1].get("citations_count") or 0))
        elif sort_by == "Nom (A→Z)":
            sorted_tools.sort(key=lambda x: x[1].get("name", x[0]).lower())
        elif sort_by == "Version":
            sorted_tools.sort(key=lambda x: x[1].get("latest_release") or "")

        cols = st.columns(3)
        for i, (tid, tool) in enumerate(sorted_tools):
            cit = tool.get("citations_count") or 0
            name = tool.get("name", tid)
            version = tool.get("latest_release") or "—"
            sr = "✅" if tool.get("supports_shortreads") else "❌"
            lr = "✅" if tool.get("supports_longreads") else "❌"
            strain = "✅" if tool.get("strain_level") else "❌"

            dbs_used = []
            for u in _to_list(tool.get("uses_databases")):
                if not isinstance(u, dict):
                    continue
                did = u.get("@id", "")
                dname = databases[did].get("name", did) if did in databases else did
                ts = taxonomy_badge(u.get("taxonomy_system"))
                col_ts = "#17C3B2" if "GTDB" in ts else "#AFA9EC"
                dbs_used.append(
                    f"<span style='color:{col_ts};font-size:11px'>● {dname}</span>"
                )

            links = ""
            if tool.get("repo"):
                links += f"<a href='{tool['repo']}' target='_blank' style='color:#888;font-size:11px'>GitHub</a> &nbsp;"
            if tool.get("doi"):
                links += f"<a href='{tool['doi']}' target='_blank' style='color:#888;font-size:11px'>Publication</a>"

            bar_w = int(
                160
                * cit
                / max(max(t.get("citations_count") or 0 for _, t in sorted_tools), 1)
            )

            card_html = f"""
<div style='background:#161B27;border:1px solid #2A2F42;border-radius:10px;
padding:14px 16px;margin-bottom:6px;font-family:sans-serif'>
  <div style='font-size:15px;font-weight:600;color:#E0DFFF;margin-bottom:4px'>{name}</div>
  <div style='font-size:11px;color:#666;margin-bottom:8px'>v{version}</div>
  <div style='display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap'>
    <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>SR {sr}</span>
    <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>LR {lr}</span>
    <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>Strain {strain}</span>
  </div>
  <div style='margin-bottom:6px'>{"<br>".join(dbs_used) or "<span style='color:#444;font-size:11px'>aucune BD renseignée</span>"}</div>
  <div style='margin-top:8px'>
    <div style='background:#1A1F2E;border-radius:3px;height:4px;width:160px'>
      <div style='background:#534AB7;height:4px;border-radius:3px;width:{bar_w}px'></div>
    </div>
    <span style='font-size:10px;color:#555'>{cit} citations</span>
  </div>
  <div style='margin-top:6px'>{links}</div>
</div>"""
            with cols[i % 3]:
                st.markdown(card_html, unsafe_allow_html=True)


def _tab_tools():
    import pandas as pd

    st.markdown("### 🔧 Outils")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        f_sr = st.selectbox("Short reads", ["All", "✅", "❌"], key="f_sr")
    with col_b:
        f_lr = st.selectbox("Long reads", ["All", "✅", "❌"], key="f_lr")
    with col_c:
        f_strain = st.selectbox("Strain-level", ["All", "✅", "❌"], key="f_strain")
    with col_d:
        f_taxo = st.selectbox("Taxonomie BD", ["All", "GTDB", "NCBI"], key="f_taxo")
    search_t = st.text_input(
        "🔍 Recherche", "", key="search_t", placeholder="nom, approche, BD…"
    )

    rows = []
    for tid, t in sorted(tools.items()):
        dbs_all = _to_list(t.get("uses_databases"))
        db_names = ", ".join(
            u.get("name") or u.get("@id", "") for u in dbs_all if isinstance(u, dict)
        )
        taxo_set = {
            taxonomy_badge(u.get("taxonomy_system"))
            for u in dbs_all
            if isinstance(u, dict)
        }
        taxo_str = " + ".join(sorted(x for x in taxo_set if x != "—")) or "—"
        rows.append(
            {
                "Name": t.get("name", tid),
                "Type": t.get("type", "—"),
                "Version": t.get("latest_release") or "—",
                "Short reads": "✅" if t.get("supports_shortreads") else "❌",
                "Long reads": "✅" if t.get("supports_longreads") else "❌",
                "Strain-level": "✅" if t.get("strain_level") else "❌",
                "Functional": "✅" if t.get("functional_profiling") else "❌",
                "RAM (GB)": str(t.get("ram") or "—"),
                "DB Taxonomy ": taxo_str,
                "Citations": t.get("citations_count") or 0,
                "DBs used": db_names,
                "Approach": t.get("approach_detail") or "—",
            }
        )

    df = pd.DataFrame(rows)
    if f_sr != "All":
        df = df[df["Short reads"] == f_sr]
    if f_lr != "All":
        df = df[df["Long reads"] == f_lr]
    if f_strain != "All":
        df = df[df["Strain-level"] == f_strain]
    if f_taxo != "All":
        df = df[df["DB Taxonomy "].str.contains(f_taxo, na=False)]
    if search_t:
        m = (
            df["Name"].str.contains(search_t, case=False, na=False)
            | df["Approach"].str.contains(search_t, case=False, na=False)
            | df["DBs used"].str.contains(search_t, case=False, na=False)
        )
        df = df[m]

    st.caption(f"{len(df)} Tools shown")
    display_df = (
        df.sort_values("Citations", ascending=False)
        if not df.empty and "Citations" in df.columns
        else df
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    selected = st.selectbox(
        "Details view",
        ["—"] + sorted(t.get("name", k) for k, t in tools.items()),
        key="sel_tool",
    )
    if selected != "—":
        tid = next((k for k, v in tools.items() if v.get("name", k) == selected), None)
        if tid:
            _tool_card(tools[tid])


def _tool_card(tool: dict):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Name** : {tool.get('name','—')}")
        st.markdown(f"**Type** : {tool.get('type','—')}")
        st.markdown(f"**Version** : {tool.get('latest_release') or '—'}")
        st.markdown(f"**RAM** : {tool.get('ram') or '—'} GB")
        st.markdown(
            f"**Short reads** : {'✅' if tool.get('supports_shortreads') else '❌'}"
        )
        st.markdown(
            f"**Long reads** : {'✅' if tool.get('supports_longreads') else '❌'}"
        )
        st.markdown(f"**Strain-level** : {'✅' if tool.get('strain_level') else '❌'}")
        st.markdown(
            f"**Functional** : {'✅' if tool.get('functional_profiling') else '❌'}"
        )
        st.markdown(f"**Citations** : {tool.get('citations_count') or '—'}")
        desc = tool.get("description") or tool.get("approach_detail") or ""
        if desc:
            st.markdown(f"**Approach** : {desc}")
        sm = tool.get("sub_module")
        if sm and isinstance(sm, dict):
            st.markdown(f"**Submodule** : {sm.get('name', sm.get('@id',''))}")
    with col2:
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
        st.markdown("**Databases used :**")
        for u in _to_list(tool.get("uses_databases")):
            if not isinstance(u, dict):
                continue
            name = u.get("name") or u.get("@id", "?")
            ts = taxonomy_badge(u.get("taxonomy_system"))
            rels = ", ".join(str(r) for r in _to_list(u.get("release")) if r)
            color = "#1D9E75" if "GTDB" in ts else "#534AB7"
            badge = (
                f"<span style='background:{color};color:white;"
                f"padding:1px 7px;border-radius:8px;font-size:11px'>{ts}</span>"
                if ts != "—"
                else ""
            )
            rel_str = f" · r{rels}" if rels else ""
            st.markdown(
                f"- **{name}** &nbsp;{badge}{rel_str}",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# TAB BASES DE DONNÉES
# ─────────────────────────────────────────────────────────────────────────────
def _tab_databases():
    st.markdown("### 🗄️ Databases")

    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        f_taxon = st.multiselect(
            "Covered Taxons",
            ["Bacteria", "Archaea", "Eukaryota", "Viruses", "Fungi"],
            key="f_taxon",
        )
    with col_b:
        search_db = st.text_input(
            "🔍 Search", "", key="search_db", placeholder="name, sample, origin…"
        )
    with col_c:
        sort_by = st.selectbox(
            "Sort by",
            ["Name (A→Z)", "Sub-dbs (↓)"],
            key="db_cards_sort",
        )

    # Filtrage et préparation des données
    filtered_dbs = []
    for db_id, db in databases.items():
        taxa_list = taxon_labels(db)
        taxa_str = ", ".join(taxa_list)
        sample_str = sample_label(db)
        origin_str = origin_label(db)
        name_str = db.get("name", db_id)

        # Filtre Taxons
        if f_taxon and not any(fx in taxa_str for fx in f_taxon):
            continue

        # Filtre Recherche
        if search_db:
            q = search_db.lower()
            if not (
                q in name_str.lower()
                or q in sample_str.lower()
                or q in origin_str.lower()
                or q in db_id.lower()
            ):
                continue

        filtered_dbs.append((db_id, db))

    # Tri
    if sort_by == "Name (A→Z)":
        filtered_dbs.sort(key=lambda x: x[1].get("name", x[0]).lower())
    elif sort_by == "Sub-dbs (↓)":
        filtered_dbs.sort(key=lambda x: -len(_to_list(x[1].get("hasPart"))))

    st.caption(f"{len(filtered_dbs)} Databases shown")

    # Affichage sous forme de cartes
    cols = st.columns(3)
    for i, (db_id, db) in enumerate(filtered_dbs):
        name = db.get("name", db_id)
        release = db_release_str(db)
        taxa = taxon_labels(db)
        sample = sample_label(db)
        origin = origin_label(db)
        parts = _to_list(db.get("hasPart"))

        # Badges pour les taxons
        taxa_badges = "".join(
            f"<span style='background:#1D9E7522;border:1px solid #1D9E75;padding:1px 6px;border-radius:6px;font-size:10px;color:#2ECC8A;margin-right:4px'>{t}</span>"
            for t in taxa
        ) if taxa else "<span style='color:#666;font-size:11px'>—</span>"

        # Détails métadonnées
        details_html = []
        if sample != "—":
            details_html.append(f"<span style='color:#aaa;font-size:11px'>🧪 {sample}</span>")
        if origin != "—":
            details_html.append(f"<span style='color:#aaa;font-size:11px'>🌍 {origin}</span>")
        if parts:
            details_html.append(f"<span style='color:#17C3B2;font-size:11px'>📦 {len(parts)} sub-dbs</span>")

        details_str = "<br>".join(details_html) if details_html else "<span style='color:#444;font-size:11px'>No metadata</span>"

        # Liens
        links = ""
        if db.get("homepage"):
            links += f"<a href='{db['homepage']}' target='_blank' style='color:#888;font-size:11px'>Website</a> &nbsp;"
        if db.get("doi"):
            links += f"<a href='{db['doi']}' target='_blank' style='color:#888;font-size:11px'>Publication</a>"

        card_html = f"""
<div style='background:#161B27;border:1px solid #2A2F42;border-radius:10px;
padding:14px 16px;margin-bottom:12px;font-family:sans-serif;display:flex;flex-direction:column;justify-content:space-between;min-height:180px'>
  <div>
    <div style='font-size:15px;font-weight:600;color:#E0DFFF;margin-bottom:4px'>{name}</div>
    <div style='font-size:11px;color:#666;margin-bottom:8px'>Release: {release}</div>
    <div style='margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px'>{taxa_badges}</div>
    <div style='margin-bottom:8px'>{details_str}</div>
  </div>
  <div style='margin-top:6px'>{links}</div>
</div>"""
        with cols[i % 3]:
            st.markdown(card_html, unsafe_allow_html=True)

    # Vue détaillée au choix
    st.markdown("---")
    selected_db = st.selectbox(
        "Details view",
        ["—"] + sorted(db.get("name", k) for k, db in databases.items()),
        key="sel_db",
    )
    if selected_db != "—":
        db_id = next(
            (k for k, v in databases.items() if v.get("name", k) == selected_db),
            None,
        )
        if db_id:
            _db_card(databases[db_id], db_id)
# ═════════════════════════════════════════════════════════════════════════════
# DISPATCH
# ═════════════════════════════════════════════════════════════════════════════
if page == "🔍 Survey":
    render_questionnaire()
elif page == "📊 Catalog":
    render_catalogue()
elif page == "🏠 Home":
    render_home()
