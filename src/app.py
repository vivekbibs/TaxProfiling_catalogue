import sys
from pathlib import Path
try:
    from src.recommender import CatalogDatabase, CatalogTool
except ModuleNotFoundError:
    from recommender import CatalogDatabase, CatalogTool
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

def _reco_card_html(rec: dict, small: bool = False) -> str:
    tool = rec["tool"]
    db = rec["db"]
    t_name = tool.get("name", rec["tool_id"])
    db_id = rec["db_id"]
    db_name = db.get("name", db_id) if db else db_id

    # Caractéristiques
    sr = "✅" if tool.get("supports_shortreads") else "❌"
    lr = "✅" if tool.get("supports_longreads") else "❌"
    strain = "✅" if tool.get("strain_level") else "❌"
    func = "✅" if tool.get("functional_profiling") else "❌"

    # Badge Taxonomie
    ts_display = taxonomy_badge(rec.get("db_ts"))
    color = "#1D9E75" if "GTDB" in ts_display else ("#534AB7" if ts_display != "—" else "#444")
    taxo_html = f"<span style='background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:bold'>{ts_display}</span>" if ts_display != "—" else ""

    # Releases compatibles
    rels = rec.get("releases", [])
    rels_str = f"<div style='font-size:11px;color:#888;margin-bottom:6px'>Releases: {', '.join(rels)}</div>" if rels else ""

    html = f"""
    <div style='background:#161B27;border:1px solid #2A2F42;border-radius:10px;
    padding:14px 16px;margin-bottom:12px;font-family:sans-serif;display:flex;flex-direction:column;min-height:{'160' if small else '200'}px'>
      <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px'>
        <div style='font-size:15px;font-weight:600;color:#E0DFFF'>🔧 {t_name}</div>
        {taxo_html}
      </div>
      <div style='font-size:13px;font-weight:600;color:#1D9E75;margin-bottom:4px'>🗄️ {db_name}</div>
      {rels_str}
      <div style='display:flex;gap:4px;flex-wrap:wrap;margin-top:auto'>
        <span style='background:#222;padding:2px 6px;border-radius:4px;font-size:10px;color:#aaa'>SR {sr}</span>
        <span style='background:#222;padding:2px 6px;border-radius:4px;font-size:10px;color:#aaa'>LR {lr}</span>
        <span style='background:#222;padding:2px 6px;border-radius:4px;font-size:10px;color:#aaa'>Strain {strain}</span>
        <span style='background:#222;padding:2px 6px;border-radius:4px;font-size:10px;color:#aaa'>Func {func}</span>
      </div>
    </div>"""
    return html

