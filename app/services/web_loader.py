from __future__ import annotations

import requests

from bs4 import BeautifulSoup

from langchain_core.documents import Document


# WEB LOADER

def load_webpage(url: str) -> Document:
    """
    Load a webpage and extract clean readable text.

    Returns:
        LangChain Document containing:
        - page_content
        - metadata (source URL and page title)
    """

    # 1. VALIDATE URL

    if not url:
        raise ValueError("URL cannot be empty.")

    if not url.startswith(("http://", "https://")):
        raise ValueError(
            "Invalid URL. URL must start with http:// or https://"
        )

    print("\n" + "=" * 80)
    print("[WEB LOADER]")
    print("=" * 80)

    print(f"[WEB] Fetching URL: {url}")

    # 2. FETCH WEBPAGE

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        print(f"[WEB] Failed to fetch webpage: {str(e)}")

        raise RuntimeError(
            f"Could not load webpage: {str(e)}"
        )

    print(
        f"[WEB] Status Code: {response.status_code}"
    )

    # 3. PARSE HTML

    soup = BeautifulSoup(
        response.text,
        "lxml"
    )

    # 4. EXTRACT TITLE

    title = ""

    if soup.title and soup.title.string:

        title = soup.title.string.strip()

    if not title:

        title = url

    print(f"[WEB] Page Title: {title}")

    # 5. REMOVE UNWANTED CONTENT

    unwanted_tags = [

        "script",
        "style",
        "noscript",
        "iframe",
        "svg",

        "nav",
        "footer",
        "header",
        "aside",

        "form",
        "button",

    ]

    for tag in soup(unwanted_tags):

        tag.decompose()

    # 6. TRY TO FIND MAIN CONTENT

    main_content = (

        soup.find("article")

        or soup.find("main")

        or soup.find(
            "div",
            class_=lambda value:
            value
            and any(
                keyword in value.lower()
                for keyword in [
                    "article",
                    "content",
                    "post",
                    "entry",
                ]
            )
        )

    )

    # 7. EXTRACT TEXT

    if main_content:

        text = main_content.get_text(
            separator="\n",
            strip=True
        )

        print(
            "[WEB] Main article content detected."
        )

    else:

        text = soup.get_text(
            separator="\n",
            strip=True
        )

        print(
            "[WEB] Main content not detected. "
            "Using cleaned page text."
        )

    # 8. CLEAN TEXT

    lines = [

        line.strip()

        for line in text.splitlines()

        if line.strip()

    ]

    # Remove duplicate consecutive lines

    cleaned_lines = []

    previous_line = None

    for line in lines:

        if line != previous_line:

            cleaned_lines.append(line)

        previous_line = line

    clean_text = "\n".join(
        cleaned_lines
    )

    # 9. VALIDATE CONTENT

    if len(clean_text) < 100:

        raise ValueError(
            "Could not extract enough readable content "
            "from this webpage."
        )

    # 10. CREATE LANGCHAIN DOCUMENT

    document = Document(

        page_content=clean_text,

        metadata={
            "source": url,
            "title": title,
            "type": "web",
        }

    )

    print(
        f"[WEB] Extracted characters: "
        f"{len(clean_text)}"
    )

    print("[WEB] Webpage loaded successfully.")

    print("=" * 80 + "\n")

    return document