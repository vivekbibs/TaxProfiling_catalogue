# Catalogue de Profiling Taxonomique

Ce projet centralise un **catalogue** d'outils, et de bases de données de référence associées, pour le profiling taxonomique (metagenomique), avec:

- une interface **Streamlit** pour explorer le catalogue et obtenir des recommandations en fonctions des questions/besoins des utilisateurs;
- des **notebooks** de workflow pour lancer des analyses sur cluster et cloud IFB;
- des scripts utilitaires de curation/mise a jour.

L'objectif est de relier proprement:
1) les métadonnées des outils,
2) les métadonnées des bases,
3) les cas d'usage utilisateur (type d'echantillon, taxons cibles, contraintes techniques...).

---

# What is Taxonomic Profiling ? 

Sophia Hampe, Bérénice Batut, Paul Zierep, Taxonomic Profiling and Visualization of Metagenomic Data (Galaxy Training Materials). [https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html](https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html)

Hiltemann, Saskia, Rasche, Helena et al., 2023 Galaxy Training: A Powerful Framework for Teaching! PLOS Computational Biology [10.1371/journal.pcbi.1010752](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010752)
Batut et al., 2018 Community-Driven Data Analysis Training for Biology Cell Systems 10.1016/j.cels.2018.05.012

The term “microbiome” describes “a characteristic microbial community occupying a reasonably well-defined habitat which has distinct physio-chemical properties. The term thus not only refers to the microorganisms involved but also encompasses their theatre of activity” (Whipps et al. 1988).


Microbiome data can be gathered from different environments such as soil, water or the human gut. The biological interest lies in general in the question how the microbiome present at a specific site influences this environment. To study a microbiome, we need to use indirect methods like metagenomics or metatranscriptomics.

Metagenomic samples contain DNA from different organisms at a specific site, where the sample was collected. Metagenomic data can be used to find out which organisms coexist in that niche and which genes are present in the different organisms. Metatranscriptomic samples include the transcribed gene products, thus RNA, that therefore allow to not only study the presence of genes but additionally their expression in the given environment. The following tutorial will focus on metagenomics data, but the principle is the same for metatranscriptomics data.

The investigation of microorganisms present at a specific site and their relative abundance is also called “microbial community profiling”. The main objective is to identify the microorganisms that are present within the given sample. This can be achieved for all known microbes, where the DNA sequence specific for a certain species is known.

For that we try to identify the taxon to which each individual read belongs.

For metagenomic data analysis we start with sequences derived from DNA fragments that are isolated from the sample of interest. Ideally, the sequences from all microbes in the sample are present. The underlying idea of taxonomic assignment is to compare the DNA sequences found in the sample (reads) to DNA sequences of a database. When a read matches a database DNA sequence of a known microbe, we can derive a list with microbes present in the sample.

Taxonomic profiling refers to methods that produces relative abundance of present microorganisms, through an abundance profile table, without any binning/assembly methods.
## 1) Structure du projet

```text
catalogue/
├── data/
│   ├── databases/              # JSON des bases de donnees
│   ├── tools/                  # JSON des outils
│   └── schemas/                # schemas JSON-LD (tool_schema, database_schema...)
├── scripts/
│   ├── streamlit/
│   │   ├── app.py              # UI Streamlit (questionnaire + catalogue)
│   │   └── catalogue_utils.py  # logique metier (chargement, normalisation, recommandation)
│   ├── notebooks/
│   │   ├── sylph_nb.ipynb      # workflow Sylph + GlobDB
│   │   └── singlem_nb.ipynb    # workflow SingleM + GlobDB
│   └── update_tools.py         # utilitaire de mise a jour/curation des outils
├── curation_report.txt         # rapport de curation des releases outils
└── README.md
```

---

## 2) Logique de donnees (JSON)

### 2.1 Outils (`data/tools/*.json`)

Chaque outil contient par exemple:

- `@id`, `name`, `type`
- `latest_release`, `curated_release`
- capacites: `supports_shortreads`, `supports_longreads`, `strain_level`, `functional_profiling`
- references: `repo`, `doc`, `doi`, `bio_tools`
- relation vers les bases: `uses_databases`

