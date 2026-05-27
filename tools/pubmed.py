"""
PubMed Client — Interface for NCBI E-utilities (Entrez) to search clinical literature.
"""

import requests
import json
import time

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

class PubMedClient:
    def __init__(self, email: str = "physician_ai@example.edu"):
        self.email = email
        self.tool = "PhysicianAI"

    def search(self, query: str, max_results: int = 15) -> list[dict]:
        """
        Searches PubMed for a query and returns a list of summaries.
        Uses relevance-based sorting to favor best matches.
        """
        # 1. Search for IDs
        search_url = f"{BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",  # Favors "Best Match" results
            "email": self.email,
            "tool": self.tool
        }
        
        try:
            resp = requests.get(search_url, params=params)
            resp.raise_for_status()
            id_list = resp.json().get("esearchresult", {}).get("idlist", [])
            
            if not id_list:
                return []

            # 2. Get summaries for IDs
            summary_url = f"{BASE_URL}/esummary.fcgi"
            sum_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
                "email": self.email,
                "tool": self.tool
            }
            
            # Brief delay to respect NCBI guidelines
            time.sleep(0.4)
            
            sum_resp = requests.get(summary_url, params=sum_params)
            sum_resp.raise_for_status()
            result_dict = sum_resp.json().get("result", {})
            
            summaries = []
            for pm_id in id_list:
                if pm_id in result_dict:
                    s = result_dict[pm_id]
                    summaries.append({
                        "id": pm_id,
                        "title": s.get("title"),
                        "source": s.get("source"),
                        "pubdate": s.get("pubdate"),
                        "authors": [a.get("name") for a in s.get("authors", [])],
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pm_id}/"
                    })
            return summaries

        except Exception as e:
            print(f"PubMed search error: {e}")
            return []
