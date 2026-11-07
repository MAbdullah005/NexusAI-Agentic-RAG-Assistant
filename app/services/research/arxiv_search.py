"""
arXiv Search Service for Deep Research Mode.
Retrieves academic research papers using arXiv's standard public Atom API.
"""

from typing import List, Dict, Any, Optional
import urllib.parse
import xml.etree.ElementTree as ET
import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def search_arxiv(
    query: str,
    max_results: int = 5,
    timeout: int = 8
) -> List[Dict[str, Any]]:
    """
    Search arXiv for academic papers matching the query.

    Returns:
        List of dicts: title, url, snippet (abstract), authors, published_date, source_type
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    logger.info(f"[DEEP RESEARCH ARXIV] Searching query='{cleaned_query}' (max_results={max_results})")

    # Format query for arXiv API
    encoded_query = urllib.parse.quote(cleaned_query)
    url = f"{ARXIV_API_BASE}?search_query=all:{encoded_query}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"

    headers = {
        "User-Agent": "NexusAI-DeepResearch/1.0 (academic research assistant)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"[DEEP RESEARCH ARXIV] Request failed with HTTP {resp.status_code}")
            return []

        root = ET.fromstring(resp.text)
        entries = root.findall("atom:entry", ATOM_NS)
        papers = []

        for entry in entries:
            title_elem = entry.find("atom:title", ATOM_NS)
            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Untitled Paper"

            # Check for dummy error entry
            if "Error" in title and "not found" in title.lower():
                continue

            id_elem = entry.find("atom:id", ATOM_NS)
            paper_url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

            summary_elem = entry.find("atom:summary", ATOM_NS)
            summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

            pub_elem = entry.find("atom:published", ATOM_NS)
            published = pub_elem.text.strip()[:10] if pub_elem is not None and pub_elem.text else None

            authors = []
            for author_elem in entry.findall("atom:author", ATOM_NS):
                name_elem = author_elem.find("atom:name", ATOM_NS)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            papers.append({
                "title": title,
                "url": paper_url,
                "snippet": summary,
                "authors": authors,
                "published_date": published,
                "source_type": "arxiv",
                "score": 0.8,
            })

        logger.info(f"[DEEP RESEARCH ARXIV] Retrieved {len(papers)} papers for '{cleaned_query}'")
        return papers

    except requests.exceptions.Timeout:
        logger.warning(f"[DEEP RESEARCH ARXIV] Request timed out for query '{cleaned_query}'")
        return []
    except Exception as e:
        logger.warning(f"[DEEP RESEARCH ARXIV] Error searching arXiv: {e}")
        return []

