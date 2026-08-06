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
