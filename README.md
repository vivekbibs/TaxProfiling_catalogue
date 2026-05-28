# A FAIR Catalog for Taxonomic Profiling


---

**Taxonomic Profiling** refers to methods that directly calculates the **relative abundance** of each present **microorganism** taxa, and provide an abundance profile table, without requiring any binning or assembly method.

Information about these tools and databases was scattered around various documentations, and sometimes incomplete, so we decided to create this catalogue.
This project centralizes metadata of tools and associated reference databases for taxonomic profiling, featuring:

- A **Streamlit** interface to explore the catalog and obtain recommendations based on user questions and needs;
- Tools and databases' metadata annotated with ontologies.


---

## 1) Project structure

```text
catalogue/
├── data/
│   ├── databases/              # reference databases metadata in JSON format
│   ├── tools/                  # tools metadata in JSON format
│   └── schemas/                # JSON-LD schemas (tool_schema, database_schema...)
├── scripts/
│   ├── streamlit/
│   │   ├── app.py              # Streamlit UI 
│   │   └── catalogue_utils.py  # utils for streamlit interface
│   ├── notebooks/
│   │   ├── sylph_nb.ipynb      # Sylph + GlobDB workflow
│   │   └── singlem_nb.ipynb    # SingleM + GlobDB workflow
│   
└── README.md
```

---

## 2) Data model (JSON)

### 2.1 Tools (`data/tools/*.json`)

Each tool entry contains for example:

- `@id`, `name`, `type`
- `latest_release`, `curated_release`
- capabilities: `supports_shortreads`, `supports_longreads`, `strain_level`, `functional_profiling`
- references: `repo`, `doc`, `doi`, `bio_tools`
- relationship to databases: `uses_databases`

The key field is `uses_databases` (list of objects), e.g.:

- `@id`: database identifier
- `taxonomy_system`: `gtdb`, `ncbi`, etc.
- `release`: database release used by the tool

> The taxonomy badge displayed in Streamlit is derived from this tool/database relationship (inside `uses_databases`), not from a global field on the database itself.

### 2.2 Databases (`data/databases/*.json`)

Each database entry typically contains:

- `@id`, `name`, `release`/`latest_release`
- `taxonomic_scope`
- `sample`, `origin`
- `hasPart` / `isPartOf` for composite catalogues
- `compatible_tools` (downloads and per-tool variants)

Example of composite logic:

- `globdb` contains several sub-catalogues via `hasPart` (`gtdb`, `motus-db`, `gfs`, `cfmd`, `shgo`, ...).
- A tool may point directly to `globdb`, and the recommendation engine can leverage the sub-databases to better match a specific context.

---

## 3) Streamlit application

### 3.1 Running the application

From the project root:

```bash
streamlit run scripts/streamlit/app.py
```

### 3.2 What `app.py` does

`scripts/streamlit/app.py` handles:

- navigation (`Survey` / `Catalog`);
- user widgets (read type, sample category, target taxa, RAM, etc.);
- calls to `recommend(...)`;
- display of recommendations: tool + database + links + downloads;
- catalogue views (graph, matrix, tables, cards).

### 3.3 What `catalogue_utils.py` does

`scripts/streamlit/catalogue_utils.py` contains:

- `load_catalogue(...)`: JSON loading;
- `_normalize(...)`: structure harmonisation (dict/list);
- `db_scope(...)`: tag extraction from `sample` and `origin`;
- display helpers (`sample_label`, `origin_label`, `taxonomy_badge`, etc.);
- `_score_db_entry(...)` and `recommend(...)`: recommendation engine.

### 3.4 Recommendation flow

1. Filter tools by capabilities (short/long reads, strain-level, functional, RAM).
2. For each tool, evaluate candidate databases via `uses_databases`.
3. Compute a score (environment/host match + composite logic via `hasPart`).
4. Select the best database for each tool/database pair.
5. Final ranking and display.

---


## 4) Curation and maintenance

### 4.1 `latest_release` vs `curated_release`

- `latest_release`: most recently detected version.
- `curated_release`: version explicitly validated and curated in this catalogue.

The `scripts/update_tools.py` script identifies tools that need curation (when `latest_release != curated_release` or `curated_release` is empty) and feeds `curation_report.txt`.

### 4.2 Adding a new tool

1. Create `data/tools/<tool>.json`.
2. Fill in the base fields + `uses_databases`.
3. Check consistency of database IDs (`@id` must already exist).
4. Restart Streamlit and test the questionnaire.

### 4.3 Adding a new database

1. Create `data/databases/<db>.json`.
2. Fill in `sample`, `origin`, `taxonomic_scope`, `isPartOf`/`hasPart` if needed.
3. Add `uses_databases` relationships on the relevant tool(s).
4. If a download is available, fill in `compatible_tools`.

### 4.4 Avoiding common inconsistencies

- Questionnaire labels must match the mapping keys (`SAMPLE_FILTER` / `SAMPLE_CATEGORIES`).
- IDs in `uses_databases[@id]` must point to an existing JSON in `data/databases/`.
- `taxonomy_system` must be defined at the tool/database relationship level (inside `uses_databases`).

---

## 5) Dependencies

Python dependencies used in the project (depending on the modules executed):

- `streamlit`
- `pandas`
- `plotly`
- `networkx`
- `numpy`
- `seaborn`
- `matplotlib`
- `scipy`

Install according to your environment (venv/conda/cluster).

---

## 6) Design philosophy

This project aims to be:

- **traceable**: every recommendation must be explainable from the JSON files;
- **extensible**: new databases and tools can be added easily;
- **useful to maintainers**: clear visibility of pending updates (curation, compatibility, releases).

If a result looks unexpected, the recommended debugging approach is:
1. check the tool JSON (`uses_databases`),
2. check the database JSON (`sample`, `origin`, `hasPart`),
3. check the questionnaire mappings,
4. trace the score in `catalogue_utils.py`.