"""Scan Polymarket Gamma API for active US macro economic data release markets."""

import re, time, json, requests, pandas as pd
from datetime import datetime

API = "https://gamma-api.polymarket.com/markets"
# Word-boundary patterns to avoid false positives (ISM != Ismaily, CPI != CPI(M), etc.)
KEYWORD_PATTERNS = [
    r"\bCPI\b", r"\binflation\b", r"\bnonfarm\b", r"\bpayrolls?\b",
    r"\bFed\b", r"\bFOMC\b", r"\binterest rate", r"\brate cut", r"\brate hike",
    r"\bGDP\b", r"\bunemployment\b", r"\bretail sales\b", r"\bPCE\b",
    r"\bPPI\b", r"\bjobless\b", r"\bISM\b", r"\bPMI\b", r"\bhousing starts\b",
    r"\bconsumer confidence\b",
]
MACRO_RE = re.compile("|".join(KEYWORD_PATTERNS), re.IGNORECASE)

CATEGORIES = {
    "CPI": [r"\bCPI\b", r"\binflation\b"],
    "Fed": [r"\bFed\b", r"\bFOMC\b", r"\binterest rate", r"\brate cut", r"\brate hike"],
    "GDP": [r"\bGDP\b"],
    "Labor": [r"\bnonfarm\b", r"\bpayrolls?\b", r"\bunemployment\b", r"\bjobless\b"],
    "Other": [r"\bretail sales\b", r"\bPCE\b", r"\bPPI\b", r"\bISM\b", r"\bPMI\b",
              r"\bhousing starts\b", r"\bconsumer confidence\b"],
}

# Exclude non-macro noise (word boundaries to avoid "iNFLation" matching NFL etc.)
EXCLUDE_RE = re.compile(
    r"Communist Party of India"
    r"|Ismaily|Ismaïla|Ismail[^a]|Rashid Ismailov"
    r"|Premier League|La Liga|Serie A|Bundesliga|Ligue 1"
    r"|\bUEFA\b|\bFIFA\b|Champions League|Europa League"
    r"|\bcricket\b|\brugby\b|\bNFL\b|\bNBA\b|\bMLB\b|\bNHL\b|\bMLS\b"
    r"|Goalscorer|Goals in|Cards in|Assists in"
    r"|O/U \d|Both Teams|Match Result|Correct Score"
    r"|\bcommodity\b|\bbitcoin\b|\bethereum\b|\bcrypto\b|\bBTC\b|\bETH\b"
    # Non-US countries (keep only US macro)
    r"|\bJapan\b|\bChina\b|\bIndia\b|South Korea|\bMexico\b|\bBrazil\b|\bCanada\b|\bArgentina\b"
    r"|\bAustralia\b|\bGermany\b|\bFrance\b|\bTurkey\b|\bUK\b|\bEuro(?:pe|zone)\b"
    r"|Bank of Japan|Bank of England|\bECB\b|\bBOJ\b|\bBOE\b",
    re.IGNORECASE,
)

OUT_DIR = "research/phase_c4_macro"


def fetch_all_markets():
    markets, offset = [], 0
    while True:
        r = requests.get(API, params={"active": "true", "closed": "false", "limit": 100, "offset": offset})
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        markets.extend(batch)
        offset += len(batch)
        if offset % 5000 == 0:
            print(f"  fetched {len(markets)} markets...")
        time.sleep(0.1)
    print(f"  fetched {len(markets)} markets total")
    return markets


def matches_macro(question: str) -> bool:
    if EXCLUDE_RE.search(question):
        return False
    return bool(MACRO_RE.search(question))


def classify(question: str) -> str:
    for cat, patterns in CATEGORIES.items():
        if any(re.search(p, question, re.IGNORECASE) for p in patterns):
            return cat
    return "Other"


