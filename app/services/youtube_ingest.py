import os
from app.services.youtube_loader import load_youtube_transcript
from app.core.splitter import chunk_text
from app.llm.embeddings import get_embeddings
from app.core.vectorstore import create_vector_db

def process_youtube_transcript(text: str, doc_id: str, video_url: str, video_id: str = ""):
    """
    Split YouTube transcript text into retrieval-ready document chunks with preserved metadata.
    """
    vid_identifier = video_id or doc_id
    metadata = {
        "doc_id": doc_id,
        "source": video_url,
        "filename": f"YouTube Video ({vid_identifier})",
        "title": f"YouTube Video ({vid_identifier})",
        "type": "youtube",
    }
    return chunk_text(text=text, metadata=metadata, doc_id=doc_id)


def ingest_youtube(video_id: str, doc_id: str):
    """
    Build and SAVE vectorstore for YouTube video (ONLY ONCE)
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    text = load_youtube_transcript(url)

    if not text or len(text.strip()) < 10:
        raise ValueError("No valid transcript text extracted from YouTube video.")

    docs = process_youtube_transcript(text=text, doc_id=doc_id, video_url=url, video_id=video_id)
    if not docs:
        raise ValueError("Could not create retrieval chunks from YouTube transcript.")

    embeddings = get_embeddings()

    vectorstore = create_vector_db(docs, embeddings=embeddings)

    # SAVE FAISS
    save_path = os.path.join("data/yt/vectorstores/", doc_id)
    os.makedirs(save_path, exist_ok=True)

    vectorstore.save_local(save_path)

    return save_path