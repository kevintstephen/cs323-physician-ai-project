"""
Guideline API — allows physicians to search clinical guidelines and
attach their personal notes and interpretations to them in the wiki.
"""

import re
from pathlib import Path
from wiki.loader import parse_wiki_sections, get_wiki_file_content, save_wiki_file_content, append_to_markdown, generate_id, today_str, ADDED_KEY
from tools.pubmed import PubMedClient


def search_guidelines(query: str, doctor_id: str = "default") -> list[dict]:
    """
    Searches the guidelines.md file for a query string.
    Returns a list of matching rules/guidelines with their attributes.
    """
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    if not content:
        return []

    sections = parse_wiki_sections(content)
    results = []
    query = query.lower()

    for s in sections:
        for r in s['rules']:
            if query in r['text'].lower() or any(query in val.lower() for val in r['attributes'].values()):
                results.append({
                    "category": s['category'],
                    "topic": s['topic'],
                    "text": r['text'],
                    "attributes": r['attributes']
                })
    return results


def add_guideline_note(topic: str, guideline_text: str, note_type: str, note_content: str, doctor_id: str = "default"):
    """
    Adds or updates a note (e.g., 'Physician Notes', 'Rationale') to a specific 
    guideline in guidelines.md.
    """
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    sections = parse_wiki_sections(content)
    
    updated = False
    # Clean up search text
    guideline_text_clean = re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", guideline_text).lower().strip()
    
    for s in sections:
        if s['topic'].lower() == topic.lower():
            for r in s['rules']:
                # Clean up rule text
                r_text_clean = re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", r['text']).lower().strip()
                if r_text_clean == guideline_text_clean:
                    r['attributes'][note_type] = note_content
                    updated = True
                    break
    
    if updated:
        # Reconstruct the markdown content
        new_content = "# Clinical Guidelines\n\n"
        current_cat = ""
        for s in sections:
            if s['category'] != current_cat:
                new_content += f"## {s['category']}\n"
                current_cat = s['category']
            new_content += f"### {s['topic']}\n"
            for r in s['rules']:
                # Preserve the original rule text which might have an ID
                new_content += f"- {r['text']}\n"
                for k, v in r['attributes'].items():
                    new_content += f"  - {k}: {v}\n"
            new_content += "\n"
        
        save_wiki_file_content(doctor_id, "guidelines.md", new_content)


def save_guideline(category: str, topic: str, text: str, attributes: dict, doctor_id: str = "default"):
    """
    Saves a new guideline to the guidelines.md file.
    """
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    sections = parse_wiki_sections(content)

    # The wiki markdown stores each field as a single "  - Key: value" line, so any newline
    # in a pasted abstract/notes value would split the entry and corrupt parsing. Collapse
    # internal whitespace to keep every value on one line.
    def _flatten(v):
        return " ".join(str(v).split())
    text = _flatten(text)
    attributes = {k: _flatten(v) for k, v in attributes.items()}

    # New guidelines are stamped with the date they enter the wiki; updates to an existing
    # guideline keep its original Added date.
    new_attributes = dict(attributes)
    new_attributes.setdefault(ADDED_KEY, today_str())

    # 1. Check if it already exists
    text_clean = re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", text).lower().strip()
    for s in sections:
        if s['category'].lower() == category.lower() and s['topic'].lower() == topic.lower():
            for r in s['rules']:
                if re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", r['text']).lower().strip() == text_clean:
                    # Update existing attributes (do not reset the original Added date)
                    r['attributes'].update(attributes)
                    break
            else:
                # Add to existing topic
                s['rules'].append({"text": text, "attributes": new_attributes})
            break
    else:
        # Add new section
        sections.append({
            "category": category,
            "topic": topic,
            "rules": [{"text": text, "attributes": new_attributes}]
        })

    # 2. Reconstruct markdown
    new_content = "# Clinical Guidelines\n\n"
    current_cat = ""
    for s in sections:
        if s['category'] != current_cat:
            new_content += f"## {s['category']}\n"
            current_cat = s['category']
        new_content += f"### {s['topic']}\n"
        for r in s['rules']:
            # Ensure it has an ID
            if not re.match(r"^\[ID:\s*[^\]]+\]", r['text']):
                rule_id = generate_id(s['category'], s['topic'], r['text'])
                final_text = f"[ID: {rule_id}] {r['text']}"
            else:
                final_text = r['text']
            
            new_content += f"- {final_text}\n"
            for k, v in r['attributes'].items():
                new_content += f"  - {k}: {v}\n"
        new_content += "\n"
    
    save_wiki_file_content(doctor_id, "guidelines.md", new_content)


def delete_guideline(category: str, topic: str, text: str, doctor_id: str = "default"):
    """
    Removes a single guideline (matched by category, topic, and ID-stripped text)
    from guidelines.md and rewrites the file.
    """
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    sections = parse_wiki_sections(content)

    text_clean = re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", text).lower().strip()
    for s in sections:
        if s['category'].lower() == category.lower() and s['topic'].lower() == topic.lower():
            s['rules'] = [
                r for r in s['rules']
                if re.sub(r"^\[ID:\s*[^\]]+\]\s*", "", r['text']).lower().strip() != text_clean
            ]

    # Drop now-empty topics, then reconstruct markdown.
    sections = [s for s in sections if s['rules']]
    new_content = "# Clinical Guidelines\n\n"
    current_cat = ""
    for s in sections:
        if s['category'] != current_cat:
            new_content += f"## {s['category']}\n"
            current_cat = s['category']
        new_content += f"### {s['topic']}\n"
        for r in s['rules']:
            new_content += f"- {r['text']}\n"
            for k, v in r['attributes'].items():
                new_content += f"  - {k}: {v}\n"
        new_content += "\n"

    save_wiki_file_content(doctor_id, "guidelines.md", new_content)


def search_pubmed(query: str) -> list[dict]:
    """Wraps PubMedClient for the API."""
    client = PubMedClient()
    return client.search(query)