Le champ cle est `uses_databases` (liste d'objets), ex:

- `@id`: identifiant de la base
- `taxonomy_system`: `gtdb`, `ncbi`, etc.
- `release`: release de la base utilisee par l'outil

> Le badge taxonomie affiche dans Streamlit est derive de cette relation (couple outil/base), pas d'un champ global de la base.

### 2.2 Bases (`data/databases/*.json`)

Chaque base contient typiquement:

- `@id`, `name`, `release`/`latest_release`
- `taxonomic_scope`
- `sample`, `origin`
- `hasPart` / `isPartOf` pour les catalogues composes
- `compatible_tools` (telechargements et variantes par outil)

Exemple de logique composee:

- `globdb` contient plusieurs sous-catalogues via `hasPart` (`gtdb`, `motus-db`, `gfs`, `cfmd`, `shgo`, ...).
- un outil peut pointer vers `globdb` directement, et la recommandation peut exploiter les sous-BDs pour mieux matcher un contexte specifique.

---

## 3) Application Streamlit

### 3.1 Lancer l'application

Depuis la racine du projet:

```bash
streamlit run scripts/streamlit/app.py
```

### 3.2 Ce que fait `app.py`

`scripts/streamlit/app.py` gere:

- la navigation (`Questionnaire` / `Catalogue`);
- les widgets utilisateur (type de reads, categorie d'echantillon, taxons cibles, RAM, etc.);
- l'appel a `recommend(...)`;
- l'affichage des recommandations outil + base + liens + telechargement;
- les vues catalogue (graphe, matrice, tables, cartes).

### 3.3 Ce que fait `catalogue_utils.py`

`scripts/streamlit/catalogue_utils.py` contient:

- `load_catalogue(...)`: chargement JSON;
- `_normalize(...)`: harmonisation des structures (dict/list);
- `db_scope(...)`: extraction des tags depuis `sample` et `origin`;
- helpers d'affichage (`sample_label`, `origin_label`, `taxonomy_badge`, etc.);
- `_score_db_entry(...)` et `recommend(...)`: moteur de recommandation.

### 3.4 Flux de recommandation

1. Filtrage outils par capacites (short/long reads, strain-level, fonctionnel, RAM).
2. Pour chaque outil, evaluation des bases candidates via `uses_databases`.
3. Calcul d'un score (match environnement/hote + logique composee via `hasPart`).
4. Selection de la meilleure base pour ce couple outil/base.
5. Tri final et affichage.

---

## 4) Notebooks (`scripts/notebooks`)

Les notebooks sont des workflows d'analyse, independants de Streamlit.

### `sylph_nb.ipynb`

- Pipeline Sylph sur FASTQ apparies (`R1`/`R2`).
- Base configuree sur **GlobDB Sylph** (path IFB core cluster):
  - `/data/sylph/databases/sylph/globdb/globdb_r226_sylph_c200.syldb`
- Agregation TSV en matrice d'abondance + clustering.

### `singlem_nb.ipynb`

- Pipeline SingleM sur FASTQ.
- Base configuree sur **GlobDB SingleM** (path IFB core cluster):
  - `/shared/bank/singlem/glob_db/GlobDB_r226.metapackage_v1.smpkg`
- Execution `singlem pipe` + `singlem summarise`, puis agregation et clustering.

---

## 5) Curation et maintenance

### 5.1 `latest_release` vs `curated_release`

- `latest_release`: version la plus recente detectee.
- `curated_release`: version explicitement validee/curatee dans ce catalogue.

Le script `scripts/update_tools.py` sert a identifier les outils a recurer (quand `latest_release != curated_release` ou `curated_release` vide) et alimenter `curation_report.txt`.

### 5.2 Ajouter un nouvel outil

1. Creer `data/tools/<tool>.json`.
2. Renseigner les champs de base + `uses_databases`.
3. Verifier la coherence des IDs de bases (`@id` existants).
4. Relancer Streamlit et tester le questionnaire.

### 5.3 Ajouter une nouvelle base

1. Creer `data/databases/<db>.json`.
2. Renseigner `sample`, `origin`, `taxonomic_scope`, `isPartOf`/`hasPart` si besoin.
3. Ajouter des relations `uses_databases` cote outil(s) concernes.
4. Si telechargement disponible, renseigner `compatible_tools`.

### 5.4 Eviter les incoherences frequentes

- Les labels du questionnaire doivent correspondre aux cles de mapping (`SAMPLE_FILTER` / `SAMPLE_CATEGORIES`).
- Les IDs dans `uses_databases[@id]` doivent pointer vers un JSON existant dans `data/databases/`.
- `taxonomy_system` doit etre defini au niveau relation outil/base (dans `uses_databases`).

---


## 6) Dependances

Dependances Python utilisees dans le projet (selon les modules executes):

- `streamlit`
- `pandas`
- `plotly`
- `networkx`
- `numpy`
- `seaborn`
- `matplotlib`
- `scipy`

Installer selon votre environnement (venv/conda/cluster).

---

## 7) Philosophie du catalogue

Ce projet vise a etre:

- **traçable**: chaque recommandation doit pouvoir etre expliquee par les JSON;
- **evolutif**: ajout de nouvelles bases/outils sans casser l'interface;
- **utile aux maintainers**: vision claire des mises a jour necessaires (curation, compatibilites, releases).

Si un resultat parait surprenant, la bonne methode est:
1) verifier le JSON outil (`uses_databases`),
2) verifier le JSON base (`sample`, `origin`, `hasPart`),
3) verifier les mappings questionnaire,
4) tracer le score dans `catalogue_utils.py`.