#!/usr/bin/env python3
"""
update_tools.py
───────────────
Deux fonctions principales :

1. sync_latest_releases(tools_dir, token)
   Pour chaque JSON dans tools/, interroge l'API GitHub,
   compare avec latest_release, et met à jour le JSON si différent.

2. curation_report(tools_dir)
   Pour chaque JSON dans tools/, compare latest_release et curated_release.
   Génère un rapport des outils à recurer manuellement.

Usage :
    # Les deux d'un coup (recommandé)
    python update_tools.py --tools data/tools/

    # Seulement sync GitHub
    python update_tools.py --tools data/tools/ --only-sync

    # Seulement le rapport de curation
    python update_tools.py --tools data/tools/ --only-report

    # Avec token GitHub (évite le rate limiting à 60 req/h)
    python update_tools.py --tools data/tools/ --token ghp_xxxx
    # ou via variable d'environnement :
    export GITHUB_TOKEN=ghp_xxxx
    python update_tools.py --tools data/tools/
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
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────


def get_headers(token: str | None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def extract_owner_repo(repo_url: str) -> tuple[str, str] | None:
    """Extrait (owner, repo) depuis une URL GitHub."""
    match = re.search(r"github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$", repo_url.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def fetch_latest_release(owner: str, repo: str, headers: dict) -> str | None:
    """
    Retourne le tag de la dernière release GitHub.
    Fallback sur le dernier tag si pas de release officielle.
    """
    # 1. Essayer les releases
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        return r.json().get("tag_name")

    # 2. Fallback : tags
    if r.status_code == 404:
        url_tags = f"{GITHUB_API}/repos/{owner}/{repo}/tags?per_page=1"
        r2 = requests.get(url_tags, headers=headers, timeout=10)
        if r2.status_code == 200 and r2.json():
            return r2.json()[0]["name"]
        return None

    r.raise_for_status()
    return None


def normalize_version(v: str | None) -> str:
    """Normalise une version pour comparaison (retire 'v' prefix, strip)."""
    if not v:
        return ""
    return v.strip().lstrip("v")


def load_json(path: Path) -> dict | None:
    """Retourne le dict JSON ou None si le fichier n'est pas parsable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def is_tool_json(data: dict) -> bool:
    """Verifie que c'est bien un JSON d'outil."""
    ctx = data.get("@context", "")
    if isinstance(ctx, str) and "tool_schema" in ctx:
        return True
    return bool(data.get("type") or data.get("supports_shortreads") is not None)


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION 1 — Synchronisation des latest_release depuis GitHub
# ─────────────────────────────────────────────────────────────────────────────


