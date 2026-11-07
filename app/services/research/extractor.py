"""
Web Content Extractor for Deep Research Mode.
Extracts main article body text using requests and BeautifulSoup with robust error handling.
"""

from typing import Optional, Dict, Any
import re
import requests
from bs4 import BeautifulSoup

from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 5
MAX_EXTRACT_CHARS = 12000
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Elements to remove completely before text extraction
UNWANTED_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "form", "noscript", "svg", "button", "iframe", "menu"
]

# Common classes and IDs containing ads, cookie banners, navigation
UNWANTED_SELECTORS = [
    ".ad", ".advertisement", ".cookie-banner", ".navbar", ".navigation",
    ".sidebar", ".menu", ".social-share", ".newsletter-signup", "#cookie-notice",
    "#header", "#footer", ".comments", "#comments"
]


def extract_page_content(
    url: str,
    fallback_snippet: str = "",
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Fetch and extract cleaned main article text from a web URL.
    Gracefully falls back to fallback_snippet if extraction fails or blocks.

    Returns:
        dict: {
            "url": str,
            "text": str,
            "success": bool,
            "extracted_length": int
        }
    """
    if not url or not url.startswith("http"):
        return {
            "url": url,
            "text": fallback_snippet,
            "success": False,
            "extracted_length": len(fallback_snippet),
        }

    # Don't try scraping binary or non-HTML files
    if any(url.lower().endswith(ext) for ext in [".pdf", ".zip", ".tar.gz", ".png", ".jpg"]):
        return {
            "url": url,
            "text": fallback_snippet,
            "success": False,
            "extracted_length": len(fallback_snippet),
        }

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            logger.info(f"[DEEP RESEARCH EXTRACT] HTTP {resp.status_code} for {url}; using snippet")
            return {
                "url": url,
                "text": fallback_snippet,
                "success": False,
                "extracted_length": len(fallback_snippet),
            }

        # Check content type
        content_type = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            return {
                "url": url,
                "text": fallback_snippet,
                "success": False,
                "extracted_length": len(fallback_snippet),
            }

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip unwanted tags
        for tag in soup(UNWANTED_TAGS):
            tag.decompose()

        # Try to find main content element if available
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"content|post|article|body", re.I))
            or soup.body
            or soup
        )

        # Extract text paragraphs
        paragraphs = []
        for p in main_content.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
            text = p.get_text(strip=True)
            if len(text) > 30:  # Skip tiny labels and nav breadcrumbs
                paragraphs.append(text)

        extracted_text = "\n\n".join(paragraphs).strip()

        # Fallback to general stripped strings if paragraph extraction is too short
        if len(extracted_text) < 150:
            extracted_text = "\n\n".join(soup.stripped_strings)

        # Normalize spaces within lines while preserving paragraph breaks
        cleaned_paragraphs = []
        for p in extracted_text.split("\n\n"):
            norm = re.sub(r"[ \t]+", " ", p).strip()
            if len(norm) > 25:
                cleaned_paragraphs.append(norm)

        cleaned = "\n\n".join(cleaned_paragraphs)

        if len(cleaned) > MAX_EXTRACT_CHARS:
            cleaned = cleaned[:MAX_EXTRACT_CHARS] + "..."

        if len(cleaned) < 80 and fallback_snippet:
            cleaned = fallback_snippet

        return {
            "url": url,
            "text": cleaned,
            "success": True,
            "extracted_length": len(cleaned),
        }

    except requests.exceptions.Timeout:
        logger.info(f"[DEEP RESEARCH EXTRACT] Timeout for {url}; using snippet fallback")
        return {
            "url": url,
            "text": fallback_snippet,
            "success": False,
            "extracted_length": len(fallback_snippet),
        }
    except Exception as e:
        logger.info(f"[DEEP RESEARCH EXTRACT] Failed for {url} ({e}); using snippet fallback")
        return {
            "url": url,
            "text": fallback_snippet,
            "success": False,
            "extracted_length": len(fallback_snippet),
        }
