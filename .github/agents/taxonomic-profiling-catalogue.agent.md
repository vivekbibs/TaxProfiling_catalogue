---
name: taxonomic-profiling-catalogue
description: "Use when adapting the JSON database structure in data/databases and data/tools, improving the Streamlit UI in src/app.py, or tuning the recommendation engine in src/catalogue_utils.py for the taxonomic profiling catalogue."
applyTo:
  - "src/**"
  - "data/databases/**"
  - "data/tools/**"
  - "data/schemas/**"
tags:
  - streamlit
  - recommendation
  - taxonomy
  - database-structure
---

This custom agent is optimized for work on the TaxProfiling_catalogue repository.

Use this agent when you need help with:
- Designing or refactoring the structure of JSON database metadata in `data/databases`.
- Managing tool metadata in `data/tools` and how tools map to reference databases.
- Improving the Streamlit interface in `src/app.py` for presenting database/tool recommendations.
- Enhancing the recommendation engine logic in `src/catalogue_utils.py`.
- Handling composite databases, `hasPart` / `isPartOf` relations, sample/origin scope, and taxonomic scope.
- Aligning questionnaire inputs with database filtering and tool selection.

Recommended prompts to try with this agent:
- "Help me improve the recommendation engine so it better matches sample/origin filters and taxonomic preferences."
- "Refactor the Streamlit survey UI to make database and tool recommendations more intuitive."
- "Update the JSON schema and loader to support composite databases with hasPart/isPartOf relations."
- "Explain how tools with multiple reference databases are scored and how to change that behavior."
