#!/usr/bin/env python3
"""
update_tools.py
───────────────
Deux fonctions :

1. sync_latest_releases(tools_dir, token)
   Pour chaque JSON dans tools_dir/, interroge l'API GitHub via le champ
   'repo', récupère la dernière release, et met à jour 'latest_release'
   dans le JSON si la valeur a changé.

2. curation_report(tools_dir, output_path)
   Pour chaque JSON dans tools_dir/, compare 'latest_release' et
   'curated_release'. Génère un rapport des outils à recurer manuellement.

Hypothèses minimales sur les JSONs :
  - Tout fichier .json dans tools_dir est un outil.
  - Les champs utilisés sont : name, repo, latest_release, curated_release.
  - Si un champ est absent, il est traité comme vide/inconnu.
  - Si un fichier est invalide (JSON malformé), il est signalé et ignoré.

Usage :
    python update_tools.py --tools data/tools/

    python update_tools.py --tools data/tools/ --only-sync
    python update_tools.py --tools data/tools/ --only-report
    python update_tools.py --tools data/tools/ --report-output mon_rapport.txt

    # Token GitHub (évite la limite 60 req/h anonyme)
    python update_tools.py --tools data/tools/ --token ghp_xxxx
    export GITHUB_TOKEN=ghp_xxxx && python update_tools.py --tools data/tools/
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"


# ─────────────────────────────────────────────────────────────────────────────
# I/O
# ─────────────────────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict | None:
    """
    Charge un fichier JSON. Retourne None si le fichier est invalide,
    avec un message d'avertissement.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  [WARN] {path.name} ignoré — JSON invalide : {e}")
        return None
    except UnicodeDecodeError as e:
        print(f"  [WARN] {path.name} ignoré — encodage invalide : {e}")
        return None


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def iter_tools(tools_dir: Path):
    """
    Itère sur tous les fichiers .json dans tools_dir.
    Yield : (path, data) pour les fichiers valides.
    """
    files = sorted(tools_dir.glob("*.json"))
    if not files:
        print(f"[WARN] Aucun fichier .json trouvé dans {tools_dir}")
        return
    for path in files:
        data = load_json(path)
        if data is not None:
            yield path, data


# ─────────────────────────────────────────────────────────────────────────────
# GITHUB
# ─────────────────────────────────────────────────────────────────────────────


def get_headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def extract_owner_repo(repo_url: str) -> tuple[str, str] | None:
    match = re.search(
        r"github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$",
        repo_url.strip(),
    )
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_github_latest(owner: str, repo: str, headers: dict) -> str | None:
    """
    Retourne le tag de la dernière release officielle.
    Si aucune release n'existe, retourne le dernier tag.
    Si rien n'existe, retourne None.
    """
    # 1. Release officielle
    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest",
        headers=headers,
        timeout=10,
    )
    if r.status_code == 200:
        return r.json().get("tag_name")

    # 2. Fallback : tags
    if r.status_code == 404:
        r2 = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/tags?per_page=1",
            headers=headers,
            timeout=10,
        )
        if r2.status_code == 200 and r2.json():
            return r2.json()[0]["name"]
        return None

    r.raise_for_status()


def normalize_version(v) -> str:
    """Normalise pour comparaison : retire préfixe 'v', strip."""
    if not v:
        return ""
    return str(v).strip().lstrip("v")


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION 1 — Sync latest_release depuis GitHub
# ─────────────────────────────────────────────────────────────────────────────