# Helper pour remonter parents et grand-parents
def get_all_ancestors(db_id: str, databases: dict) -> list:
    ancestors = set()
    queue = [db_id]
    while queue:
        current = queue.pop(0)
        db_obj = databases.get(current, {})
        parents = _to_list(db_obj.get("isPartOf", []))
        for p in parents:
            if isinstance(p, dict) and p.get("@id"):
                pid = p["@id"]
                if pid not in ancestors:
                    ancestors.add(pid)
                    queue.append(pid)
    return list(ancestors)
    
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

    pref_taxo_for_reco = (
        "Indifférent"
        if str(pref_taxo).strip().lower() in ("any", "indifferent", "indifférent")
        else pref_taxo
    )

    recs = recommend(
        databases, tools, envo_key, host_key, selected_orgs, reads_key,
        pref_taxo_for_reco, wants_strain, wants_func, max_ram
    )

    if not recs:
        st.warning("No tool matches your criteria exactly. Try loosening filters.")
        return

    # 1. Dédoublonnage global (outil, BD) pour éviter les répétitions
    unique_recs = {}
    for r in recs:
        key = (r["tool_id"], r["db_id"])
        # On privilégie la recommandation native par rapport à une entrée "extension"
        if key not in unique_recs or not r.get("extension_of"):
            unique_recs[key] = r

    # 2. On isole les recommandations "Racines" (qui ne sont pas des extensions de parent)
    base_recs = [r for r in recs if not r.get("extension_of")]

    st.success(f"**{len(base_recs)} recommandation(s) principale(s)** trouvée(s).")

    # 3. Affichage en grille horizontale (3 colonnes)
    cols = st.columns(3)
    
    for i, rec in enumerate(base_recs):
        with cols[i % 3]:
            # Affichage de la carte principale
            st.markdown(_reco_card_html(rec), unsafe_allow_html=True)
            
            # Recherche des parents et grand-parents (ex: globdb)
            ancestors = get_all_ancestors(rec["db_id"], databases)
            
            if ancestors:
                # On récupère toutes les recos compatibles avec ces bases parentes
                composite_recs = [ur for ur in unique_recs.values() if ur["db_id"] in ancestors]
                
                if composite_recs:
                    # Extraction propre des noms pour la phrase d'explication
                    parent_dbs = {cr["db_id"]: cr["db"].get("name", cr["db_id"]) for cr in composite_recs}
                    p_names_str = ", ".join(parent_dbs.values())
                    t_names_str = ", ".join(list(set([cr["tool"].get("name", cr["tool_id"]) for cr in composite_recs])))
                    
                    with st.expander(f"📦 Alternatives via {p_names_str}"):
                        st.markdown(
                            f"<div style='font-size:13px; color:#bbb; margin-bottom:12px; line-height:1.4'>"
                            f"💡 <b>{rec['db'].get('name', rec['db_id'])}</b> est intégrée dans le catalogue <b>{p_names_str}</b>, "
                            f"base(s) utilisée(s) par <b>{t_names_str}</b>. "
                            f"Nous suggérons d'utiliser ces couples (compatibles avec vos filtres) :"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        # Affichage des cartes composites (en mode "small")
                        for cr in composite_recs:
                            st.markdown(_reco_card_html(cr, small=True), unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CATALOGUE
# ═════════════════════════════════════════════════════════════════════════════

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
    import numpy as np
    import plotly.graph_objects as go

    v_ego, v_matrix = st.tabs(
        [
            "🕸️ Ego-graph",
            "🔲 Matrix",
        ]
    )

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


# ─────────────────────────────────────────────────────────────────────────────
# TAB TOOLS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_tools():
    st.markdown("### 🔧 Tools")
    
    # Transformation des dictionnaires bruts en objets typés
    wrapped_tools = {tid: CatalogTool.from_dict(tid, t) for tid, t in tools.items()}

    selected_tool = st.selectbox(
        "Select",
        ["—"] + sorted(t.raw.get("name", tid) for tid, t in wrapped_tools.items()),
        key="sel_tool",
    )
    if selected_tool != "—":
        tid = next((k for k, v in wrapped_tools.items() if v.raw.get("name", k) == selected_tool), None)
        if tid:
            detail_col, _, _ = st.columns(3)
            with detail_col:
                st.markdown(_tool_card_html(tid, wrapped_tools[tid], databases, tools), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Filter")

    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        f_features = st.multiselect(
            "Capabilities / Features",
            ["Short Reads", "Long Reads", "Strain-level", "Functional profiling"],
            key="f_tool_features",
        )
    with col_b:
        search_tool = st.text_input(
            "🔍 Search", "", key="search_tool", placeholder="name, description, database…"
        )
    with col_c:
        sort_by = st.selectbox(
            "Sort by",
            ["Citations (↓)", "Name (A→Z)", "Version"],
            key="cards_sort",
        )

    filtered_tools = []
    for tid, tool in wrapped_tools.items():
        name = tool.raw.get("name", tid)
        desc = tool.raw.get("description") or tool.raw.get("approach_detail") or ""

        # Utilisation de l'attribut typé tool.uses_databases
        db_names = []
        for u in tool.uses_databases:
            if isinstance(u, dict):
                did = u.get("@id", "")
                dname = databases.get(did, {}).get("name", did)
                db_names.append(dname)
        dbs_str = ", ".join(db_names)

        # Filtre Fonctionnalités via les booléens de la dataclass
        if f_features:
            if "Short Reads" in f_features and not tool.supports_shortreads:
                continue
            if "Long Reads" in f_features and not tool.supports_longreads:
                continue
            if "Strain-level" in f_features and not tool.strain_level:
                continue
            if "Functional profiling" in f_features and not tool.functional_profiling:
                continue

        if search_tool:
            q = search_tool.lower()
            if not (q in name.lower() or q in desc.lower() or q in tid.lower() or q in dbs_str.lower()):
                continue

        filtered_tools.append((tid, tool))

    if sort_by == "Citations (↓)":
        filtered_tools.sort(key=lambda x: -(x[1].raw.get("citations_count") or 0))
    elif sort_by == "Name (A→Z)":
        filtered_tools.sort(key=lambda x: x[1].raw.get("name", x[0]).lower())
    elif sort_by == "Version":
        filtered_tools.sort(key=lambda x: x[1].raw.get("latest_release") or "", reverse=True)

    st.caption(f"{len(filtered_tools)} Tools shown")

    cols = st.columns(3)
    for i, (tid, tool) in enumerate(filtered_tools):
        with cols[i % 3]:
            st.markdown(_tool_card_html(tid, tool, databases, tools), unsafe_allow_html=True)

def _tool_card_html(tid: str, tool: CatalogTool, databases: dict, tools: dict) -> str:
    cit = tool.raw.get("citations_count") or 0
    name = tool.raw.get("name", tid)
    version = tool.raw.get("latest_release") or "—"
    
    # Utilisation directe des booléens garantis par CatalogTool
    sr = "✅" if tool.supports_shortreads else "❌"
    lr = "✅" if tool.supports_longreads else "❌"
    strain = "✅" if tool.strain_level else "❌"
    func = "✅" if tool.functional_profiling else "❌"

    max_citations = max((t.get("citations_count") or 0 for t in tools.values()), default=1)
    bar_w = int(160 * cit / max(max_citations, 1))

    dbs_used = []
    # Plus besoin de _to_list() grâce à tool.uses_databases
    for u in tool.uses_databases:
        if not isinstance(u, dict):
            continue
        did = u.get("@id", "")
        dname = databases[did].get("name", did) if did in databases else did
        ts = taxonomy_badge(u.get("taxonomy_system"))
        col_ts = "#17C3B2" if "GTDB" in ts else "#AFA9EC"
        dbs_used.append(f"<span style='color:{col_ts};font-size:11px'>● {dname}</span>")

    dbs_html = "<br>".join(dbs_used) if dbs_used else "<span style='color:#444;font-size:11px'>aucune BD renseignée</span>"

    links = ""
    if tool.raw.get("repo"):
        links += f"<a href='{tool.raw['repo']}' target='_blank' style='color:#888;font-size:11px'>GitHub</a> &nbsp;"
    if tool.raw.get("doc"):
        links += f"<a href='{tool.raw['doc']}' target='_blank' style='color:#888;font-size:11px'>Doc</a> &nbsp;"
    if tool.raw.get("doi"):
        links += f"<a href='{tool.raw['doi']}' target='_blank' style='color:#888;font-size:11px'>Publication</a>"

    return f"""
<div style='background:#161B27;border:1px solid #2A2F42;border-radius:10px;
padding:14px 16px;margin-bottom:12px;font-family:sans-serif;display:flex;flex-direction:column;justify-content:space-between;min-height:220px'>
  <div>
    <div style='font-size:15px;font-weight:600;color:#E0DFFF;margin-bottom:4px'>{name}</div>
    <div style='font-size:11px;color:#666;margin-bottom:8px'>v{version}</div>
    <div style='display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap'>
      <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>SR {sr}</span>
      <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>LR {lr}</span>
      <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>Strain {strain}</span>
      <span style='background:#222;padding:1px 7px;border-radius:6px;font-size:11px;color:#aaa'>Func {func}</span>
    </div>
    <div style='margin-bottom:6px'>{dbs_html}</div>
  </div>
  <div>
    <div style='margin-top:8px'>
      <div style='background:#1A1F2E;border-radius:3px;height:4px;width:160px'>
        <div style='background:#534AB7;height:4px;border-radius:3px;width:{bar_w}px'></div>
      </div>
      <span style='font-size:10px;color:#555'>{cit} citations</span>
    </div>
    <div style='margin-top:6px'>{links}</div>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# TAB BASES DE DONNÉES
# ─────────────────────────────────────────────────────────────────────────────
def _tab_databases():
    st.markdown("### 🗄️ Databases")
    st.markdown("---")
    
    # Transformation en objets typés
    wrapped_dbs = {did: CatalogDatabase.from_dict(did, d) for did, d in databases.items()}

    selected_db = st.selectbox(
        "Select",
        ["—"] + sorted(db.raw.get("name", k) for k, db in wrapped_dbs.items()),
        key="sel_db",
    )
    if selected_db != "—":
        db_id = next(
            (k for k, v in wrapped_dbs.items() if v.raw.get("name", k) == selected_db),
            None,
        )
        if db_id:
            detail_col, _, _ = st.columns(3)
            with detail_col:
                st.markdown(_db_card_html(db_id, wrapped_dbs[db_id], databases, tools), unsafe_allow_html=True)

    st.markdown("####  Filter")
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

    filtered_dbs = []
    for db_id, db in wrapped_dbs.items():
        taxa_list = taxon_labels(db.raw)
        taxa_str = ", ".join(taxa_list)
        sample_str = sample_label(db.raw)
        origin_str = origin_label(db.raw)
        name_str = db.raw.get("name", db_id)

        if f_taxon and not any(fx in taxa_str for fx in f_taxon):
            continue

        if search_db:
            q = search_db.lower()
            if not (q in name_str.lower() or q in sample_str.lower() or q in origin_str.lower() or q in db_id.lower()):
                continue

        filtered_dbs.append((db_id, db))

    if sort_by == "Name (A→Z)":
        filtered_dbs.sort(key=lambda x: x[1].raw.get("name", x[0]).lower())
    elif sort_by == "Sub-dbs (↓)":
        # Plus besoin de _to_list(db.get("hasPart"))
        filtered_dbs.sort(key=lambda x: -len(x[1].has_part))

    st.caption(f"{len(filtered_dbs)} Databases shown")

    cols = st.columns(3)
    for i, (db_id, db) in enumerate(filtered_dbs):
        with cols[i % 3]:
            st.markdown(_db_card_html(db_id, db, databases, tools), unsafe_allow_html=True)

def _db_card_html(db_id: str, db: CatalogDatabase, databases: dict, tools: dict) -> str:
    name = db.raw.get("name", db_id)
    release = db_release_str(db.raw)
    taxa = taxon_labels(db.raw)
    sample = sample_label(db.raw)
    origin = origin_label(db.raw)
    
    # Utilisation directe des attributs de listes de CatalogDatabase
    parts = db.has_part
    parents = db.is_part_of
    compatible_tools = db.compatible_tools

    taxa_badges = "".join(
        f"<span style='background:#1D9E7522;border:1px solid #1D9E75;padding:1px 6px;border-radius:6px;font-size:10px;color:#2ECC8A;margin-right:4px'>{t}</span>"
        for t in taxa
    ) if taxa else "<span style='color:#666;font-size:11px'>—</span>"

    details_html = []
    if sample != "—":
        details_html.append(f"<span style='color:#aaa;font-size:11px'>🧪 {sample}</span>")
    if origin != "—":
        details_html.append(f"<span style='color:#aaa;font-size:11px'>🌍 {origin}</span>")
    if parts:
        details_html.append(f"<span style='color:#17C3B2;font-size:11px'>📦 {len(parts)} sub-dbs</span>")
    if parents:
        parent_names = []
        for p in parents:
            if isinstance(p, dict):
                pid = p.get("@id", "")
                parent_name = p.get("name") or databases.get(pid, {}).get("name", pid)
                if parent_name:
                    parent_names.append(parent_name)
            elif isinstance(p, str):
                parent_names.append(databases.get(p, {}).get("name", p))

        if parent_names:
            parents_lines = "<br>".join(f"&nbsp;&nbsp;• {pn}" for pn in parent_names)
            details_html.append(
                f"<span style='color:#AFA9EC;font-size:11px'>🔗 Part of:<br>{parents_lines}</span>"
            )

    if compatible_tools:
        tool_names = []
        for t in compatible_tools:
            if isinstance(t, dict):
                tid = t.get("@id", "")
                tool_name = t.get("name") or tools.get(tid, {}).get("name", tid)
                if tool_name:
                    tool_names.append(tool_name)
            elif isinstance(t, str):
                tool_names.append(tools.get(t, {}).get("name", t))

        if tool_names:
            tools_lines = "<br>".join(f"&nbsp;&nbsp;• {tn}" for tn in tool_names)
            details_html.append(
                f"<span style='color:#F5A623;font-size:11px'>🛠️ Compatible with:<br>{tools_lines}</span>"
            )

    details_str = "<br>".join(details_html) if details_html else "<span style='color:#444;font-size:11px'>No metadata</span>"

    links = ""
    if db.raw.get("homepage"):
        links += f"<a href='{db.raw['homepage']}' target='_blank' style='color:#888;font-size:11px'>Website</a> &nbsp;"
    if db.raw.get("doi"):
        links += f"<a href='{db.raw['doi']}' target='_blank' style='color:#888;font-size:11px'>Publication</a>"

    return f"""
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

# ═════════════════════════════════════════════════════════════════════════════
# DISPATCH
# ═════════════════════════════════════════════════════════════════════════════
if page == "🔍 Survey":
    render_questionnaire()
elif page == "📊 Catalog":
    render_catalogue()
elif page == "🏠 Home":
    render_home()