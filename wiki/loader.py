import os
from pathlib import Path


WIKI_DIR = Path(__file__).parent


def load_wiki(doctor_id: str = "default") -> str:
    """
    Loads all markdown files from wiki/<doctor_id>/ and returns them
    as a single concatenated string. This string is injected into every
    agent call so agents are grounded in this doctor's accumulated reasoning.
    """
    doctor_dir = WIKI_DIR / doctor_id
    if not doctor_dir.exists():
        return ""

    pages = []
    for md_file in sorted(doctor_dir.glob("*.md")):
        content = md_file.read_text().strip()
        if content:
            pages.append(f"### {md_file.stem.replace('_', ' ').title()}\n\n{content}")

    return "\n\n---\n\n".join(pages)
