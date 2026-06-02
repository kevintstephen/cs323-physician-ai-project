import os
import re
import json
import hashlib
from datetime import date
from pathlib import Path


WIKI_DIR = Path(__file__).parent

# Attribute used to record when a rule was first added to the wiki, so the physician can
# see how old a reference is when revisiting it later.
ADDED_KEY = "Added"


def today_str() -> str:
    """Today's date as YYYY-MM-DD for stamping new wiki entries."""
    return date.today().isoformat()


def generate_id(category: str, topic: str, rule_text: str) -> str:
    """Generates a stable, deterministic ID for a wiki rule."""
    # Note: only category/topic/rule_text feed the ID — attributes like the Added date do
    # not, so dating an entry never changes its citation ID.
    text = f"{category}:{topic}:{rule_text}".strip().lower()
    return hashlib.md5(text.encode()).hexdigest()[:6]


def parse_wiki_sections(content: str) -> list[dict]:
    """
    Parses markdown into a list of {category, topic, rules}.
    Rules are returned as dicts: {"text": str, "attributes": dict}.
    """
    sections = []
    current_cat = "General"
    
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            current_cat = line[3:].strip()
            i += 1
        elif line.startswith("### "):
            topic = line[4:].strip()
            rules = []
            i += 1
            while i < len(lines) and not lines[i].startswith("#"):
                clean_line = lines[i].strip()
                if clean_line.startswith("- "):
                    # Main rule text
                    rule_text = clean_line[2:].strip()
                    # Strip existing ID if present to get core rule text
                    clean_rule_text = re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", rule_text)
                    
                    rule_obj = {"text": clean_rule_text, "attributes": {}}
                    
                    # Look for sub-bullets (nested attributes)
                    j = i + 1
                    while j < len(lines) and lines[j].startswith("  - "):
                        sub_line = lines[j].strip()[2:].strip() # Remove "- "
                        if ":" in sub_line:
                            key, val = sub_line.split(":", 1)
                            rule_obj["attributes"][key.strip()] = val.strip()
                        j += 1
                    
                    rules.append(rule_obj)
                    i = j
                else:
                    i += 1
            sections.append({
                "category": current_cat,
                "topic": topic,
                "rules": rules
            })
        else:
            i += 1
    return sections


def load_wiki(doctor_id: str = "default") -> str:
    """
    Loads all markdown files from wiki/<doctor_id>/ and returns them
    as a single concatenated string. Rules are prefixed with [ID: xxxxxx]
    to allow agents to cite them precisely.
    """
    doctor_dir = WIKI_DIR / doctor_id
    if not doctor_dir.exists():
        return ""

    pages = []
    for md_file in sorted(doctor_dir.glob("*.md")):
        content = md_file.read_text().strip()
        if not content:
            continue
        
        sections = parse_wiki_sections(content)
        formatted_sections = []
        for s in sections:
            rules_with_ids = []
            for r in s['rules']:
                rule_id = generate_id(s['category'], s['topic'], r['text'])
                rules_with_ids.append(f"- [ID: {rule_id}] {r['text']}")
                for key, val in r['attributes'].items():
                    rules_with_ids.append(f"  - {key}: {val}")
            
            section_text = f"## {s['category']}\n### {s['topic']}\n" + "\n".join(rules_with_ids)
            formatted_sections.append(section_text)
            
        pages.append(f"### File: {md_file.stem.replace('_', ' ').title()}\n\n" + "\n\n".join(formatted_sections))

    return "\n\n---\n\n".join(pages)


def get_wiki_insight(doctor_id: str, insight_id: str) -> dict:
    """Retrieves the specific rule content by its ID (case-insensitive)."""
    doctor_dir = WIKI_DIR / doctor_id
    if not doctor_dir.exists():
        return {}

    insight_id = insight_id.lower()
    for md_file in doctor_dir.glob("*.md"):
        content = md_file.read_text()
        sections = parse_wiki_sections(content)
        for s in sections:
            for r in s['rules']:
                if generate_id(s['category'], s['topic'], r['text']).lower() == insight_id:
                    return {
                        "category": s['category'],
                        "topic": s['topic'],
                        "rule": r['text'],
                        "attributes": r['attributes']
                    }
    return {}


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
        
        formatted_rules = []
        for r in rules:
            if isinstance(r, dict):
                # Stamp the date this rule is added to the wiki (preserve any existing one).
                attrs = dict(r.get('attributes', {}))
                attrs.setdefault(ADDED_KEY, today_str())
                formatted_rules.append(f"- {r['text']}")
                for key, val in attrs.items():
                    formatted_rules.append(f"  - {key}: {val}")
            else:
                formatted_rules.append(f"- {r}")

        if topic_index != -1:
            # Topic exists, append rules to it
            insert_pos = topic_index + 1
            while insert_pos < search_limit and lines[insert_pos].strip() and not lines[insert_pos].startswith("#"):
                insert_pos += 1
            
            existing_text = "\n".join(lines).lower()
            to_insert = []
            # Only insert the main rule if it doesn't exist. 
            # This is a bit simplistic for nested attributes, but let's start here.
            current_rule_lines = []
            for r_line in formatted_rules:
                if r_line.startswith("- "):
                    if current_rule_lines:
                        # Check if existing_text contains the main rule
                        if current_rule_lines[0].lower() not in existing_text:
                            to_insert.extend(current_rule_lines)
                    current_rule_lines = [r_line]
                else:
                    current_rule_lines.append(r_line)
            
            if current_rule_lines and current_rule_lines[0].lower() not in existing_text:
                to_insert.extend(current_rule_lines)

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
        data = json.loads(path.read_text())
        
        # Format rules to content if missing (legacy support for app.py)
        for item in data:
            if "content" not in item and "rules" in item:
                lines = []
                for r in item["rules"]:
                    if isinstance(r, dict):
                        lines.append(f"- {r.get('text', '')}")
                        for k, v in r.get('attributes', {}).items():
                            lines.append(f"  - {k}: {v}")
                    else:
                        lines.append(f"- {r}")
                item["content"] = "\n".join(lines)
        return data
    except json.JSONDecodeError:
        return []


def add_pending_updates(doctor_id: str, updates: dict):
    """Adds new updates to the staging queue."""
    pending = get_pending_updates(doctor_id)
    
    def format_rules_to_content(rules: list) -> str:
        lines = []
        for r in rules:
            if isinstance(r, dict):
                lines.append(f"- {r.get('text', '')}")
                for k, v in r.get('attributes', {}).items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"- {r}")
        return "\n".join(lines)

    # Handle new list-based format from WikiSubstrateAgent
    for item in updates.get("new_protocols", []):
        rules = item.get("rules", [])
        pending.append({
            "type": "protocol",
            "category": item.get("category", "General"),
            "header": item.get("topic", "Miscellaneous"),
            "content": format_rules_to_content(rules),
            "rules": rules
        })
            
    for item in updates.get("new_preferences", []):
        rules = item.get("rules", [])
        pending.append({
            "type": "preference",
            "category": item.get("category", "General"),
            "header": item.get("topic", "Miscellaneous"),
            "content": format_rules_to_content(rules),
            "rules": rules
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