def sync_latest_releases(tools_dir: Path, token: str | None) -> list[dict]:
    """
    Pour chaque JSON de tools_dir :
    - récupère la latest release sur GitHub
    - met à jour le champ latest_release si différente
    - ajoute github_last_fetched

    Retourne la liste des résultats (dict) pour chaque outil.
    """
    headers = get_headers(token)
    results = []

    tool_files = sorted(tools_dir.glob("*.json"))
    if not tool_files:
        print(f"[WARN] Aucun fichier JSON trouvé dans {tools_dir}")
        return results

    print(f"\n{'─'*60}")
    print(f"  SYNCHRONISATION GITHUB — {len(tool_files)} fichier(s)")
    print(f"{'─'*60}")

    for path in tool_files:
        data = load_json(path)
        if data is None or not is_tool_json(data):
            continue
        name = data.get("name", path.stem)
        repo_url = data.get("repo")

        result = {
            "file": path.name,
            "name": name,
            "status": None,
            "old": data.get("latest_release"),
            "new": None,
            "message": "",
        }

        # Ignorer les outils sans repo GitHub
        if not repo_url or "github.com" not in repo_url:
            result["status"] = "SKIP"
            result["message"] = "Pas de repo GitHub renseigné."
            results.append(result)
            print(f"  [{result['status']:7}] {name:20} — {result['message']}")
            continue

        owner_repo = extract_owner_repo(repo_url)
        if not owner_repo:
            result["status"] = "ERROR"
            result["message"] = f"URL GitHub non parsable : {repo_url}"
            results.append(result)
            print(f"  [{result['status']:7}] {name:20} — {result['message']}")
            continue

        owner, repo = owner_repo

        try:
            github_release = fetch_latest_release(owner, repo, headers)
        except requests.HTTPError as e:
            result["status"] = "ERROR"
            result["message"] = f"API GitHub : {e}"
            results.append(result)
            print(f"  [{result['status']:7}] {name:20} — {result['message']}")
            continue
        except requests.RequestException as e:
            result["status"] = "ERROR"
            result["message"] = f"Réseau : {e}"
            results.append(result)
            print(f"  [{result['status']:7}] {name:20} — {result['message']}")
            continue

        if github_release is None:
            result["status"] = "SKIP"
            result["message"] = "Aucune release ni tag trouvé sur GitHub."
            results.append(result)
            print(f"  [{result['status']:7}] {name:20} — {result['message']}")
            continue

        result["new"] = github_release
        current = data.get("latest_release", "")

        if normalize_version(current) == normalize_version(github_release):
            result["status"] = "OK"
            result["message"] = f"À jour ({github_release})"
        else:
            # Mise à jour
            data["latest_release"] = github_release
            data["github_last_fetched"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            save_json(path, data)
            result["status"] = "UPDATED"
            result["message"] = f"{current or '?'}  →  {github_release}"

        results.append(result)
        print(f"  [{result['status']:7}] {name:20} — {result['message']}")

    updated = sum(1 for r in results if r["status"] == "UPDATED")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    print(f"\n  ✅ {updated} mis à jour   ❌ {errors} erreur(s)\n")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION 2 — Rapport de curation manuelle
# ─────────────────────────────────────────────────────────────────────────────


def curation_report(tools_dir: Path, output_path: Path | None = None) -> list[dict]:
    """
    Compare latest_release et curated_release pour chaque outil.
    Si elles diffèrent (ou si curated_release est vide), l'outil est à recurer.

    Affiche le rapport en console et l'écrit dans output_path si fourni.
    Retourne la liste des outils à recurer.
    """
    tool_files = sorted(tools_dir.glob("*.json"))
    to_curate = []
    up_to_date = []
    skipped = []

    for path in tool_files:
        data = load_json(path)
        if data is None or not is_tool_json(data):
            continue
        name = data.get("name", path.stem)
        latest = data.get("latest_release", "")
        curated = data.get("curated_release", "")

        # Ignorer les sous-outils (pas de curation autonome)
        if data.get("type", "").lower() in ("sub-tool", "sub_tool"):
            skipped.append(
                {"name": name, "reason": "Sub-tool (curation via outil parent)"}
            )
            continue

        # Champs manquants
        if not latest or latest.lower() in ("unknown", "null"):
            skipped.append(
                {
                    "name": name,
                    "reason": "latest_release non renseignée — vérifiez GitHub manuellement.",
                    "file": path.name,
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
                    "latest_release": latest,
                    "curated_release": curated or "(vide)",
                    "repo": data.get("repo", "—"),
                    "doi": data.get("doi", "—"),
                }
            )

    # ── Formatage du rapport ──────────────────────────────────────────────────
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("═" * 60)
    lines.append(f"  RAPPORT DE CURATION — {now}")
    lines.append("═" * 60)
    lines.append(
        f"\n  {len(to_curate)} outil(s) à recurer"
        f"  |  {len(up_to_date)} à jour"
        f"  |  {len(skipped)} ignoré(s)\n"
    )

    if to_curate:
        lines.append("─" * 60)
        lines.append("  ⚠️  OUTILS À RECURER MANUELLEMENT")
        lines.append("─" * 60)
        for t in to_curate:
            lines.append(f"\n  🔧 {t['name']}  ({t['file']})")
            lines.append(f"     latest_release  : {t['latest_release']}")
            lines.append(f"     curated_release : {t['curated_release']}")
            if t["repo"] != "—":
                lines.append(f"     repo            : {t['repo']}")
            if t["doi"] != "—":
                lines.append(f"     publication     : {t['doi']}")
            lines.append(
                f"     → Mettez curated_release = \"{t['latest_release']}\" "
                "après avoir vérifié et mis à jour les champs du JSON."
            )
    else:
        lines.append("\n  ✅ Tous les outils sont à jour (curated = latest).")

    if up_to_date:
        lines.append(f"\n{'─'*60}")
        lines.append("  ✅ OUTILS À JOUR")
        lines.append("─" * 60)
        for t in up_to_date:
            lines.append(f"  {t['name']:25} {t['version']}")

    if skipped:
        lines.append(f"\n{'─'*60}")
        lines.append("  ℹ️  IGNORÉS")
        lines.append("─" * 60)
        for t in skipped:
            reason = t.get("reason", "")
            fname = t.get("file", "")
            line = f"  {t['name']:25} {reason}"
            if fname:
                line += f"  ({fname})"
            lines.append(line)

    lines.append("\n" + "═" * 60)
    report_text = "\n".join(lines)

    # ── Affichage console ─────────────────────────────────────────────────────
    print(report_text)

    # ── Écriture fichier ──────────────────────────────────────────────────────
    if output_path:
        output_path.write_text(report_text, encoding="utf-8")
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
        epilog=__doc__,
    )
    parser.add_argument(
        "--tools",
        type=Path,
        default=Path("data/tools"),
        help="Dossier contenant les JSON d'outils (défaut : data/tools/)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="Token GitHub (ou variable d'environnement GITHUB_TOKEN).",
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

    if not args.token and do_sync:
        print(
            "[WARN] Pas de token GitHub — limite : 60 requêtes/heure.\n"
            "[WARN] Utilisez --token ou exportez GITHUB_TOKEN pour 5000 req/h.\n"
        )

    if do_sync:
        sync_latest_releases(args.tools, args.token)

    if do_report:
        curation_report(args.tools, args.report_output)


if __name__ == "__main__":
    main()
