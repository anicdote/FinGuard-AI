"""Canonical downloadable STR artifact derived from existing case data."""

from datetime import datetime, timezone


def render_str(case: dict) -> str:
    """Return the existing Agent 5 narrative without changing AI generation."""
    narrative = str(case.get("str_narrative") or "").strip()
    if not narrative:
        raise ValueError("No STR narrative is available for this case")
    # Match the UI's removal of display-only approval placeholders.
    lines = [line for line in narrative.splitlines()
             if not line.upper().startswith("APPROVED BY:")
             and "BIOMETRIC VERIFICATION: PENDING HARDWARE INTEGRATION" not in line.upper()]
    return "\n".join(lines).strip() + "\n"


def str_filename(case_id: str) -> str:
    return f"STR_{case_id}_{datetime.now(timezone.utc).date().isoformat()}.txt"
