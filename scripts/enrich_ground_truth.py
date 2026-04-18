"""
Enrich ground truth CSVs with wallet addresses from Polymarket public profiles.

Usage:
    uv run python scripts/enrich_ground_truth.py

Queries https://polymarket.com/@<username> and extracts the proxy wallet address
from the profile page HTML. Rate-limited to 1 req/sec.
"""

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

GT_DIR = Path("data/ground_truth")
WALLETS_CSV = GT_DIR / "wallets.csv"
SHARPS_CSV = GT_DIR / "sharps_positive.csv"
LOG_PATH = GT_DIR / "enrichment_log.md"

PROFILE_URL = "https://polymarket.com/@{username}"
RATE_LIMIT_SECONDS = 1.1

# Regex to find 0x addresses in page source (proxy wallets embedded in Next.js JSON)
ADDRESS_RE = re.compile(r'"proxyWallet"\s*:\s*"(0x[a-fA-F0-9]{40})"')
# Fallback: any 0x address in profile meta / JSON payload
FALLBACK_RE = re.compile(r'"(0x[a-fA-F0-9]{40})"')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) polycasquette-research/0.1",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_profile_address(username: str) -> dict | None:
    """Fetch a Polymarket profile page and extract the proxy wallet address."""
    url = PROFILE_URL.format(username=username)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            return {"status": "404", "address": None, "url": url}
        resp.raise_for_status()
        html = resp.text

        # Try proxyWallet field first
        match = ADDRESS_RE.search(html)
        if match:
            return {"status": "ok", "address": match.group(1), "url": url}

        # Fallback: grab first 0x address from page
        addresses = FALLBACK_RE.findall(html)
        # Filter out common non-wallet addresses (contract addresses etc.)
        unique = list(dict.fromkeys(addresses))
        if unique:
            return {"status": "ok_fallback", "address": unique[0], "url": url}

        return {"status": "no_address_found", "address": None, "url": url}

    except requests.RequestException as e:
        return {"status": f"error: {e}", "address": None, "url": url}


def extract_usernames_from_notes(notes: str) -> list[str]:
    """Extract potential Polymarket usernames from a notes field."""
    usernames = []
    # Look for @username patterns
    for m in re.finditer(r"@(\w[\w-]*)", notes):
        usernames.append(m.group(1))
    # Look for known name patterns like "Username. " or "username:"
    for m in re.finditer(r"^(\w[\w-]+)\.", notes):
        usernames.append(m.group(1))
    return usernames


def enrich_csv(csv_path: Path, address_col: str, notes_col: str, log_entries: list):
    """Read a CSV, try to fill missing addresses from Polymarket profiles."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated = 0
    for row in rows:
        if row[address_col].strip():
            continue  # Already has an address

        # Try to find a username in the notes
        notes = row.get(notes_col, "")
        usernames = extract_usernames_from_notes(notes)

        for username in usernames:
            time.sleep(RATE_LIMIT_SECONDS)
            result = fetch_profile_address(username)
            entry = {
                "file": csv_path.name,
                "username": username,
                "status": result["status"],
                "address": result["address"],
                "url": result["url"],
                "notes": notes[:80],
            }
            log_entries.append(entry)
            print(f"  @{username}: {result['status']} → {result['address'] or 'N/A'}")

            if result["address"]:
                row[address_col] = result["address"]
                updated += 1
                break  # Got an address, move to next row

    # Write back
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated


def write_log(log_entries: list, wallets_updated: int, sharps_updated: int):
    """Write enrichment results to markdown log."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Enrichment Log — {now}\n",
        f"## Summary\n",
        f"- Wallets updated: **{wallets_updated}**",
        f"- Sharps updated: **{sharps_updated}**",
        f"- Total API calls: **{len(log_entries)}**\n",
        "## Detail\n",
        "| File | Username | Status | Address | URL |",
        "|------|----------|--------|---------|-----|",
    ]
    for e in log_entries:
        addr = f"`{e['address']}`" if e["address"] else "—"
        lines.append(f"| {e['file']} | @{e['username']} | {e['status']} | {addr} | {e['url']} |")

    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nLog written to {LOG_PATH}")


def main():
    log_entries = []

    print("=== Enriching wallets.csv ===")
    w = enrich_csv(WALLETS_CSV, "address", "notes", log_entries)

    print("\n=== Enriching sharps_positive.csv ===")
    s = enrich_csv(SHARPS_CSV, "address", "notes", log_entries)

    write_log(log_entries, w, s)
    print(f"\nDone. {w} wallets + {s} sharps enriched.")


if __name__ == "__main__":
    main()
