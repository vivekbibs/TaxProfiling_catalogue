import json
import os

def update_or_create_sub_db(data, output_dir):
    """
    Parcourt les éléments de 'hasPart' dans GlobDB.
    Si le fichier existe, ajoute/met à jour 'isPartOf'.
    Si le fichier n'existe pas, le crée avec la structure de base.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for part in data["hasPart"]:
        file_id = part["id"]
        file_name = f"{file_id}.json"
        file_path = os.path.join(output_dir, file_name)
        
        # Valeur du parent
        parent_id = data.get("@id", "globdb")

        if os.path.exists(file_path):
            # --- MODE MISE À JOUR ---
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    sub_db = json.load(f)
                except json.JSONDecodeError:
                    print(f"⚠️ Erreur de lecture : {file_path} est corrompu.")
                    continue
            
            # Ajout ou mise à jour du champ
            sub_db["isPartOf"] = parent_id
            action = "Mis à jour"
        else:
            # --- MODE CRÉATION ---
            sub_db = {
                "name": part["name"],
                "@id": file_id,
                "type": "Microbial Database",
                "virus": False,
                "eukaryotes": False,
                "bacteria": True,
                "archaea": True,
                "release": str(part.get("release", "unknown")),
                "environment": "specific",
                "isPartOf": parent_id,
                "bacteria_archaea_databases": [],
                "viral_databases": [],
                "eukaryote_databases": []
            }
            action = "Généré (nouveau)"

        # Sauvegarde
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sub_db, f, indent=2, ensure_ascii=False)
        
        print(f"✅ {action} : {file_path}")

if __name__ == "__main__":
    # Chemins basés sur votre structure
    glob_db_path = "/home/vashokan/Bureau/IS4/catalogue/databases/globdb.json"
    output_dir = "/home/vashokan/Bureau/IS4/catalogue/databases"

    try:
        with open(glob_db_path, 'r', encoding='utf-8') as f:
            glob_db = json.load(f)
        
        print(f"🚀 Analyse de {glob_db['name']} en cours...")
        update_or_create_sub_db(glob_db, output_dir)
        print("\n✨ Opération terminée avec succès.")
        
    except FileNotFoundError:
        print(f"❌ Erreur : Le fichier principal {glob_db_path} est introuvable.")
    except Exception as e:
        print(f"❌ Une erreur est survenue : {e}")