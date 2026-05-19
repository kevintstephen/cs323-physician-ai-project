import os
import re
import json
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


def append_to_markdown(file_path: Path, new_data: dict[str, list[str]]):
    """
    Intelligently appends new bullet points to a Markdown file under matching ## Headers.
    If a header doesn't exist, it appends it to the end.
    """
    if not file_path.exists():
        file_path.write_text("")

    content = file_path.read_text()
    lines = content.splitlines()

    for header, items in new_data.items():
        if not items:
            continue

        header_pattern = rf"^##\s+{re.escape(header)}\s*$"
        header_index = -1
        for i, line in enumerate(lines):
            if re.match(header_pattern, line, re.IGNORECASE):
                header_index = i
                break

        formatted_items = [f"- {item}" for item in items]

        if header_index != -1:
            # Insert items after the header, but before the next header or end of file
            insert_pos = header_index + 1
            # Skip any existing text/bullets immediately after the header
            while insert_pos < len(lines) and lines[insert_pos].strip() and not lines[insert_pos].startswith("##"):
                insert_pos += 1
            
            # Check for duplicates before inserting
            existing_items = set(content.lower())
            to_insert = [item for item in formatted_items if item.lower() not in existing_items]
            
            if to_insert:
                lines[insert_pos:insert_pos] = to_insert
                if insert_pos == len(lines) - len(to_insert): # If we added at the very end
                    lines.append("") # Add a trailing newline
        else:
            # Append new header and items to the end
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"## {header}")
            lines.extend(formatted_items)
            lines.append("")

    file_path.write_text("\n".join(lines).strip() + "\n")


def update_wiki(doctor_id: str, protocols: dict, preferences: dict):
    """
    Updates the doctor's wiki files with new protocols and preferences.
    """
    doctor_dir = WIKI_DIR / doctor_id
    doctor_dir.mkdir(parents=True, exist_ok=True)

    if protocols:
        append_to_markdown(doctor_dir / "clinical_protocols.md", protocols)
    
    if preferences:
        append_to_markdown(doctor_dir / "preferences.md", preferences)


def get_pending_updates(doctor_id: str) -> list[dict]:
    """Loads the staging queue of pending wiki updates."""
    path = WIKI_DIR / doctor_id / "pending_updates.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def add_pending_updates(doctor_id: str, updates: dict):
    """Adds new updates to the staging queue."""
    pending = get_pending_updates(doctor_id)
    
    # protocols
    for cond, items in updates.get("new_protocols", {}).items():
        for item in items:
            pending.append({
                "type": "protocol",
                "header": cond,
                "content": item
            })
            
    # preferences
    for cat, items in updates.get("new_preferences", {}).items():
        for item in items:
            pending.append({
                "type": "preference",
                "header": cat,
                "content": item
            })

    path = WIKI_DIR / doctor_id / "pending_updates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, indent=2))


def remove_pending_update(doctor_id: str, index: int):
    """Removes an item from the staging queue after approval or rejection."""
    pending = get_pending_updates(doctor_id)
    if 0 <= index < len(pending):
        pending.pop(index)
        path = WIKI_DIR / doctor_id / "pending_updates.json"
        path.write_text(json.dumps(pending, indent=2))


def get_wiki_file_content(doctor_id: str, filename: str) -> str:
    """Reads raw content of a wiki file."""
    path = WIKI_DIR / doctor_id / filename
    if not path.exists():
        return ""
    return path.read_text()


def save_wiki_file_content(doctor_id: str, filename: str, content: str):
    """Saves raw content to a wiki file."""
    path = WIKI_DIR / doctor_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n")
