import os
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

# --- extension → langchain Language mapping (for smart splitting) ---

LANGUAGE_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".mjs": Language.JS,
    ".cjs": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".c": Language.CPP,
    ".cc": Language.CPP,
    ".cpp": Language.CPP,
    ".h": Language.CPP,
    ".hpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".swift": Language.SWIFT,
    ".kt": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".html": Language.HTML,
    ".htm": Language.HTML,
    ".md": Language.MARKDOWN,
    ".markdown": Language.MARKDOWN,
    ".rst": Language.RST,
    ".lua": Language.LUA,
    ".pl": Language.PERL,
    ".pm": Language.PERL,
}


def detect_language(relative_path: str) -> Language | None:
    """Map file extension to a Language enum for the text splitter."""
    return LANGUAGE_MAP.get(os.path.splitext(relative_path)[1])



def line_range(text: str, start_offset: int,end_offset:int) -> tuple[int, int]:
    """Return the start and end line numbers of a chunk.""" 
    start_line = text.count("\n", 0, start_offset) + 1 
    end_line = text.count("\n", 0, end_offset) + 1
    return start_line, end_line


def split_code(text:str,chunk_size:int,chunk_overlap:int,relative_path:str):
    """Split file text into chunks using generic splitter."""
    splitter=RecursiveCharacterTextSplitter(separators=["\n\n","\n"," ",""],chunk_size=chunk_size,
        chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


# --- main entry point: split all files → chunks with line-number metadata ---

def chunk_size_for_repo(size_kb: int) -> tuple[int, int]:
    """Pick chunk_size/overlap based on repo size in KB."""
    if size_kb < 5_000:
        return 2000, 300
    if size_kb < 50_000:
        return 2500, 400
    return 3000, 500


def chunk_files(files:list[dict],commit_sha:str,owner:str,
                repo:str,chunk_size:int=1300,chunk_overlap:int=300)->list[dict]:
    
    chunk=[]
    for file in files:
        
        try:
            with open(file["path"],'r',encoding="utf-8",errors="ignore") as f:
                text=f.read()
        except OSError:
            continue
        if not text.strip():
            continue
        relative_path=file["relative_path"]
        detected = detect_language(relative_path)
        parts=split_code(text,chunk_size,chunk_overlap,relative_path)
        prev_end=0
        for part in parts:
            # consecutive chunks overlap by up to chunk_overlap chars, so the
            # next chunk may start before the previous one ended.
            start_offset = text.find(part, max(0, prev_end - chunk_overlap))
            if start_offset == -1:
                logging.getLogger(__name__).warning(
                    "could not locate chunk inside %s — skipping", relative_path
                )
                continue
            end_offset = start_offset + len(part)
            start_line, end_line = line_range( text, start_offset, end_offset )
            prev_end = end_offset
            chunk.append({
                "text":part,
                "metadata":{
                    "owner":owner,
                    "repo":repo,
                    "commit_sha":commit_sha,
                    "file_path":relative_path,
                    "start_line":start_line,
                    "end_line":end_line,
                    "language": detected.value if detected else None
                }
            })

    return chunk


