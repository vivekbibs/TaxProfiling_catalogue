"""Configuration constants for the recommendation engine.

Keeping weights and aliases in one place makes tuning the recommender easier
without touching the core matching logic.
"""

SCORE_WEIGHTS = {
    "match_envo": 4,
    "match_host": 4,
    "global_fallback": 1,
    "composite_bonus": 1,
    "gtdb_bonus": 2,
    "globdb_bonus": 3,
    "part_score_inheritance": 1,
    "broad_context_bonus": 1,
}

PREFERENCE_ALIASES = {"indifférent": "any", "indifferent": "any", "any": "any"}
# ─────────────────────────────────────────────────────────────────────────────
# CORRESPONDANCES  question → filtres
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_FILTER: dict[str, tuple] = {
    "Human gut": ("ENVO_00002003", "NCBITaxon_9606"),
    "Human skin": ("ENVO_2100003", "NCBITaxon_9606"),
    "Human mouth": ("ENVO_08000002", "NCBITaxon_9606"),
    "Mouse gut (Mus musculus)": ("ENVO_00002003", "NCBITaxon_10090"),
    "Rat gut (Rattus norvegicus)": ("ENVO_00002003", "NCBITaxon_10116"),
    "Dog gut (Canis lupus)": ("ENVO_00002003", "NCBITaxon_9615"),
    "Cat gut (Felis catus)": ("ENVO_00002003", "NCBITaxon_9685"),
    "Pig gut (Sus scrofa)": ("ENVO_00002003", "NCBITaxon_9825"),
    "Rabbit gut (Oryctolagus cuniculus)": ("ENVO_00002003", "NCBITaxon_9986"),
    "Chicken caecum (Gallus gallus)": ("GENEPIO_0100899", "NCBITaxon_9031"),
    "Goat gut (Capra hircus)": ("ENVO_00002003", "NCBITaxon_9925"),
    "Sheep gut (Ovis aries)": ("ENVO_00002003", "NCBITaxon_9940"),
    "Soil": ("ENVO_00001998", None),
    "Ocean / Marine water": ("ENVO_00002006", "ENVO_00002149"),
    "Fresh water / Lake / River": ("ENVO_00002006", None),
    "Sediment": ("ENVO_00002007", None),
    "Glacier-fed Streams": ("ENVO_00002007", "ENVO_00001529"),
    "Food": ("FOODON_00002403", None),
    "Multi-environments / Global": (None, None),
    "Other/ I don't know": (None, None),
}

SAMPLE_CATEGORIES: dict[str, list[str]] = {
    "Human": [
        "Human gut",
        "Human skin",
        "Human mouth",
    ],
    "Animal": [
        "Mouse gut (Mus musculus)",
        "Rat gut (Rattus norvegicus)",
        "Dog gut (Canis lupus)",
        "Cat gut (Felis catus)",
        "Pig gut (Sus scrofa)",
        "Rabbit gut (Oryctolagus cuniculus)",
        "Chicken caecum (Gallus gallus)",
        "Goat gut (Capra hircus)",
        "Sheep gut (Ovis aries)",
    ],
    "Environmental": [
        "Soil",
        "Ocean / Marine water",
        "Fresh water / Lake / River",
        "Sediment",
        "Glacier-fed streams",
        "Food",
    ],
    "Multi-environments / Global": ["Multi-environments / Global"],
    "Other": ["Other / I don't know"],
}

TAXON_IRI: dict[str, str] = {
    "Bacteria": "NCBITaxon_2",
    "Archaea": "NCBITaxon_2157",
    "Eukaryota": "NCBITaxon_2759",
    "Viruses": "NCBITaxon_10239",
    "Fungi": "NCBITaxon_4751",
}

SPECIAL_SCOPE_TAGS = {"virus", "fungi", "eukaryota", "plasmid"}