def sync_latest_releases(tools_dir: Path, token: str | None) -> list[dict]:
    """
    Pour chaque JSON dans tools_dir :
      - lit le champ 'repo'
      - interroge l'API GitHub
      - met à jour 'latest_release' et 'github_last_fetched' si nécessaire

    Retourne la liste des résultats par outil.
    """
    headers = get_headers(token)
    results = []

    print(f"\n{'─'*62}")
    print("  SYNC GITHUB — latest_release")
    print(f"{'─'*62}")

    for path, data in iter_tools(tools_dir):
        name = data.get("name") or path.stem
        repo_url = data.get("repo")

        result = {
            "file": path.name,
            "name": name,
            "status": None,
            "old": data.get("latest_release"),
            "new": None,
            "message": "",
        }

        # Pas de repo renseigné
        if not repo_url:
            result["status"] = "SKIP"
            result["message"] = "Champ 'repo' absent ou vide."
            results.append(result)
            _print_result(result)
            continue

        # Repo non-GitHub
        if "github.com" not in repo_url:
            result["status"] = "SKIP"
            result["message"] = f"Repo non-GitHub : {repo_url}"
            results.append(result)
            _print_result(result)
            continue

        owner_repo = extract_owner_repo(repo_url)
        if not owner_repo:
            result["status"] = "ERROR"
            result["message"] = f"URL GitHub non parsable : {repo_url}"
            results.append(result)
            _print_result(result)
            continue

        owner, repo = owner_repo

        try:
            github_tag = fetch_github_latest(owner, repo, headers)
        except requests.HTTPError as e:
            result["status"] = "ERROR"
            result["message"] = f"API GitHub : {e}"
            results.append(result)
            _print_result(result)
            continue
        except requests.RequestException as e:
            result["status"] = "ERROR"
            result["message"] = f"Réseau : {e}"
            results.append(result)
            _print_result(result)
            continue

        if github_tag is None:
            result["status"] = "SKIP"
            result["message"] = "Aucune release ni tag trouvé sur GitHub."
            results.append(result)
            _print_result(result)
            continue

        result["new"] = github_tag
        current = data.get("latest_release")

        if normalize_version(current) == normalize_version(github_tag):
            result["status"] = "OK"
            result["message"] = f"À jour ({github_tag})"
        else:
            data["latest_release"] = github_tag
            data["github_last_fetched"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            save_json(path, data)
            result["status"] = "UPDATED"
            result["message"] = f"{current or '?'}  →  {github_tag}"

        results.append(result)
        _print_result(result)

    updated = sum(1 for r in results if r["status"] == "UPDATED")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    print(f"\n  ✅ {updated} mis à jour   ❌ {errors} erreur(s)\n")
    return results


def _print_result(r: dict) -> None:
    print(f"  [{r['status']:7}] {r['name'][:22]:22} {r['message']}")


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION 2 — Rapport de curation manuelle
# ─────────────────────────────────────────────────────────────────────────────


def curation_report(
    tools_dir: Path,
    output_path: Path | None = None,
) -> list[dict]:
    """
    Compare 'latest_release' et 'curated_release' pour chaque outil.
    Génère un rapport des outils dont la curation est en retard.

    Un outil est à recurer si :
      - curated_release est absent, vide, ou différent de latest_release.

    Un outil est ignoré si :
      - latest_release est absent ou 'unknown' (impossible de comparer).

    Retourne la liste des outils à recurer.
    """
    to_curate = []
    up_to_date = []
    skipped = []

    for path, data in iter_tools(tools_dir):
        name = data.get("name") or path.stem
        latest = data.get("latest_release")
        curated = data.get("curated_release")

        # Impossible de comparer sans latest_release valide
        if not latest or str(latest).strip().lower() in ("", "unknown", "null", "none"):
            skipped.append(
                {
                    "name": name,
                    "file": path.name,
                    "reason": f"'latest_release' = {repr(latest)} — vérification GitHub manuelle requise.",
                }
            )
            continue

        if normalize_version(curated) == normalize_version(latest):
            up_to_date.append({"name": name, "version": latest})
        else:
            to_curate.append(
                {
                    "name": name,
                    "file": path.name,
                    "latest_release": str(latest),
                    "curated_release": str(curated) if curated else "(vide)",
                    "repo": data.get("repo") or "—",
                    "doi": data.get("doi") or "—",
                }
            )

    # ── Formatage ────────────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []

    lines.append("═" * 62)
    lines.append(f"  RAPPORT DE CURATION — {now}")
    lines.append("═" * 62)
    lines.append(
        f"\n  {len(to_curate)} à recurer  "
        f"|  {len(up_to_date)} à jour  "
        f"|  {len(skipped)} ignoré(s)\n"
    )

    if to_curate:
        lines.append("─" * 62)
        lines.append("  ⚠️  OUTILS À RECURER MANUELLEMENT")
        lines.append("─" * 62)
        for t in to_curate:
            lines.append(f"\n  🔧 {t['name']}  ({t['file']})")
            lines.append(f"     latest_release  : {t['latest_release']}")
            lines.append(f"     curated_release : {t['curated_release']}")
            if t["repo"] != "—":
                lines.append(f"     repo            : {t['repo']}")
            if t["doi"] != "—":
                lines.append(f"     publication     : {t['doi']}")
            lines.append(
                f"     → Après curation, mettez "
                f"curated_release = \"{t['latest_release']}\"."
            )
    else:
        lines.append("\n  ✅ Tous les outils sont à jour.")

    if up_to_date:
        lines.append(f"\n{'─'*62}")
        lines.append("  ✅ À JOUR")
        lines.append("─" * 62)
        for t in up_to_date:
            lines.append(f"  {t['name'][:30]:30} {t['version']}")

    if skipped:
        lines.append(f"\n{'─'*62}")
        lines.append("  ℹ️  IGNORÉS (latest_release manquante ou inconnue)")
        lines.append("─" * 62)
        for t in skipped:
            lines.append(f"  {t['name'][:30]:30} ({t['file']})")
            lines.append(f"    → {t['reason']}")

    lines.append("\n" + "═" * 62)
    report_text = "\n".join(lines)

    print(report_text)

    if output_path:
        output_path.write_text(report_text + "\n", encoding="utf-8")
        print(f"\n  📄 Rapport sauvegardé : {output_path}\n")

    return to_curate


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Synchronise les latest_release depuis GitHub et génère "
            "un rapport de curation pour les outils du catalogue."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tools",
        type=Path,
        default=Path("data/tools"),
        help="Dossier contenant les JSON d'outils (défaut : data/tools/).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="Token GitHub personnel (ou variable GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--only-sync",
        action="store_true",
        help="Effectuer uniquement la synchronisation GitHub.",
    )
    parser.add_argument(
        "--only-report",
        action="store_true",
        help="Générer uniquement le rapport de curation.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("curation_report.txt"),
        help="Fichier de sortie du rapport (défaut : curation_report.txt).",
    )

    args = parser.parse_args()

    if not args.tools.is_dir():
        print(f"[ERROR] Dossier introuvable : {args.tools}")
        sys.exit(1)

    do_sync = not args.only_report
    do_report = not args.only_sync

    if do_sync and not args.token:
        print(
            "[WARN] Pas de token GitHub fourni.\n"
            "[WARN] Limite anonyme : 60 requêtes/heure.\n"
            "[WARN] Utilisez --token ou exportez GITHUB_TOKEN.\n"
        )

    if do_sync:
        sync_latest_releases(args.tools, args.token)

    if do_report:
        curation_report(args.tools, args.report_output)


if __name__ == "__main__":
    main()
