import os
import json


def create_sub_db_files(data,outpur_dir):
    """
    Crée un fichier JSON pour chaque élément dans 'hasPart'.
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for part in data["hasPart"]:
        # Construction de l'objet pour la sous-base
        # On garde la structure de base, mais on l'adapte à la sous-base
        sub_db = {
            "name": part["name"],
            "@id": part["id"],
            "type": "Microbial Database", # Type par défaut
            "virus": False,               # Valeurs par défaut à ajuster manuellement si besoin
            "eukaryotes": False,
            "bacteria": True,
            "archaea": True,
            "release": str(part.get("release", "unknown")),
            "environment": "specific",    # Valeur par défaut
            "isPartOf": data["@id"],      # On indique l'appartenance à GlobDB
            "bacteria_archaea_databases": [],
            "viral_databases": [],
            "eukaryote_databases": []
        }

        # Nom du fichier basé sur l'ID
        file_name = f"{part['id']}.json"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sub_db, f, indent=2, ensure_ascii=False)
        
        print(f"Généré : {file_path}")

if __name__ == "__main__":
    glob_db_path = "databases/globdb.json"
    # Création d'un dossier de sortie pour ne pas polluer le répertoire courant
    output_dir = "/home/vashokan/Bureau/IS4/catalogue/databases"
    with open(glob_db_path, 'r', encoding='utf-8') as f:
        glob_db = json.load(f)
    create_sub_db_files(glob_db,output_dir)
    print("\nTerminé ! Les fichiers sont dans le dossier 'sub_databases/'.")