"""Populate US state water/rivers/mountain facts with Gemini extraction.

Reads each state markdown article, extracts the lead plus Geography section, asks
Gemini for strict JSON, then replaces rows in:
- us_state_water_access
- us_state_major_rivers
- us_state_mountain_ranges
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT_DIR / "data" / "us_state_facts.sqlite"
DEFAULT_CSV = ROOT_DIR / "data" / "us_states.csv"
DEFAULT_MODEL = "gemini-2.5-flash-lite"

WATER_ALIASES = {
    "Atlantic": "Atlantic Ocean",
    "Pacific": "Pacific Ocean",
    "Gulf": "Gulf of Mexico",
    "Gulf Coast": "Gulf of Mexico",
}

ALLOWED_WATER_BODIES = {
    "Atlantic Ocean",
    "Pacific Ocean",
    "Gulf of Mexico",
    "Arctic Ocean",
    "Bering Sea",
    "Gulf of Alaska",
    "Lake Superior",
    "Lake Michigan",
    "Lake Huron",
    "Lake Erie",
    "Lake Ontario",
}

RIVER_ALIASES = {
    "Mississippi River": "Mississippi",
    "Missouri River": "Missouri",
    "Colorado River": "Colorado",
    "Columbia River": "Columbia",
    "Ohio River": "Ohio",
    "Rio Grande River": "Rio Grande",
}

EXCLUDED_RIVERS = {
    "Table Rock Lake",
}

MOUNTAIN_ALIASES = {
    "Rockies": "Rocky Mountains",
    "Appalachians": "Appalachian Mountains",
    "Cascades": "Cascade Range",
    "coastal mountain ranges": "Coast Ranges",
}

EXCLUDED_MOUNTAINS = {
    "Allegheny Plateau",
    "Appalachian Trail",
    "Atlantic Coastal Plain",
    "Cumberland Plateau",
    "Driftless Area",
    "Erie Plain",
    "volcanic islands",
    "Sierra Madre Occidental",
}

# Some local Wikipedia Geography sections are sparse or mention features only in
# prose/infoboxes, so Gemini can miss obvious state-level quiz facts. Keep these
# as explicit deterministic additions rather than relying on re-prompting.
MANUAL_FACT_ADDITIONS = {
    "Hawaii": {
        "major_rivers": {"Wailuku", "Wailua"},
        "mountain_ranges": {"Koolau Range", "Waianae Range"},
    },
    "Maine": {
        "major_rivers": {"Androscoggin", "Kennebec", "Penobscot", "Saint John"},
        "mountain_ranges": {"Appalachian Mountains", "Longfellow Mountains"},
    },
    "Texas": {
        "mountain_ranges": {"Chisos Mountains", "Davis Mountains", "Franklin Mountains", "Guadalupe Mountains"},
    },
}


def load_dotenv_if_present() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_states(csv_path: Path) -> list[tuple[str, Path]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return [(row["name"], ROOT_DIR / row["md_file"].replace("\\", "/")) for row in csv.DictReader(handle)]


def extract_section(markdown: str, heading_regex: str) -> str:
    match = re.search(heading_regex, markdown, re.M | re.I)
    if not match:
        return ""
    level = len(match.group(1))
    start = match.end()
    next_heading = re.search(r"^#{1," + str(level) + r"}\s+", markdown[start:], re.M)
    return markdown[start : start + next_heading.start()] if next_heading else markdown[start:]


def extract_context(markdown: str) -> str:
    first_h2 = re.search(r"^##\s+", markdown, re.M)
    lead = markdown[: first_h2.start()] if first_h2 else markdown[:4000]
    geography = extract_section(markdown, r"^(#{2,3})\s+Geography\b.*$")
    return f"Lead:\n{lead[:5000]}\n\nGeography:\n{geography[:12000]}"


def clean_list(
    values,
    aliases: dict[str, str] | None = None,
    allowed: set[str] | None = None,
    excluded: set[str] | None = None,
) -> list[str]:
    aliases = aliases or {}
    excluded = excluded or set()
    result = []
    seen = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        value = re.sub(r"\s+", " ", value).strip().strip(".,;:")
        value = re.sub(r"\bRivers?$", "", value).strip()
        value = aliases.get(value, value)
        if allowed is not None and value not in allowed:
            continue
        if value in excluded:
            continue
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return sorted(result)


def add_manual_facts(state_name: str, key: str, values: list[str]) -> list[str]:
    additions = MANUAL_FACT_ADDITIONS.get(state_name, {}).get(key, set())
    if not additions:
        return values
    return sorted({*values, *additions})


def gemini_extract(model: str, api_key: str, state_name: str, context: str) -> dict:
    prompt = f"""