def extract_row(m: dict) -> dict:
    outcomes = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])
    prices = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
    outcome_str = " / ".join(f"{o}={p}" for o, p in zip(outcomes, prices))
    return {
        "question": m.get("question", ""),
        "slug": m.get("slug", ""),
        "url": f"https://polymarket.com/event/{m.get('slug', '')}",
        "volume24hr": float(m.get("volume24hr", 0) or 0),
        "volumeTotal": float(m.get("volume", 0) or 0),
        "liquidity": float(m.get("liquidity", 0) or 0),
        "endDate": m.get("endDate", ""),
        "category": classify(m.get("question", "")),
        "outcomes": outcome_str,
    }


def write_markdown(df: pd.DataFrame, path: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Polymarket — Marchés macro US actifs\n", f"*Scan du {now}*\n"]

    for cat in ["CPI", "Fed", "GDP", "Labor", "Other"]:
        sub = df[df["category"] == cat].reset_index(drop=True)
        lines.append(f"\n## {cat} ({len(sub)} marchés)\n")
        if sub.empty:
            lines.append("Aucun marché actif.\n")
            continue
        lines.append("| Question | Vol 24h | Vol Total | Liquidity | End Date | Outcomes |")
        lines.append("|----------|---------|-----------|-----------|----------|----------|")
        for _, r in sub.iterrows():
            end = r["endDate"][:10] if r["endDate"] else "—"
            lines.append(f"| {r['question'][:80]} | ${r['volume24hr']:,.0f} | ${r['volumeTotal']:,.0f} | ${r['liquidity']:,.0f} | {end} | {r['outcomes'][:60]} |")

    # Observations terrain
    lines.append("\n## Observations terrain\n")
    lines.append(f"- **Total marchés macro actifs** : {len(df)}")
    for cat in ["CPI", "Fed", "GDP", "Labor", "Other"]:
        n = len(df[df["category"] == cat])
        lines.append(f"- **{cat}** : {n} marchés")

    liq = df["liquidity"]
    lines.append(f"\n### Distribution liquidité")
    lines.append(f"- Médiane : ${liq.median():,.0f}")
    lines.append(f"- Max : ${liq.max():,.0f}")
    lines.append(f"- Min : ${liq.min():,.0f}")

    top5 = df.nlargest(5, "liquidity")
    lines.append(f"\n### Top 5 les plus liquides")
    for _, r in top5.iterrows():
        lines.append(f"- {r['question'][:80]} — ${r['liquidity']:,.0f}")

    bot3 = df.nsmallest(3, "liquidity")
    lines.append(f"\n### Bottom 3 les moins liquides")
    for _, r in bot3.iterrows():
        lines.append(f"- {r['question'][:80]} — ${r['liquidity']:,.0f}")

    # Only show future end dates
    future = df[(df["endDate"] != "") & (df["endDate"] >= today)].sort_values("endDate").head(10)
    if not future.empty:
        lines.append(f"\n### Prochaines résolutions")
        for _, r in future.iterrows():
            lines.append(f"- {r['endDate'][:10]} — {r['question'][:80]}")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    print("Fetching all active markets from Gamma API...")
    raw = fetch_all_markets()

    rows = [extract_row(m) for m in raw if matches_macro(m.get("question", ""))]
    df = pd.DataFrame(rows).sort_values("volume24hr", ascending=False).reset_index(drop=True)
    print(f"Macro matches: {len(df)}")

    csv_path = f"{OUT_DIR}/polymarket_macro_markets.csv"
    md_path = f"{OUT_DIR}/polymarket_macro_markets.md"
    df.to_csv(csv_path, index=False)
    write_markdown(df, md_path)
    print(f"\nOutputs:\n  {csv_path}\n  {md_path}")
    print(f"\nTop 15 by 24h volume:")
    print(df[["question", "volume24hr", "liquidity", "category"]].head(15).to_string(index=False))
    print(f"\nBy category:")
    print(df.groupby("category").agg(count=("question", "size"), liq_median=("liquidity", "median"),
                                      liq_total=("liquidity", "sum"), vol24h_total=("volume24hr", "sum")).to_string())
