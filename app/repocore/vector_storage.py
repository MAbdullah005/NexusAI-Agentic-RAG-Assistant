from sqlalchemy import Column, Integer, String, Text, text, bindparam
import re
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from .database import engine, sync_engine
from .config import settings
from app.db.models import Chunk, Base


embedding_param = bindparam("embedding", type_=Vector(settings.EMBEDDING_DIMENSIONS))


async def add_chunks(chunks, embeddings):
    """Store chunks + embeddings. Only re-indexes if commit_sha changed."""
    if not chunks:
        return
    if len(chunks) != len(embeddings):
        raise ValueError(f"chunks embeddings mismatch: {len(chunks)} vs {len(embeddings)}")

    owner = chunks[0]["metadata"]["owner"]
    repo = chunks[0]["metadata"]["repo"]
    commit_sha = chunks[0]["metadata"]["commit_sha"]

    async with engine.begin() as conn:
        existing = await conn.execute(
            text("SELECT commit_sha FROM chunks WHERE owner = :owner AND repo = :repo LIMIT 1"),
            {"owner": owner, "repo": repo}
        )
        row = existing.fetchone()
        if row and row[0] == commit_sha:
            return

        await conn.execute(
            text("DELETE FROM chunks WHERE owner = :owner AND repo = :repo"),
            {"owner": owner, "repo": repo}
        )

        for chunk, embedding in zip(chunks, embeddings):
            meta = chunk["metadata"]
            await conn.execute(
                text("""
                    INSERT INTO chunks (owner, repo, commit_sha, file_path, language, start_line, end_line, content, embedding)
                    VALUES (:owner, :repo, :commit_sha, :file_path, :language, :start_line, :end_line, :content, :embedding)
                """).bindparams(embedding_param),
                {
                    "owner": meta["owner"],
                    "repo": meta["repo"],
                    "commit_sha": meta["commit_sha"],
                    "file_path": meta["file_path"],
                    "language": meta.get("language"),
                    "start_line": meta["start_line"],
                    "end_line": meta["end_line"],
                    "content": chunk["text"],
                    "embedding": embedding,
                }
            )

async def query_chunks(owner, repo, embedding, k=5):
    """Semantic search: return top-k chunks for a repo by embedding similarity."""
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language,
                       embedding <=> :embedding AS distance
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                ORDER BY embedding <=> :embedding
                LIMIT :k
            """).bindparams(embedding_param),
            {"owner": owner, "repo": repo, "embedding": embedding, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    distances = [row[8] for row in rows]
    return documents, metadatas, distances


async def get_file_chunks(owner, repo, file_path):
    """Return all chunks stored for a single file (used by neighbor expansion)."""
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo AND file_path = :file_path
            """),
            {"owner": owner, "repo": repo, "file_path": file_path}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas



async def get_files_chunks(owner, repo, file_paths):
    """Fetch chunks for many files in ONE query. Returns {file_path: (docs, metas)}.

    Replaces the N-per-file round trips in neighbor expansion with a single
    query; repeated files in the request are free.
    """
    unique = sorted(set(file_paths))
    if not unique:
        return {}

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo AND file_path = ANY(:paths)
            """),
            {"owner": owner, "repo": repo, "paths": unique}
        )
        rows = result.fetchall()

    grouped = {}
    for row in rows:
        meta = {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        grouped.setdefault(row[4], ([], []))
        grouped[row[4]][0].append(row[0])
        grouped[row[4]][1].append(meta)
    return grouped


FILE_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]+\.[A-Za-z0-9]{1,10}")


def path_tokens(query: str) -> list[str]:
    """Extract filename/path tokens from a question (e.g. render.yaml, src/a.ts)."""
    tokens = set(FILE_TOKEN_RE.findall(query))
    for m in re.finditer(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", query):
        tokens.add(m.group(0))
    cleaned = []
    for t in tokens:
        t = t.lstrip("./").rstrip("/")
        if len(t) >= 2:
            cleaned.append(t)
    return sorted(cleaned) if cleaned else []


async def match_file_paths(owner, repo, query, k=15):
    """Deterministic filename lookup: chunks whose file_path matches path tokens."""
    tokens = path_tokens(query)
    if not tokens:
        return [], []

    conds = []
    params = {"owner": owner, "repo": repo, "k": k}
    for i, t in enumerate(tokens):
        p_eq, p_like = f"eq{i}", f"like{i}"
        params[p_eq] = t
        params[p_like] = f"%{t}%"
        conds.append(f"(file_path = :{p_eq} OR file_path ILIKE :{p_like})")
    where = " OR ".join(conds)

    sql = f"""
        SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
        FROM chunks
        WHERE owner = :owner AND repo = :repo AND ({where})
        ORDER BY file_path
        LIMIT :k
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(sql), params)
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas



