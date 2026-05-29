import argparse
import sys

import pandas as pd


def get_tax_level(tax_string):
    """Déduit le niveau taxonomique à partir du dernier préfixe de la chaîne Sylph."""
    last_node = str(tax_string).split("|")[-1]
    if last_node.startswith("d__"):
        return "domain"
    elif last_node.startswith("p__"):
        return "phylum"
    elif last_node.startswith("c__"):
        return "class"
    elif last_node.startswith("o__"):
        return "order"
    elif last_node.startswith("f__"):
        return "family"
    elif last_node.startswith("g__"):
        return "genus"
    elif last_node.startswith("s__"):
        return "species"
    elif last_node.startswith("t__"):
        return "strain"
    return "unknown"


def parse_sylph(filepath):
    """Parse et standardise la sortie de Sylph."""
    try:
        # Extraire le nom de l'échantillon depuis la première ligne (ex: #SampleID  mouse_1.fq)
        with open(filepath, "r") as f:
            first_line = f.readline()

        sample_id = (
            first_line.strip().split("\t")[1]
            if first_line.startswith("#SampleID")
            else "unknown_sample"
        )

        # Charger le reste du tableau (en sautant la première ligne)
        df = pd.read_csv(filepath, sep="\t", skiprows=1)

        # Créer le DataFrame standardisé
        std_df = pd.DataFrame(
            {
                "Sample": sample_id,
                "Taxonomy": df["clade_name"],
                "Relative_Abundance": df["relative_abundance"],
                "Level": df["clade_name"].apply(get_tax_level),
                "Tool": "Sylph",
            }
        )
        return std_df
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier Sylph : {e}")
        sys.exit(1)


def parse_singlem(filepath):
    """Parse et standardise la sortie 'with_extras' de SingleM."""
    try:
        df = pd.read_csv(filepath, sep="\t")

        if "relative_abundance" not in df.columns:
            print(
                "Erreur: Le fichier SingleM doit contenir la colonne 'relative_abundance'."
            )
            print(
                "Veuillez générer le fichier avec 'singlem summarise --output-taxonomic-profile-with-extras'."
            )
            sys.exit(1)

        # Standardiser la taxonomie : enlever "Root; " et remplacer "; " par "|"
        # SingleM format: Root; d__Bacteria; p__Proteobacteria...
        tax_std = (
            df["taxonomy"]
            .str.replace(r"^Root(?:;\s*)?", "", regex=True)
            .str.replace("; ", "|")
        )

        std_df = pd.DataFrame(
            {
                "Sample": df["sample"],
                "Taxonomy": tax_std,
                "Relative_Abundance": df["relative_abundance"],
                "Level": df["level"],
                "Tool": "SingleM",
            }
        )
        return std_df
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier SingleM : {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Standardise les profils taxonomiques de Sylph et SingleM."
    )
    parser.add_argument(
        "--sylph", required=True, help="Fichier de sortie de Sylph (.sylphmpa)"
    )
    parser.add_argument(
        "--singlem",
        required=True,
        help="Fichier de sortie SingleM (format 'with_extras' TSV)",
    )
    parser.add_argument(
        "--output", required=True, help="Fichier CSV de sortie fusionné"
    )

    args = parser.parse_args()

    print("Traitement du fichier Sylph...")
    df_sylph = parse_sylph(args.sylph)

    print("Traitement du fichier SingleM...")
    df_singlem = parse_singlem(args.singlem)

    print("Fusion des données...")
    df_combined = pd.concat([df_sylph, df_singlem], ignore_index=True)

    # Sauvegarde
    df_combined.to_csv(args.output, sep="\t", index=False)
    print(f"Fichier standardisé généré avec succès : {args.output}")


if __name__ == "__main__":
    main()
