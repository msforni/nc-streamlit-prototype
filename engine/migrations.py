"""Supabase schema verification and canonical data seeding.

Pattern (intentionally conservative for a small-team internal tool):
- DDL is applied OUT-OF-BAND once via Supabase SQL editor (paste of
  migrations/001_initial.sql). The migration is idempotent.
- This module verifies on app startup that expected tables are reachable,
  and seeds the LC v1.0 canonical register if not already present.
- Python only does CRUD via supabase-py. No raw SQL execution.

If you want fully-automated DDL, add `[supabase.postgres_url]` to Streamlit
secrets and extend this module with a psycopg2 branch that runs SQL files in
order. Out of scope for T106 v1.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Tuple

from supabase import Client

REPO_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = REPO_ROOT / "migrations"
LC_FIXTURE = REPO_ROOT / "data" / "lc_v1_segments.csv"

EXPECTED_TABLES = [
    "migrations_applied",
    "segment_registers",
    "parameter_overrides",
    "runs",
    "pdf_outputs",
    "audit_log",
]


def verify_schema(client: Client) -> Tuple[bool, str]:
    """Return (ok, message). Verifies expected tables are reachable.

    A table is "reachable" if a `select limit 1` succeeds. This catches the
    common case where DDL hasn't been applied yet — the table genuinely
    doesn't exist and supabase-py raises.
    """
    missing = []
    for table in EXPECTED_TABLES:
        try:
            client.table(table).select("*").limit(1).execute()
        except Exception:
            missing.append(table)
    if missing:
        return False, (
            f"Missing tables: {missing}. "
            f"Apply migrations/001_initial.sql in the Supabase SQL editor."
        )
    return True, "All expected tables present."


def seed_lc_canonical(client: Client) -> bool:
    """Insert the LC v1.0 canonical register if not already present.

    Returns True if a row was inserted, False if it already existed or the
    fixture is missing.
    """
    if not LC_FIXTURE.exists():
        return False

    existing = (
        client.table("segment_registers")
        .select("id")
        .eq("name", "LC v1.0 canonical")
        .limit(1)
        .execute()
    )
    if existing.data:
        return False

    csv_content = LC_FIXTURE.read_text()
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    total_kwp = sum(float(row.get("kwp_dc", 0) or 0) for row in rows)

    client.table("segment_registers").insert({
        "name": "LC v1.0 canonical",
        "estate": "Laem Chabang",
        "description": "NC-FM-LC-001 v1.0 ground-truth segment register",
        "segment_count": len(rows),
        "total_envelope_kwp": total_kwp,
        "csv_content": csv_content,
        "is_canonical": True,
        "source_reference": "LC_Package v1.0",
    }).execute()
    return True


def apply_pending(client: Client) -> Tuple[bool, str]:
    """Run on app startup. Verifies schema and seeds canonical data.

    Returns (ok, status_message). If not ok, the app should still load but
    warn the user that persistence features are disabled until migrations
    are applied.
    """
    ok, msg = verify_schema(client)
    if not ok:
        return False, msg

    try:
        seeded = seed_lc_canonical(client)
        suffix = "LC canonical seeded." if seeded else "LC canonical already present."
        return True, f"Schema verified. {suffix}"
    except Exception as e:
        return False, f"Schema OK but seed failed: {type(e).__name__}: {e}"
