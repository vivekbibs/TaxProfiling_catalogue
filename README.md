# Taxonomic Profiling Catalog

This project centralizes a **catalog** of tools and associated reference databases for taxonomic profiling (metagenomics), featuring:

- A **Streamlit** interface to explore the catalog and obtain recommendations based on user questions and needs;
- Workflow **notebooks** to launch analyses on the IFB cluster and cloud;
- Utility scripts for curation and updates.

The goal is to properly link:
1) tool metadata,
2) database metadata,
3) user use cases (sample type, target taxa, technical constraints, etc.).

---

# What is Taxonomic Profiling? 
The following introduction was largely inspired by:

Sophia Hampe, Bérénice Batut, Paul Zierep, Taxonomic Profiling and Visualization of Metagenomic Data (Galaxy Training Materials). [https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html](https://training.galaxyproject.org/training-material/topics/microbiome/tutorials/taxonomic-profiling/tutorial.html)

Hiltemann, Saskia, Rasche, Helena et al., 2023 Galaxy Training: A Powerful Framework for Teaching! PLOS Computational Biology [10.1371/journal.pcbi.1010752](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010752)

Batut et al., 2018 Community-Driven Data Analysis Training for Biology Cell Systems [10.1016/j.cels.2018.05.012](https://doi.org/10.1016%2Fj.cels.2018.05.012)

---

## 5) Maintenance and Contribution

### 5.1 Project Structure

```text
.
├── data/
│   ├── databases/       # JSON-LD files for databases
│   └── tools/           # JSON-LD files for tools
├── scripts/
│   ├── streamlit/       # Streamlit application (app.py)
│   └── processing/      # Curation and extraction scripts
└── notebooks/           # Analysis templates for IFB