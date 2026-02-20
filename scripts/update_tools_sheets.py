import requests
import re
import sys
import pandas as pd


def get_latest_github_version(repo_url):
    """
    Récupère le tag de la dernière release ou le premier tag valide (non 'latest').
    """
    match = re.search(r"github\.com/([^/]+)/([^/]+)", str(repo_url))
    if not match:
        return None

    owner, repo = match.groups()
    repo = repo.replace(".git", "")

    try:
        # 1. Tentative via l'API 'latest release'
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(api_url, timeout=10)

        if response.status_code == 200:
            tag_name = response.json().get("tag_name")
            # Si le tag n'est pas "latest", on le traite
            if tag_name.lower() != "latest":
                return tag_name[1:] if tag_name.startswith("v") else tag_name

        # 2. Fallback : Parcourir les tags pour trouver une version réelle
        # On cherche le premier tag qui contient un chiffre (pour éviter 'latest', 'stable', etc.)
        tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
        tags_response = requests.get(tags_url, timeout=10)

        if tags_response.status_code == 200:
            tags = tags_response.json()
            for tag in tags:
                name = tag.get("name")
                # On ignore 'latest' et on vérifie s'il y a au moins un chiffre dans le tag
                if name.lower() != "latest" and any(char.isdigit() for char in name):
                    return name[1:] if name.startswith("v") else name

    except Exception as e:
        print(f"Erreur de connexion à l'API GitHub pour {repo}: {e}")

    return None


# Retourne True si une mise à jour est disponible, False sinon
def update_or_not(repo_url, local_release):
    """
    Compare la version locale avec la version distante.
    """
    print(f"Vérification du dépôt : {repo_url}")
    print(f"Version locale actuelle : {local_release}")
    to_update = False
    remote_version = get_latest_github_version(repo_url)

    if remote_version is None:
        print("Impossible de récupérer la version distante.")
        return True
    print(f"Dernière version sur GitHub : {remote_version}")

    if remote_version == local_release:
        print("✅ Votre version est à jour.")
        print("--------------------------------------------------")
        return False
    else:
        print(
            f"⚠️ Une nouvelle version est disponible ! ({local_release} -> {remote_version})"
        )
        print("--------------------------------------------------")
        return True


if __name__ == "__main__":
    # 1. Chargement du fichier
    try:
        tools = pd.read_csv("Tools.tsv", sep="\t")
        print(f"Chargement réussi : {len(tools)} lignes trouvées.")
    except FileNotFoundError:
        print("Erreur : Le fichier Tools.tsv est introuvable.")
        sys.exit(1)

    # 2. Nettoyage de la colonne Release (supprime le 'v' initial si présent)
    # On s'assure d'abord que les données sont des chaînes de caractères
    tools["Release"] = (
        tools["Release"].astype(str).apply(lambda x: x[1:] if x.startswith("v") else x)
    )

    # 3. Vérification des versions
    print("Vérification des versions en cours...")

    tools["To update"] = tools.apply(
        lambda row: update_or_not(row["repo"], row["Release"]), axis=1
    )

    # 4. Affichage et sauvegarde
    print("\nRésultats de l'analyse :")
    print(tools[["repo", "Release", "To update"]])
    tools.to_csv("Tools_updated.tsv", sep="\t", index=False)