async def keyword_search(owner, repo, query, k=15):
    """Lexical full-text search over chunk content AND file paths (Postgres FTS)."""
    terms = list(dict.fromkeys(
        t for t in re.findall(r"[A-Za-z0-9_.\-]+", query) if len(t) >= 2
    ))
    if not terms:
        return [], []
    or_query = " | ".join(terms)

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                  AND search_tsv @@ to_tsquery('english', :or_query)
                ORDER BY ts_rank_cd(search_tsv, to_tsquery('english', :or_query)) DESC, file_path
                LIMIT :k
            """),
            {"owner": owner, "repo": repo, "or_query": or_query, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas



def query_chunks_sync(owner, repo, embedding, k=5):
    """Synchronous semantic search: return top-k chunks for a repo by embedding similarity."""
    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language,
                       embedding <=> :embedding AS distance
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                ORDER BY embedding <=> :embedding
                LIMIT :k
            """).bindparams(embedding_param),
            {"owner": owner, "repo": repo, "embedding": embedding, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    distances = [row[8] for row in rows]
    return documents, metadatas, distances


def get_files_chunks_sync(owner, repo, file_paths):
    """Synchronous batch chunk lookup across files for neighbor expansion."""
    unique = sorted(set(file_paths))
    if not unique:
        return {}

    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo AND file_path = ANY(:paths)
            """),
            {"owner": owner, "repo": repo, "paths": unique}
        )
        rows = result.fetchall()

    grouped = {}
    for row in rows:
        meta = {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        grouped.setdefault(row[4], ([], []))
        grouped[row[4]][0].append(row[0])
        grouped[row[4]][1].append(meta)
    return grouped


def match_file_paths_sync(owner, repo, query, k=15):
    """Synchronous deterministic filename lookup: chunks whose file_path matches path tokens."""
    tokens = path_tokens(query)
    q_lower = query.lower()
    if any(w in q_lower for w in ("summarize", "summary", "overview", "about", "what does", "readme")):
        if "readme" not in [t.lower() for t in tokens]:
            tokens.append("README")

    if not tokens:
        return [], []

    conds = []
    params = {"owner": owner, "repo": repo, "k": k}
    for i, t in enumerate(tokens):
        p_eq, p_like = f"eq{i}", f"like{i}"
        params[p_eq] = t
        params[p_like] = f"%{t}%"
        conds.append(f"(file_path = :{p_eq} OR file_path ILIKE :{p_like})")
    where = " OR ".join(conds)

    sql = f"""
        SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
        FROM chunks
        WHERE owner = :owner AND repo = :repo AND ({where})
        ORDER BY file_path
        LIMIT :k
    """

    with sync_engine.begin() as conn:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas


def keyword_search_sync(owner, repo, query, k=15):
    """Synchronous lexical full-text search over chunk content AND file paths (Postgres FTS)."""
    terms = list(dict.fromkeys(
        t for t in re.findall(r"[A-Za-z0-9_.\-]+", query) if len(t) >= 2
    ))
    if not terms:
        return [], []
    or_query = " | ".join(terms)

    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                  AND search_tsv @@ to_tsquery('english', :or_query)
                ORDER BY ts_rank_cd(search_tsv, to_tsquery('english', :or_query)) DESC, file_path
                LIMIT :k
            """),
            {"owner": owner, "repo": repo, "or_query": or_query, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas



def query_chunks_sync(owner, repo, embedding, k=5):
    """Synchronous semantic search: return top-k chunks for a repo by embedding similarity."""
    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language,
                       embedding <=> :embedding AS distance
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                ORDER BY embedding <=> :embedding
                LIMIT :k
            """).bindparams(embedding_param),
            {"owner": owner, "repo": repo, "embedding": embedding, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    distances = [row[8] for row in rows]
    return documents, metadatas, distances


def get_files_chunks_sync(owner, repo, file_paths):
    """Synchronous batch chunk lookup across files for neighbor expansion."""
    unique = sorted(set(file_paths))
    if not unique:
        return {}

    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo AND file_path = ANY(:paths)
            """),
            {"owner": owner, "repo": repo, "paths": unique}
        )
        rows = result.fetchall()

    grouped = {}
    for row in rows:
        meta = {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        grouped.setdefault(row[4], ([], []))
        grouped[row[4]][0].append(row[0])
        grouped[row[4]][1].append(meta)
    return grouped


def match_file_paths_sync(owner, repo, query, k=15):
    """Synchronous deterministic filename lookup: chunks whose file_path matches path tokens."""
    tokens = path_tokens(query)
    q_lower = query.lower()
    if any(w in q_lower for w in ("summarize", "summary", "overview", "about", "what does", "readme")):
        if "readme" not in [t.lower() for t in tokens]:
            tokens.append("README")

    if not tokens:
        return [], []

    conds = []
    params = {"owner": owner, "repo": repo, "k": k}
    for i, t in enumerate(tokens):
        p_eq, p_like = f"eq{i}", f"like{i}"
        params[p_eq] = t
        params[p_like] = f"%{t}%"
        conds.append(f"(file_path = :{p_eq} OR file_path ILIKE :{p_like})")
    where = " OR ".join(conds)

    sql = f"""
        SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
        FROM chunks
        WHERE owner = :owner AND repo = :repo AND ({where})
        ORDER BY file_path
        LIMIT :k
    """

    with sync_engine.begin() as conn:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas


def keyword_search_sync(owner, repo, query, k=15):
    """Synchronous lexical full-text search over chunk content AND file paths (Postgres FTS)."""
    terms = list(dict.fromkeys(
        t for t in re.findall(r"[A-Za-z0-9_.\-]+", query) if len(t) >= 2
    ))
    if not terms:
        return [], []
    or_query = " | ".join(terms)

    with sync_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT content, owner, repo, commit_sha, file_path, start_line, end_line, language
                FROM chunks
                WHERE owner = :owner AND repo = :repo
                  AND search_tsv @@ to_tsquery('english', :or_query)
                ORDER BY ts_rank_cd(search_tsv, to_tsquery('english', :or_query)) DESC, file_path
                LIMIT :k
            """),
            {"owner": owner, "repo": repo, "or_query": or_query, "k": k}
        )
        rows = result.fetchall()

    documents = [row[0] for row in rows]
    metadatas = [
        {
            "owner": row[1], "repo": row[2], "commit_sha": row[3],
            "file_path": row[4], "start_line": row[5], "end_line": row[6],
            "language": row[7],
        }
        for row in rows
    ]
    return documents, metadatas

