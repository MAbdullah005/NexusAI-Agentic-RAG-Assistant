import asyncio
import shutil
from .reranking import rerank
import json
from .config import settings
import urllib.request
import re
from .llm import generate_answer
from .github import download_repo,parse_github_url,get_repo_metadata
from .chunking import chunk_files, chunk_size_for_repo
from .embeddings import embed_text,embed_batch
from .vector_storage import add_chunks,query_chunks,get_files_chunks,get_files_chunks_sync,keyword_search,match_file_paths

TOP_K=10
MAX_RERANK=20
RRF_K=60

MIN_SCORE=0.15

VAGUE_PATTERNS = re.compile(
    r"\b(it|this|that|these|those|there|they|them)\b"
    r"|\b(what about|how about|explain it|why is that|and then|also)\b",
    re.IGNORECASE,
)

def is_standalone(question: str) -> bool:
    """True if the question carries enough context to be searched on its own."""
    q = question.strip()
    if len(q) < 5:
        return False
    if not any(c.isalpha() for c in q):
        return False
    return not bool(VAGUE_PATTERNS.search(q))

def build_search_query(question: str, history: list[dict] | None) -> str:
    """Search-query builder: combine with the last user question when needed.

    Only used for embedding/search. The LLM still sees the original question.
    """
    if is_standalone(question):
        return question
    last_user_q = next(
        (m["content"] for m in reversed(history or []) if m.get("role") == "user"),
        None,
    )
    if last_user_q:
        return f"{last_user_q} {question}"
    return question

# --- helpers ---

def latest_commit_sha(owner: str, repo: str, branch: str) -> str:
    """Fetch the current commit SHA for a branch."""
    with urllib.request.urlopen(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    ) as r:
        return json.load(r)["sha"]


