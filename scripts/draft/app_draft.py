"""
app.py  —  Application principale : Profiling Taxonomique Catalogue
────────────────────────────────────────────────────────────────────
Navigation multi-pages (sidebar) :
  🔍 Questionnaire  — aide au choix outil + BD (contenu de app_questionnaire.py)
  📊 Catalogue      — graphe interactif pyvis + tableaux filtrables + fiches

Structure :
    app.py
    app_questionnaire.py    ← ton fichier existant, importé comme module
    data/
        databases/
        tools/

Lancement :
    streamlit run app.py

Dépendances supplémentaires :
    pip install pyvis pandas
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — premier appel Streamlit obligatoire
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Profiling Taxonomique — Catalogue",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Importer les fonctions partagées depuis app_questionnaire
# (load_catalogue, helpers d'affichage, moteur de recommandation)
from app_questionnaire import (  # noqa: E402
    _to_list,
    load_catalogue,
    taxon_labels,
    sample_label,
    origin_label,
    is_about_label,
    seq_scope_label,
    taxonomy_badge,
    db_release_str,
    SAMPLE_FILTER,
    SAMPLE_CATEGORIES,
    TAXON_IRI,
    DB_SCOPE_FALLBACK,
    db_scope,
    _score_db_entry,
    recommend,
    compatible_tool_ids,
    download_variants,
)

# ─────────────────────────────────────────────────────────────────────────────
# DONNÉES
# ─────────────────────────────────────────────────────────────────────────────
databases, tools = load_catalogue()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — navigation
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧬 Navigation")
    page = st.radio(
        "",
        ["🔍 Questionnaire", "📊 Catalogue"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.metric("Bases de données", len(databases))
    st.metric("Outils", len(tools))


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — QUESTIONNAIRE
# On réutilise exactement le contenu de app_questionnaire.py
# en important ses constantes et fonctions puis en réexécutant son UI
# ═════════════════════════════════════════════════════════════════════════════
def render_questionnaire():
    """Restitue la page questionnaire en appelant directement le code UI."""

    # ── En-tête ───────────────────────────────────────────────────────────────
    st.markdown("# 🧬 Aide au choix — Profiling Taxonomique")
    st.markdown(
        "Répondez aux questions ci-dessous pour obtenir les outils et bases de données "
        "adaptés à votre échantillon et vos objectifs."
    )
    st.markdown("---")

    # Q1 — Séquençage
    st.markdown("## 1 · Type de séquençage")
    reads_choice = st.radio(
        "Type de lectures",
        ["Short Reads (Illumina, etc.)", "Long Reads (PacBio, Nanopore, etc.)"],
        horizontal=True,
    )
    reads_key = "Short Reads" if "Short" in reads_choice else "Long Reads"
    st.markdown("---")

    # Q2 — Échantillon
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

    # Q3 — Organismes & analyses
    st.markdown("## 3 · Organismes cibles & analyses souhaitées")
    col_org, col_extra = st.columns(2)
    with col_org:
        selected_orgs = st.multiselect(
            "Groupes taxonomiques à identifier",
            list(TAXON_IRI.keys()),
            default=["Bactéries", "Archées"],
        )
        if not selected_orgs:
            st.warning("Sélectionnez au moins un groupe.")
        if "Virus" in selected_orgs or "Eucaryotes" in selected_orgs:
            st.warning("⚠️ Peu d'outils couvrent Virus et Eucaryotes.")
    with col_extra:
        wants_strain = st.checkbox("🔬 Strain-level profiling")
        wants_func = st.checkbox("⚙️ Profiling fonctionnel")
        if wants_func:
            st.info("💡 Profiling fonctionnel : meteor / HUMAnN3.")
        if wants_strain:
            st.info("💡 Strain-level : MetaPhlAn / StrainPhlAn, Metabuli.")
    st.markdown("---")

    # Q4 — Paramètres avancés
    with st.expander("⚙️ Paramètres avancés", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            pref_taxo = st.radio(
                "Taxonomie de la base de référence",
                ["Indifférent", "GTDB", "NCBI"],
                horizontal=True,
            )
        with col_b:
            max_ram = st.slider("RAM disponible (GB)", 2, 512, 512, 2)
    st.markdown("---")

    # Recommandations
    st.markdown("## 4 · Recommandations")

    if not selected_orgs:
        st.warning("Sélectionnez au moins un groupe d'organismes (section 3).")
        return

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
            "Essayez de relâcher les filtres ou vérifiez vos JSONs."
        )
        return

    st.success(f"**{len(recs)} outil(s)** trouvé(s).")

    for i, rec in enumerate(recs):
        tool = rec["tool"]
        db = rec["db"]
        db_id = rec["db_id"] or "—"
        t_name = tool.get("name", rec["tool_id"])
        db_name = db.get("name", db_id) if db else db_id
        ts = rec["db_ts"]
        releases = rec["releases"]

        badges = []
        if tool.get("strain_level"):
            badges.append("🔬 strain-level")
        if tool.get("functional_profiling"):
            badges.append("⚙️ fonctionnel")
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
                        f"**Fonctionnel** : {'✅' if tool.get('functional_profiling') else '❌'}"
                    )
                    st.markdown(f"**Citations** : {tool.get('citations_count') or '—'}")
                    st.markdown(f"**Taxonomie** : {tool.get('taxonomy') or '—'}")
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
                if releases:
                    st.markdown(f"**Releases compatibles** : {', '.join(releases)}")
                if db:
                    taxa = taxon_labels(db)
                    if taxa:
                        st.markdown(f"**Taxons** : {', '.join(taxa)}")
                    for label, fn in [
                        ("Échantillon", sample_label),
                        ("Origine", origin_label),
                        ("Séquences", seq_scope_label),
                        ("is_about", is_about_label),
                    ]:
                        val = fn(db)
                        if val != "—":
                            st.markdown(f"**{label}** : {val}")
                    st.markdown(f"**Release** : {db_release_str(db)}")
                    if db.get("homepage"):
                        st.markdown(f"🌐 [Site officiel]({db['homepage']})")
                    if db.get("doi"):
                        st.markdown(f"📄 [Publication]({db['doi']})")
                else:
                    st.caption(
                        f"ℹ️ `{db_id}.json` absent de `data/databases/` "
                        "— ajoutez-le pour les détails complets."
                    )
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

    st.markdown("---")
    if st.button("🔄 Réinitialiser"):
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CATALOGUE
# ═════════════════════════════════════════════════════════════════════════════

# Couleurs graphe
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
    st.markdown("# 📊 Catalogue — Outils & Bases de données")
    st.markdown(f"**{len(tools)} outils** · **{len(databases)} bases de données**")
    st.markdown("---")

    tab_graph, tab_tools, tab_dbs = st.tabs(
        [
            "🕸️ Graphe de relations",
            "🔧 Outils",
            "🗄️ Bases de données",
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
    try:
        from pyvis.network import Network  # noqa: F401
    except ImportError:
        st.error("Installez pyvis : `pip install pyvis`")
        return

    from pyvis.network import Network

    # Filtres
    col1, col2, col3 = st.columns(3)
    with col1:
        show_haspart = st.checkbox(
            "Relations hasPart (BD → sous-BD)",
            value=False,
            help="Affiche les arêtes GlobDB → GTDB, GlobDB → mOTUs-db…",
        )
    with col2:
        filter_taxo = st.selectbox(
            "Filtrer arêtes par taxonomie",
            ["Toutes", "GTDB uniquement", "NCBI uniquement"],
        )
    with col3:
        min_cit = st.slider("Citations min. (outils)", 0, 2000, 0, 10)

    # Légende
    st.markdown(
        "<div style='font-size:12px;color:#888;margin:4px 0 10px'>"
        "🔵 Outil &nbsp;·&nbsp; 🟩 Base de données &nbsp;·&nbsp; ⬜ BD sans JSON "
        "&nbsp;·&nbsp; <span style='color:#1D9E75'>━</span> GTDB "
        "&nbsp;·&nbsp; <span style='color:#7B68EE'>━</span> NCBI "
        "&nbsp;·&nbsp; <span style='color:#888'>╌</span> hasPart"
        "</div>",
        unsafe_allow_html=True,
    )

    net = Network(
        height="640px",
        width="100%",
        bgcolor=_C["bg"],
        font_color=_C["text"],
        directed=True,
    )
    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=130,
        spring_strength=0.05,
        damping=0.09,
    )

    # ── Nœuds outils ─────────────────────────────────────────────────────────
    max_cit = max((t.get("citations_count") or 0 for t in tools.values()), default=1)
    active_tools = {
        tid: t for tid, t in tools.items() if (t.get("citations_count") or 0) >= min_cit
    }

    for tid, tool in active_tools.items():
        cit = tool.get("citations_count") or 0
        size = 18 + int(28 * cit / max(max_cit, 1))
        name = tool.get("name", tid)
        tip = (
            f"<b>{name}</b><br>"
            f"Version : {tool.get('latest_release') or '—'}<br>"
            f"Citations : {cit}<br>"
            f"SR : {'✅' if tool.get('supports_shortreads') else '❌'}  "
            f"LR : {'✅' if tool.get('supports_longreads') else '❌'}<br>"
            f"Strain-level : {'✅' if tool.get('strain_level') else '❌'}"
        )
        net.add_node(
            tid,
            label=name,
            title=tip,
            color=_C["tool"],
            size=size,
            shape="dot",
            font={"color": _C["text"], "size": 13},
        )

    # ── Nœuds BDs ─────────────────────────────────────────────────────────────
    all_db_ids = set(databases.keys())
    for tool in active_tools.values():
        for u in _to_list(tool.get("uses_databases")):
            if isinstance(u, dict) and u.get("@id"):
                all_db_ids.add(u["@id"])

    for db_id in all_db_ids:
        db = databases.get(db_id)
        name = db.get("name", db_id) if db else db_id
        taxa = taxon_labels(db) if db else []
        tip = (
            f"<b>{name}</b><br>"
            f"Release : {db_release_str(db) if db else '—'}<br>"
            f"Taxons : {', '.join(taxa) or '—'}<br>"
            f"Sample : {sample_label(db) if db else '—'}"
        )
        is_parent = bool(db.get("hasPart")) if db else False
        color = _C["db"] if db else _C["db_miss"]
        net.add_node(
            db_id,
            label=name,
            title=tip,
            color=color,
            size=26 if is_parent else 16,
            shape="square",
            font={"color": _C["text"], "size": 12},
        )

    # ── Arêtes uses_databases ─────────────────────────────────────────────────
    for tid, tool in active_tools.items():
        seen: set[str] = set()
        for u in _to_list(tool.get("uses_databases")):
            if not isinstance(u, dict):
                continue
            db_id = u.get("@id")
            if not db_id or db_id in seen:
                continue
            ts = taxonomy_badge(u.get("taxonomy_system"))
            if filter_taxo == "GTDB uniquement" and "GTDB" not in ts:
                continue
            if filter_taxo == "NCBI uniquement" and "NCBI" not in ts:
                continue
            seen.add(db_id)
            color = _C["edge_gtdb"] if "GTDB" in ts else _C["edge_ncbi"]
            net.add_edge(
                tid,
                db_id,
                color=color,
                width=1.5,
                title=f"uses_databases · {ts}",
                arrows="to",
            )

    # ── Arêtes hasPart ────────────────────────────────────────────────────────
    if show_haspart:
        for db_id, db in databases.items():
            for part in _to_list(db.get("hasPart")):
                if isinstance(part, dict) and part.get("@id"):
                    net.add_edge(
                        db_id,
                        part["@id"],
                        color=_C["edge_part"],
                        width=1,
                        dashes=True,
                        title="hasPart",
                        arrows="to",
                    )

    # Rendu
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        net.save_graph(tmp.name)
        html_content = Path(tmp.name).read_text(encoding="utf-8")
        os.unlink(tmp.name)

    st.components.v1.html(html_content, height=660, scrolling=False)
    st.caption(
        f"{len(active_tools)} outils · {len(all_db_ids)} BDs affichées.  "
        "Survolez un nœud pour ses détails · Molette pour zoomer · Drag pour déplacer."
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB OUTILS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_tools():
    import pandas as pd

    st.markdown("### 🔧 Outils")

    # Filtres
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        f_sr = st.selectbox("Short reads", ["Tous", "✅", "❌"], key="f_sr")
    with col_b:
        f_lr = st.selectbox("Long reads", ["Tous", "✅", "❌"], key="f_lr")
    with col_c:
        f_strain = st.selectbox("Strain-level", ["Tous", "✅", "❌"], key="f_strain")
    with col_d:
        f_taxo = st.selectbox("Taxonomie BD", ["Toutes", "GTDB", "NCBI"], key="f_taxo")
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
                "Nom": t.get("name", tid),
                "Type": t.get("type", "—"),
                "Version": t.get("latest_release") or "—",
                "Short reads": "✅" if t.get("supports_shortreads") else "❌",
                "Long reads": "✅" if t.get("supports_longreads") else "❌",
                "Strain-level": "✅" if t.get("strain_level") else "❌",
                "Fonctionnel": "✅" if t.get("functional_profiling") else "❌",
                "RAM (GB)": str(t.get("ram") or "—"),
                "Taxonomie BD": taxo_str,
                "Citations": t.get("citations_count") or 0,
                "BDs utilisées": db_names,
                "Approche": t.get("approach_detail") or "—",
            }
        )

    df = pd.DataFrame(rows)
    if f_sr != "Tous":
        df = df[df["Short reads"] == f_sr]
    if f_lr != "Tous":
        df = df[df["Long reads"] == f_lr]
    if f_strain != "Tous":
        df = df[df["Strain-level"] == f_strain]
    if f_taxo != "Toutes":
        df = df[df["Taxonomie BD"].str.contains(f_taxo, na=False)]
    if search_t:
        m = (
            df["Nom"].str.contains(search_t, case=False, na=False)
            | df["Approche"].str.contains(search_t, case=False, na=False)
            | df["BDs utilisées"].str.contains(search_t, case=False, na=False)
        )
        df = df[m]

    st.caption(f"{len(df)} outil(s) affiché(s)")
    st.dataframe(
        df.sort_values("Citations", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    # Fiche détaillée
    st.markdown("---")
    selected = st.selectbox(
        "Fiche détaillée",
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
        st.markdown(f"**Nom** : {tool.get('name','—')}")
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
            f"**Fonctionnel** : {'✅' if tool.get('functional_profiling') else '❌'}"
        )
        st.markdown(f"**Citations** : {tool.get('citations_count') or '—'}")
        desc = tool.get("description") or tool.get("approach_detail") or ""
        if desc:
            st.markdown(f"**Approche** : {desc}")
        sm = tool.get("sub_module")
        if sm and isinstance(sm, dict):
            st.markdown(f"**Sous-module** : {sm.get('name', sm.get('@id',''))}")
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
        st.markdown("**Bases de données utilisées :**")
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
    import pandas as pd

    st.markdown("### 🗄️ Bases de données")

    col_a, col_b = st.columns(2)
    with col_a:
        f_taxon = st.multiselect(
            "Taxons couverts",
            ["Bacteria", "Archaea", "Eukaryota", "Viruses", "Fungi"],
            key="f_taxon",
        )
    with col_b:
        search_db = st.text_input(
            "🔍 Recherche", "", key="search_db", placeholder="nom, sample, origine…"
        )

    rows = []
    for db_id, db in sorted(databases.items()):
        rows.append(
            {
                "Nom": db.get("name", db_id),
                "Taxons": ", ".join(taxon_labels(db)) or "—",
                "Sample": sample_label(db),
                "Origine": origin_label(db),
                "Séquences (SO)": seq_scope_label(db),
                "is_about": is_about_label(db),
                "Release": db_release_str(db),
                "Sous-BDs": len(_to_list(db.get("hasPart"))),
                "Fait partie de": ", ".join(
                    ip.get("@id", "")
                    for ip in _to_list(db.get("isPartOf"))
                    if isinstance(ip, dict)
                )
                or "—",
            }
        )

    df = pd.DataFrame(rows)

    if f_taxon:
        df = df[df["Taxons"].apply(lambda t: any(fx in t for fx in f_taxon))]

    if search_db:
        m = (
            df["Nom"].str.contains(search_db, case=False, na=False)
            | df["Sample"].str.contains(search_db, case=False, na=False)
            | df["Origine"].str.contains(search_db, case=False, na=False)
        )
        df = df[m]

    st.caption(f"{len(df)} base(s) affichée(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Fiche détaillée
    st.markdown("---")
    selected_db = st.selectbox(
        "Fiche détaillée",
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


def _db_card(db: dict, db_id: str):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nom** : {db.get('name', db_id)}")
        st.markdown(f"**Release** : {db_release_str(db)}")
        taxa = taxon_labels(db)
        if taxa:
            st.markdown(f"**Taxons** : {', '.join(taxa)}")
        for label, fn in [
            ("Sample", sample_label),
            ("Origine", origin_label),
            ("Séquences (SO)", seq_scope_label),
            ("is_about", is_about_label),
        ]:
            val = fn(db)
            if val != "—":
                st.markdown(f"**{label}** : {val}")
    with col2:
        parents = [
            ip.get("@id", "")
            for ip in _to_list(db.get("isPartOf"))
            if isinstance(ip, dict)
        ]
        if parents:
            st.markdown(f"**Fait partie de** : {', '.join(parents)}")
        parts = _to_list(db.get("hasPart"))
        if parts:
            st.markdown(f"**Contient {len(parts)} sous-BD(s) :**")
            for p in parts[:12]:
                if isinstance(p, dict):
                    rel = f" · r{p['release']}" if p.get("release") else ""
                    st.markdown(f"  - `{p.get('@id','?')}` {p.get('name','')}{rel}")
            if len(parts) > 12:
                st.caption(f"… et {len(parts) - 12} autres.")
        if db.get("homepage"):
            st.markdown(f"🌐 [Site officiel]({db['homepage']})")
        if db.get("doi"):
            st.markdown(f"📄 [Publication]({db['doi']})")


# ═════════════════════════════════════════════════════════════════════════════
# DISPATCH
# ═════════════════════════════════════════════════════════════════════════════
if page == "🔍 Questionnaire":
    render_questionnaire()
elif page == "📊 Catalogue":
    render_catalogue()
