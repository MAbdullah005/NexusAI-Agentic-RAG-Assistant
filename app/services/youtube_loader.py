from __future__ import annotations

import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    RequestBlocked,
)


def extract_video_id(url: str) -> str:
    """
    Extract YouTube video ID from various standard YouTube URL formats.
    Supports watch?v=..., youtu.be/..., embed/..., shorts/..., and direct IDs.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Invalid YouTube URL: URL cannot be empty.")

    clean_url = url.strip()

    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, clean_url)
        if match:
            return match.group(1)

    raise ValueError(f"Invalid YouTube URL: Could not extract video ID from '{url}'.")


def format_timestamp(seconds: float | int) -> str:
    """
    Format seconds into MM:SS or HH:MM:SS timestamp string.
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def load_youtube_transcript(url: str) -> str:
    """
    Fetch and return transcript text with embedded timestamp markers for YouTube video.
    Raises ValueError with descriptive reason if transcripts are disabled, missing, or blocked.
    """
    video_id = extract_video_id(url)

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id=video_id)

        transcript = None
        # Priority languages: English first
        target_languages = ["en", "en-US", "en-GB", "en-CA", "en-AU"]
        try:
            transcript = transcript_list.find_transcript(target_languages)
        except Exception:
            # Fall back to any manually created transcript
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    list(transcript_list._manually_created_transcripts.keys())
                )
            except Exception:
                # Fall back to generated transcript
                try:
                    transcript = transcript_list.find_generated_transcript(
                        list(transcript_list._generated_transcripts.keys())
                    )
                except Exception:
                    # Fall back to first available in the list
                    transcript = next(iter(transcript_list))

        if not transcript:
            raise ValueError(f"No transcripts available for YouTube video ({video_id}).")

        snippets = transcript.fetch()

        if not snippets:
            raise ValueError(f"The transcript for YouTube video ({video_id}) is empty.")

        # Format snippets with timestamps for accurate grounding and citations
        formatted_chunks = []
        for s in snippets:
            text = s.text if hasattr(s, "text") else (s.get("text", "") if isinstance(s, dict) else str(s))
            start_sec = s.start if hasattr(s, "start") else (s.get("start", 0) if isinstance(s, dict) else 0)
            clean_text = text.strip()
            if clean_text:
                ts = format_timestamp(start_sec)
                formatted_chunks.append(f"[{ts}] {clean_text}")

        full_text = "\n".join(formatted_chunks)

        if not full_text or len(full_text.strip()) < 10:
            raise ValueError(f"Extracted transcript for YouTube video ({video_id}) contains no usable text.")

        return full_text

    except TranscriptsDisabled:
        raise ValueError(
            f"Transcripts are disabled by the video owner for YouTube video ({video_id})."
        )
    except NoTranscriptFound:
        raise ValueError(
            f"No captions or transcript found for YouTube video ({video_id})."
        )
    except VideoUnavailable:
        raise ValueError(
            f"YouTube video ({video_id}) is private, unavailable, or restricted."
        )
    except RequestBlocked:
        raise ValueError(
            "YouTube request was temporarily blocked by rate limiting. Please try again later."
        )
    except Exception as e:
        err_msg = str(e)
        if "TranscriptsDisabled" in err_msg or "disabled" in err_msg.lower():
            raise ValueError(f"Transcripts are disabled for YouTube video ({video_id}).")
        if "NoTranscriptFound" in err_msg or "Could not find" in err_msg:
            raise ValueError(f"No transcript found for YouTube video ({video_id}).")
        raise ValueError(f"Failed to retrieve YouTube transcript for ({video_id}): {err_msg}")