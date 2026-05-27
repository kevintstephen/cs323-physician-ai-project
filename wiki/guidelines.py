"""
Guideline API — allows physicians to search clinical guidelines and
attach their personal notes and interpretations to them in the wiki.
"""

from pathlib import Path
from wiki.loader import parse_wiki_sections, get_wiki_file_content, save_wiki_file_content, append_to_markdown


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


import re

def add_guideline_note(topic: str, guideline_text: str, note_type: str, note_content: str, doctor_id: str = "default"):
    """
    Adds or updates a note (e.g., 'Physician Notes', 'Rationale') to a specific 
    guideline in guidelines.md.
    """
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    sections = parse_wiki_sections(content)
    
    updated = False
    # Clean up search text
    guideline_text_clean = re.sub(r"^\[ID:\s*[a-f0-9]{6}\]\s*", "", guideline_text).lower().strip()
    
    for s in sections:
        if s['topic'].lower() == topic.lower():
            for r in s['rules']:
                # Clean up rule text
                r_text_clean = re.sub(r"^\[ID:\s*[a-f0-9]{6}\]\s*", "", r['text']).lower().strip()
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
