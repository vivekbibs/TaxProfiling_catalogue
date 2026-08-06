from pathlib import Path

from src.catalogue_utils import load_catalogue, recommend


def test_recommend_returns_results_for_basic_catalogue(tmp_path):
    db_dir = tmp_path / "db"
    tool_dir = tmp_path / "tools"
    db_dir.mkdir(parents=True)
    tool_dir.mkdir(parents=True)

    (db_dir / "db1.json").write_text(
        """
        {
          "@id": "db1",
          "name": "Example DB",
          "sample": [{"@id": "obo:ENVO_00002003", "label": "gut"}],
          "origin": [{"@id": "obo:NCBITaxon_9606", "label": "human"}],
          "taxonomic_scope": [{"@id": "NCBITaxon_2", "label": "Bacteria"}],
          "supports_shortreads": true,
          "supports_longreads": true
        }
        """,
        encoding="utf-8",
    )
    (tool_dir / "tool1.json").write_text(
        """
        {
          "@id": "tool1",
          "name": "Example Tool",
          "supports_shortreads": true,
          "supports_longreads": true,
          "uses_databases": [{"@id": "db1", "taxonomy_system": "GTDB"}]
        }
        """,
        encoding="utf-8",
    )

    databases, tools = load_catalogue(db_dir, tool_dir)
    results = recommend(
        databases,
        tools,
        "ENVO_00002003",
        "NCBITaxon_9606",
        ["Bacteria"],
        "Short Reads",
        "Any",
        False,
        False,
        512,
    )

    assert results
    assert results[0]["tool_id"] == "tool1"
    assert results[0]["db_id"] == "db1"
