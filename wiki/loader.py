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


def append_to_markdown(file_path: Path, new_data: list[dict]):
    """
    Intelligently appends new topics under categories in a Markdown file.
    Structure: ## Category -> ### Topic -> - Rule
    """
    if not file_path.exists():
        file_path.write_text("")

    content = file_path.read_text()
    lines = content.splitlines()

    for item in new_data:
        category = item.get("category", "General")
        topic = item.get("topic", "Miscellaneous")
        rules = item.get("rules", [])
        
        if not rules: continue

        # 1. Find Category
        category_pattern = rf"^##\s+{re.escape(category)}\s*$"
        cat_index = -1
        for i, line in enumerate(lines):
            if re.match(category_pattern, line, re.IGNORECASE):
                cat_index = i
                break
        
        if cat_index == -1:
            # Create Category at the end
            if lines and lines[-1].strip(): lines.append("")
            lines.append(f"## {category}")
            cat_index = len(lines) - 1

        # 2. Find Topic under Category
        # Search until next ## or end of file
        topic_pattern = rf"^###\s+{re.escape(topic)}\s*$"
        topic_index = -1
        search_limit = len(lines)
        for i in range(cat_index + 1, len(lines)):
            if lines[i].startswith("## "):
                search_limit = i
                break
            if re.match(topic_pattern, lines[i], re.IGNORECASE):
                topic_index = i
                break
        
        formatted_rules = [f"- {r}" for r in rules]

        if topic_index != -1:
            # Topic exists, append rules to it
            insert_pos = topic_index + 1
            while insert_pos < search_limit and lines[insert_pos].strip() and not lines[insert_pos].startswith("#"):
                insert_pos += 1
            
            existing_text = "\n".join(lines).lower()
            to_insert = [r for r in formatted_rules if r.lower() not in existing_text]
            if to_insert:
                lines[insert_pos:insert_pos] = to_insert
        else:
            # Topic doesn't exist, create it under category
            insert_pos = search_limit
            # Back up past trailing whitespace
            while insert_pos > cat_index + 1 and not lines[insert_pos-1].strip():
                insert_pos -= 1
            
            if insert_pos < len(lines) and not lines[insert_pos].strip():
                 pass # already have a newline
            else:
                 lines.insert(insert_pos, "")
                 insert_pos += 1
            
            lines.insert(insert_pos, f"### {topic}")
            lines[insert_pos+1:insert_pos+1] = formatted_rules

    file_path.write_text("\n".join(lines).strip() + "\n")


def update_wiki(doctor_id: str, protocols: list, preferences: list):
    """
    Updates the doctor's wiki files with new protocols and preferences.
    Now expects lists of dicts with {category, topic, rules}.
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
    
    # Handle new list-based format from WikiSubstrateAgent
    for item in updates.get("new_protocols", []):
        pending.append({
            "type": "protocol",
            "category": item.get("category", "General"),
            "header": item.get("topic", "Miscellaneous"),
            "content": "\n".join(item.get("rules", []))
        })
            
    for item in updates.get("new_preferences", []):
        pending.append({
            "type": "preference",
            "category": item.get("category", "General"),
            "header": item.get("topic", "Miscellaneous"),
            "content": "\n".join(item.get("rules", []))
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
