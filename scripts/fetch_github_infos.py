#!/usr/bin/env python3
"""
fetch_github_info.py

Reads a JSON file (tool or database catalogue), extracts the 'repo' field
(expected: a GitHub URL like https://github.com/owner/repo),
then fetches via GitHub API:
  - latest release tag
  - number of open issues

Updates the JSON file in-place with:
  - latest_release
  - open_issues
  - github_last_fetched (ISO timestamp)

Usage:
    python fetch_github_info.py <file.json> [--token YOUR_GITHUB_TOKEN]

GitHub token is optional but strongly recommended to avoid rate limiting
(60 req/h unauthenticated vs 5000 req/h authenticated).
You can also set the GITHUB_TOKEN environment variable instead.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests


GITHUB_API = "https://api.github.com"


def extract_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {repo_url}")
    return match.group(1), match.group(2)


def get_headers(token: str | None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_latest_release(owner: str, repo: str, headers: dict) -> str | None:
    """Return the latest release tag, or None if no releases exist."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code == 404:
        # No releases — try tags as fallback
        url_tags = f"{GITHUB_API}/repos/{owner}/{repo}/tags"
        resp_tags = requests.get(url_tags, headers=headers, timeout=10)
        if resp_tags.status_code == 200 and resp_tags.json():
            return resp_tags.json()[0]["name"]
        return None

    resp.raise_for_status()
    return resp.json().get("tag_name")


def fetch_open_issues(owner: str, repo: str, headers: dict) -> int:
    """Return the number of open issues (excluding pull requests)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # open_issues_count includes PRs — subtract open PRs
    total = data.get("open_issues_count", 0)

    # Count open PRs
    url_prs = f"{GITHUB_API}/repos/{owner}/{repo}/pulls?state=open&per_page=1"
    resp_prs = requests.get(url_prs, headers=headers, timeout=10)
    if resp_prs.status_code == 200:
        # Use Link header to get total PR count if paginated
        link = resp_prs.headers.get("Link", "")
        match = re.search(r'page=(\d+)>; rel="last"', link)
        if match:
            open_prs = int(match.group(1))
        else:
            open_prs = len(resp_prs.json())
    else:
        open_prs = 0

    return max(0, total - open_prs)


def process_file(filepath: str, token: str | None) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    repo_url = data.get("repo")
    if not repo_url:
        print(f"[SKIP] No 'repo' field found in {filepath}")
        return

    print(f"[INFO] Processing: {filepath}")
    print(f"[INFO] Repo: {repo_url}")

    try:
        owner, repo = extract_owner_repo(repo_url)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    headers = get_headers(token)

    try:
        latest_release = fetch_latest_release(owner, repo, headers)
        open_issues = fetch_open_issues(owner, repo, headers)
    except requests.HTTPError as e:
        print(f"[ERROR] GitHub API error: {e}")
        return
    except requests.RequestException as e:
        print(f"[ERROR] Network error: {e}")
        return

    # Update JSON fields
    data["latest_release"] = latest_release or "no release found"
    data["open_issues"] = open_issues
    data["github_last_fetched"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[OK]   latest_release   : {data['latest_release']}")
    print(f"[OK]   open_issues      : {open_issues}")
    print(f"[OK]   github_last_fetched : {data['github_last_fetched']}")
    print(f"[OK]   File updated: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch GitHub latest release and open issues for a catalogue JSON file."
    )
    parser.add_argument("files", nargs="+", help="Path(s) to JSON file(s) to update")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    args = parser.parse_args()

    if not args.token:
        print("[WARN] No GitHub token provided — rate limit: 60 requests/hour.")
        print(
            "[WARN] Set GITHUB_TOKEN env var or use --token to increase to 5000/hour.\n"
        )

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"[ERROR] File not found: {filepath}")
            continue
        process_file(filepath, args.token)
        print()


if __name__ == "__main__":
    main()
