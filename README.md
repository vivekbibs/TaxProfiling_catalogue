# Taxonomic Profiling Catalog

This project centralizes a **catalog** of tools and associated reference databases for taxonomic profiling (metagenomics), featuring:

- A **Streamlit** interface to explore the catalog and obtain recommendations based on user questions and needs;
- Workflow **notebooks** to launch analyses on the IFB cluster and cloud;

The goal is to properly link:
1) tool metadata,
2) database metadata,
3) user use cases (sample type, target taxa, technical constraints, etc.).

---

The following introduction was largely inspired by:

Sophia Hampe, Bérénice Batut, Paul Zierep, Taxonomic Profiling and Visualization of Metagenomic Data (Galaxy Training Materials). [https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html](https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html)

Hiltemann, Saskia, Rasche, Helena et al., 2023 Galaxy Training: A Powerful Framework for Teaching! PLOS Computational Biology [10.1371/journal.pcbi.1010752](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010752)

Batut et al., 2018 Community-Driven Data Analysis Training for Biology Cell Systems [10.1016/j.cels.2018.05.012](https://doi.org/10.1016%2Fj.cels.2018.05.012)

The term “microbiome” describes “a characteristic microbial community occupying a reasonably well-defined habitat which has distinct physio-chemical properties. The term thus not only refers to the microorganisms involved but also encompasses their theatre of activity” (Whipps et al. 1988).

Microbiome data can be gathered from different environments such as soil, water or the human gut. The biological interest lies in general in the question how the microbiome present at a specific site influences this environment. To study a microbiome, we need to use indirect methods like metagenomics or metatranscriptomics.

Metagenomic samples contain DNA from different organisms at a specific site, where the sample was collected. Metagenomic data can be used to find out which organisms coexist in that niche and which genes are present in the different organisms. Metatranscriptomic samples include the transcribed gene products, thus RNA, that therefore allow to not only study the presence of genes but additionally their expression in the given environment. The following tutorial will focus on metagenomics data, but the principle is the same for metatranscriptomics data.

The investigation of microorganisms present at a specific site and their relative abundance is also called “microbial community profiling”. The main objective is to identify the microorganisms that are present within the given sample. This can be achieved for all known microbes, where the DNA sequence specific for a certain species is known.

For metagenomic data analysis we start with sequences derived from DNA fragments that are isolated from the sample of interest. Ideally, the sequences from all microbes in the sample are present. The underlying idea of taxonomic assignment is to compare the DNA sequences found in the sample (reads) to DNA sequences of a database. When a read matches a database DNA sequence of a known microbe, we can derive a list with microbes present in the sample.

Taxonomic Profiling refers to methods that directly calculates the relative abundance of each present microorganism taxa, and provide an abundance profile table, without requiring any binning/assembly method.

---

## 1) Project structure

```text
catalogue/
├── data/
│   ├── databases/              # database JSON files
│   ├── tools/                  # tool JSON files
│   └── schemas/                # JSON-LD schemas (tool_schema, database_schema...)
├── scripts/
│   ├── streamlit/
│   │   ├── app.py              # Streamlit UI (questionnaire + catalogue)
│   │   └── catalogue_utils.py  # business logic (loading, normalisation, recommendation)
│   ├── notebooks/
│   │   ├── sylph_nb.ipynb      # Sylph + GlobDB workflow
│   │   └── singlem_nb.ipynb    # SingleM + GlobDB workflow
│   └── update_tools.py         # tool update/curation utility
├── curation_report.txt         # tool release curation report
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

- navigation (`Questionnaire` / `Catalogue`);
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

## 4) Notebooks (`scripts/notebooks`)

The notebooks are analysis workflows, independent of Streamlit.

### `sylph_nb.ipynb`

- Sylph pipeline on paired FASTQ (`R1`/`R2`).
- Database configured on **GlobDB Sylph** (IFB core cluster path):
  - `/data/sylph/databases/sylph/globdb/globdb_r226_sylph_c200.syldb`
- TSV aggregation into an abundance matrix + clustering.

### `singlem_nb.ipynb`

- SingleM pipeline on FASTQ.
- Database configured on **GlobDB SingleM** (IFB core cluster path):
  - `/shared/bank/singlem/glob_db/GlobDB_r226.metapackage_v1.smpkg`
- `singlem pipe` + `singlem summarise` execution, then aggregation and clustering.

---

## 5) Curation and maintenance

### 5.1 `latest_release` vs `curated_release`

- `latest_release`: most recently detected version.
- `curated_release`: version explicitly validated and curated in this catalogue.

The `scripts/update_tools.py` script identifies tools that need curation (when `latest_release != curated_release` or `curated_release` is empty) and feeds `curation_report.txt`.

### 5.2 Adding a new tool

1. Create `data/tools/<tool>.json`.
2. Fill in the base fields + `uses_databases`.
3. Check consistency of database IDs (`@id` must already exist).
4. Restart Streamlit and test the questionnaire.

### 5.3 Adding a new database

1. Create `data/databases/<db>.json`.
2. Fill in `sample`, `origin`, `taxonomic_scope`, `isPartOf`/`hasPart` if needed.
3. Add `uses_databases` relationships on the relevant tool(s).
4. If a download is available, fill in `compatible_tools`.

### 5.4 Avoiding common inconsistencies

- Questionnaire labels must match the mapping keys (`SAMPLE_FILTER` / `SAMPLE_CATEGORIES`).
- IDs in `uses_databases[@id]` must point to an existing JSON in `data/databases/`.
- `taxonomy_system` must be defined at the tool/database relationship level (inside `uses_databases`).

---

## 6) Dependencies

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

## 7) Design philosophy

This project aims to be:

- **traceable**: every recommendation must be explainable from the JSON files;
- **extensible**: new databases and tools can be added without breaking the interface;
- **useful to maintainers**: clear visibility of pending updates (curation, compatibility, releases).

If a result looks unexpected, the recommended debugging approach is:
1. check the tool JSON (`uses_databases`),
2. check the database JSON (`sample`, `origin`, `hasPart`),
3. check the questionnaire mappings,
4. trace the score in `catalogue_utils.py`.