You extract structured geography facts for a US state guessing game.
Use ONLY the provided Wikipedia lead and Geography section. Do not use outside knowledge.

State: {state_name}

Return STRICT JSON only with this schema:
{{
  "water_access": ["main direct oceans/gulfs/Great Lakes only"],
  "major_rivers": ["major river names that flow through or form borders of the state"],
  "mountain_ranges": ["major mountain ranges located in the state"],
  "notes": "short ambiguity note or null"
}}

Rules:
- water_access: include only Atlantic Ocean, Pacific Ocean, Gulf of Mexico, Arctic Ocean,
  Bering Sea, Gulf of Alaska, or specific Great Lakes if directly indicated.
- Do not include bays, sounds, straits, channels, small lakes, ports, or inferred parent waters.
- major_rivers: use short English river names without the word River when possible.
- mountain_ranges: use broad range names, not individual peaks.
- If none are found, use an empty array.

Context:
---
{context}
---
""".strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 768, "responseMimeType": "application/json"},
    }
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
    return json.loads(raw)


def replace_rows(conn: sqlite3.Connection, state_id: int, waters: list[str], rivers: list[str], mountains: list[str]) -> None:
    conn.execute("DELETE FROM us_state_water_access WHERE state_id=?", (state_id,))
    conn.execute("DELETE FROM us_state_major_rivers WHERE state_id=?", (state_id,))
    conn.execute("DELETE FROM us_state_mountain_ranges WHERE state_id=?", (state_id,))
    conn.executemany("INSERT OR IGNORE INTO us_state_water_access VALUES (?, ?)", [(state_id, item) for item in waters])
    conn.executemany("INSERT OR IGNORE INTO us_state_major_rivers VALUES (?, ?)", [(state_id, item) for item in rivers])
    conn.executemany("INSERT OR IGNORE INTO us_state_mountain_ranges VALUES (?, ?)", [(state_id, item) for item in mountains])


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate US state geography facts with Gemini.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--countries-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--model", default=os.getenv("LOCAL_GEOGRAPHY_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--state", action="append", help="State name to process; can be repeated.")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured")

    states = load_states(args.countries_csv)
    if args.state:
        wanted = {name.casefold() for name in args.state}
        states = [row for row in states if row[0].casefold() in wanted]
    elif args.sample:
        wanted = {"California", "Texas", "New York", "Alaska", "Hawaii", "Colorado", "Michigan"}
        states = [row for row in states if row[0] in wanted]

    with sqlite3.connect(args.db) as conn:
        for index, (name, md_path) in enumerate(states, start=1):
            context = extract_context(md_path.read_text(encoding="utf-8"))
            try:
                extracted = gemini_extract(args.model, api_key, name, context)
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Gemini HTTP error for {name}: {exc.code} {body[:500]}") from exc
            waters = clean_list(extracted.get("water_access"), WATER_ALIASES, ALLOWED_WATER_BODIES)
            rivers = clean_list(extracted.get("major_rivers"), RIVER_ALIASES, excluded=EXCLUDED_RIVERS)
            mountains = clean_list(extracted.get("mountain_ranges"), MOUNTAIN_ALIASES, excluded=EXCLUDED_MOUNTAINS)
            waters = add_manual_facts(name, "water_access", waters)
            rivers = add_manual_facts(name, "major_rivers", rivers)
            mountains = add_manual_facts(name, "mountain_ranges", mountains)
            print(f"{name}: water={waters}; rivers={rivers}; mountains={mountains}")
            if not args.dry_run:
                state_id = conn.execute("SELECT id FROM us_states WHERE name=?", (name,)).fetchone()[0]
                replace_rows(conn, state_id, waters, rivers, mountains)
                conn.commit()
            if args.sleep and index < len(states):
                time.sleep(args.sleep)


if __name__ == "__main__":
    main()