def rrf_fuse(groups: list[tuple[list, list]]) -> tuple[list, list]:
    """Reciprocal Rank Fusion of ranked (docs, metas) candidate lists.

    Each group contributes score 1/(RRF_K + rank) per chunk, so a result that
    both vector search AND keyword search rank highly fuses to the top. A chunk
    found by only one method can still be first-placed by one list alone, so
    hybrid search never rejects either retrieval path.
    """
    scores: dict[tuple, float] = {}
    index: dict[tuple, tuple] = {}
    for docs, metas in groups:
        for rank, (d, m) in enumerate(zip(docs, metas), start=1):
            key = (m["file_path"], m["start_line"], m["end_line"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            if key not in index:
                index[key] = (d, m)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [index[k][0] for k in ordered], [index[k][1] for k in ordered]

# --- indexing pipeline: URL → metadata → download → filter → chunk → embed → store ---

async def index_repo(url:str)->dict:
    info=parse_github_url(url)
    owner=info["owner"]
    repo=info["repo"]
    meta=await get_repo_metadata(owner,repo)
    branch=meta["default_branch"]
    size_kb=meta["size_kb"]
    chunk_size,chunk_overlap=chunk_size_for_repo(size_kb)
    downloaded=await download_repo(owner,repo,branch)
    temp_dir=downloaded["temp_dir"]
    files=downloaded["filtered files"]
    if not files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("No filterable file found in this repo")
    try:
        commit_sha= await asyncio.to_thread(latest_commit_sha,owner,repo,branch)
        chunks= await asyncio.to_thread(chunk_files,files,commit_sha,owner,repo,chunk_size,chunk_overlap)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    if not chunks:
        raise ValueError("Repositry produced no chunks")
    texts=[c["text"] for c in chunks]
    vectors=await embed_text(texts)
    if not vectors or len(vectors) != len(chunks) or not all(len(v) == settings.EMBEDDING_DIMENSIONS for v in vectors):
        raise ValueError(f"Embedding count/dimension mismatch: {len(chunks)} chunks vs {len(vectors)} vectors")
    await add_chunks(chunks, vectors)

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "commit_sha": commit_sha,
        "file_count": len(files),
        "chunk_count": len(chunks),
        "chunk_size": chunk_size,
    }

# --- neighbor expansion: grab before + after chunk per initial result ---

async def find_neighbors(initial_metas:list[dict],owner:str,repo:str):
    """For each initial chunk, fetch the nearest chunk before and after in the same file.

    Adjacency is judged by line numbers with a max gap of 50 lines.
    All needed files are fetched in ONE batched query upfront.
    Deduplicates across all initial chunks so a neighbor is only added once.
    Returns added chunk docs/metas.
    """
    unique_paths = list(dict.fromkeys(m["file_path"] for m in initial_metas))
    by_file = await get_files_chunks(owner, repo, unique_paths)

    added_docs, added_metas = [], []
    added_keys = set()
    for m in initial_metas:
        docs, metas = by_file.get(m["file_path"], ([], []))
        if not docs:
            continue
        cur = (m["start_line"], m["end_line"])
        best_before_idx, best_before_gap = None, None
        best_after_idx, best_after_gap = None, None
        # scan file chunks to find closest before and after
        for idx, fm in enumerate(metas):
            if (fm["start_line"], fm["end_line"]) == cur:
                continue
            gap = fm["start_line"] - m["end_line"]
            if gap <= 0:
                # candidate overlaps or comes before — check how far back it ends
                prev_gap = m["start_line"] - fm["end_line"]
                if prev_gap >= 0 and (best_before_gap is None or prev_gap < best_before_gap):
                    best_before_idx, best_before_gap = idx, prev_gap
            else:
                # candidate comes after — track closest
                if best_after_gap is None or gap < best_after_gap:
                    best_after_idx, best_after_gap = idx, gap
        # add best before + after if they pass gap threshold and aren't duplicates
        for idx, neighbor_type in [(best_before_idx, "before"), (best_after_idx, "after")]:
            if idx is None:
                continue
            key = (metas[idx]["file_path"], metas[idx]["start_line"], metas[idx]["end_line"])
            if key in added_keys:
                continue
            if neighbor_type == "before":
                gap = m["start_line"] - metas[idx]["end_line"]
            else:
                gap = metas[idx]["start_line"] - m["end_line"]
            if 0 <= gap <= 50:
                added_keys.add(key)
                added_docs.append(docs[idx])
                added_metas.append(metas[idx])
    return added_docs, added_metas

# --- query pipeline: embed question → hybrid search (vector + FTS, RRF) → neighbors → rerank → LLM → answer + sources ---

async def ask(question: str, url: str, top_k: int = TOP_K, history: list[dict] | None = None) -> dict:
    info = parse_github_url(url)
    owner, repo = info["owner"], info["repo"]

    # HYBRID retrieval: three ranked lists fused by RRF —
    #   semantic (vector)      — meaning, paraphrases
    #   lexical (content FTS)  — exact/rare identifiers in code
    #   filename match         — explicitly named files (render.yaml)
    search_query = build_search_query(question, history)
    qvec = await asyncio.to_thread(
        lambda: embed_batch([search_query])[0]
    )

    v_docs, v_metas, _ = await query_chunks(owner, repo, qvec, top_k)
    k_docs, k_metas = await keyword_search(owner, repo, search_query, top_k)
    f_docs, f_metas = await match_file_paths(owner, repo, search_query, top_k)

    docs, metas = rrf_fuse([(v_docs, v_metas), (k_docs, k_metas), (f_docs, f_metas)])
    distances = [0.0] * len(docs)

    if not docs:
        return {"answer": "No matching code found in this repository.", "sources": []}

    # expand with same-file neighbors (before + after per chunk)
    n_docs, n_metas = await find_neighbors(metas, owner, repo)
    docs = docs + n_docs
    metas = metas + n_metas
    all_distances = list(distances) + [0] * len(n_docs)

    # dedupe by location
    seen = set()
    deduped = []
    for d, m, dist in zip(docs, metas, all_distances):
        key = (m["file_path"], m["start_line"], m["end_line"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((d, m, dist))
    docs = [d for d, _, _ in deduped]
    metas = [m for _, m, _ in deduped]
    deduped_distances = [dist for _, _, dist in deduped]

    # cap the rerank pool — Jina handles ~20 docs comfortably; beyond that it's
    # slow/429-prone and the extra low-rank chunks barely change the top-8.
    docs = docs[:MAX_RERANK]
    metas = metas[:MAX_RERANK]
    deduped_distances = deduped_distances[:MAX_RERANK]

    # Score ALL candidates (neighbors included) with Jina, then keep only those
    # above the relevance threshold (capped at 8) for the LLM context.
    reranked = await rerank(question, docs, len(docs))
    docs = [docs[i] for i, _ in reranked]
    metas = [metas[i] for i, _ in reranked]
    deduped_distances = [score for _, score in reranked]
    # drop chunks far below the top score (relative threshold), then trim to
    # top 8 most relevant. Jina reranker scores vary by repo, so an absolute
    # cutoff (e.g. 0.15) wrongly empties retrieval on small/README-heavy repos.
    if deduped_distances:
        top_score = max(deduped_distances)
        relative_cutoff = top_score * 0.25
        kept = [
            (d, m, s)
            for d, m, s in zip(docs, metas, deduped_distances)
            if s >= relative_cutoff
        ]
    else:
        kept = []
    docs = [x[0] for x in kept][:8]
    metas = [x[1] for x in kept][:8]
    deduped_distances = [x[2] for x in kept][:8]

    if not docs:
        return {"answer": "No matching code found in this repository.", "sources": []}

    # build context and get LLM answer
    context_parts = []
    for d, m in zip(docs, metas):
        file_label = f"### {m['file_path']} (lines {m['start_line']}-{m['end_line']})"
        context_parts.append(f"{file_label}\n{d}")
    context = "\n\n".join(context_parts)

    answer = await asyncio.to_thread(generate_answer, question, context,history)

    # build source links from chunk metadata
    sources = [
        {
            "file_path": m["file_path"],
            "start_line": m["start_line"],
            "end_line": m["end_line"],
            "commit_sha": m["commit_sha"],
            "score": round(d, 5),
        }
        for m, d in zip(metas, deduped_distances)
    ]
    return {"answer": answer, "sources": sources}


def find_neighbors_sync(initial_metas: list[dict], owner: str, repo: str):
    """Synchronous neighbor expansion."""
    unique_paths = list(dict.fromkeys(m["file_path"] for m in initial_metas))
    by_file = get_files_chunks_sync(owner, repo, unique_paths)

    added_docs, added_metas = [], []
    added_keys = set()
    for m in initial_metas:
        docs, metas = by_file.get(m["file_path"], ([], []))
        if not docs:
            continue
        cur = (m["start_line"], m["end_line"])
        best_before_idx, best_before_gap = None, None
        best_after_idx, best_after_gap = None, None
        for idx, fm in enumerate(metas):
            if (fm["start_line"], fm["end_line"]) == cur:
                continue
            gap = fm["start_line"] - m["end_line"]
            if gap <= 0:
                prev_gap = m["start_line"] - fm["end_line"]
                if prev_gap >= 0 and (best_before_gap is None or prev_gap < best_before_gap):
                    best_before_idx, best_before_gap = idx, prev_gap
            else:
                if best_after_gap is None or gap < best_after_gap:
                    best_after_idx, best_after_gap = idx, gap
        for idx, neighbor_type in [(best_before_idx, "before"), (best_after_idx, "after")]:
            if idx is None:
                continue
            key = (metas[idx]["file_path"], metas[idx]["start_line"], metas[idx]["end_line"])
            if key in added_keys:
                continue
            if neighbor_type == "before":
                gap = m["start_line"] - metas[idx]["end_line"]
            else:
                gap = metas[idx]["start_line"] - m["end_line"]
            if 0 <= gap <= 50:
                added_keys.add(key)
                added_docs.append(docs[idx])
                added_metas.append(metas[idx])
    return added_docs, added_metas
