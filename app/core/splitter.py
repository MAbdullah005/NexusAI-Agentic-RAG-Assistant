from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.common import is_valid_chunk
from app.utils.logger import logger

def chunk_text(text: str):
    text_length = len(text)
    logger.info(f"Here is the length of text this for this time {text_length}")

    # 1. Adaptive chunk sizing

    if text_length < 10_000:
        chunk_size = 1000
        chunk_overlap = 150

    elif text_length < 100_000:
        chunk_size = 1500
        chunk_overlap = 200

    else:
        chunk_size = 2500
        chunk_overlap = 300

    logger.info(f"Chunk size use for this embeding is {chunk_size} and chun overlap is {chunk_overlap}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    docs = splitter.create_documents([text])

    # remove empty chunks
    chunks = [d for d in docs if d.page_content.strip()]
    chunks = [c for c in chunks if is_valid_chunk(c.page_content)]

    return chunks

