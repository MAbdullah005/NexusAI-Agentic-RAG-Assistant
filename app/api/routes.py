from fastapi import APIRouter, UploadFile, File,Depends
import uuid
from fastapi import Form
from fastapi.responses import FileResponse
from app.services.youtube_loader import extract_video_id
from app.core.retriever import clear_thread_retriever_cache
import os
import sqlite3
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from app.services.youtube_ingest import ingest_youtube
from app.auth.dependencies import get_current_user

from app.utils.logger import get_logger
from app.core.retriever import thread_document_metadata
from app.graph.agent_graph import chatbot
from app.schemas.resume_chat import HITLResumeRequest
from app.services.pdf_ingest import ingest_pdf
from app.utils.common import extract_ai_text
from app.memory.postgres_memory import (
    get_thread_title_db,
    save_thread_title,
    save_message,
    get_thread_messages,
    verify_thread_ownership,
    backfill_thread_messages_from_checkpoint,
    save_thread_summary,
    get_thread_summary,
)
from app.llm.title_generator import generate_chat_title
from fastapi import HTTPException
logger = get_logger(__name__)

router = APIRouter()

from app.db.connection_adapter import get_db_connection
from app.db.session import checkpointer


#  Chat Endpoint 
@router.post("/chat")
async def chat_endpoint(
    data: dict,
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["user_id"]

    user_input = data.get("message")
    thread_id = data.get("thread_id")
    client_message_id = data.get("client_message_id") or data.get("message_id")
    selected_doc_ids = data.get("selected_doc_ids")

    if not user_input or not thread_id:
        raise HTTPException(
            status_code=400,
            detail="message and thread_id are required."
        )

    # ========================================================
    # VERIFY THREAD OWNERSHIP
    # ========================================================

    if not verify_thread_ownership(thread_id, user_id):
        raise HTTPException(
            status_code=404,
            detail="Thread not found"
        )

    # ========================================================
    # CHECK IDEMPOTENCY / CACHED RESPONSE
    # ========================================================

    user_mid = client_message_id or str(uuid.uuid4())
    assistant_mid = f"resp_{user_mid}"

    if client_message_id:
        with get_db_connection() as idem_conn:
            cursor = idem_conn.cursor()
            cursor.execute(
                """
                SELECT content
                FROM messages
                WHERE message_id = ? AND thread_id = ? AND user_id = ? AND role = 'assistant'
                """,
                (assistant_mid, thread_id, user_id)
            )
            cached_resp = cursor.fetchone()
        if cached_resp:
            logger.info(f"[CHAT API] Returning cached idempotent response for message_id={client_message_id}")
            return {
                "status": "completed",
                "thread_id": thread_id,
                "response": cached_resp[0],
            }

    # ========================================================
    # PERSIST USER MESSAGE UPFRONT
    # ========================================================

    try:
        save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content=user_input,
            message_id=user_mid,
            strict=True,
        )
    except ValueError as e:
        logger.error(f"[CHAT API] Failed to save user message: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # ========================================================
    # LANGGRAPH CONFIsG
    # ========================================================

    CONFIG = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "selected_doc_ids": selected_doc_ids,
        },
        "run_name": "chat_turn",
    }

    # ========================================================
    # RUN GRAPH
    # ========================================================

    try:
        response = chatbot.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=user_input,
                        id=user_mid
                    )
                ]
            },
            config=CONFIG,
        )
    except Exception as e:
        logger.error(f"[CHAT API] Graph execution failed for thread {thread_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat execution failed: {str(e)}"
        )

    print("\n" + "=" * 80)
    print("[CHAT API]")
    print("=" * 80)

    print(
        f"[CHAT API] Graph response type: "
        f"{type(response)}"
    )

    print(
        f"[CHAT API] Response keys: "
        f"{response.keys() if isinstance(response, dict) else 'N/A'}"
    )

    # ========================================================
    # CHECK LANGGRAPH INTERRUPT
    # ========================================================

    if isinstance(response, dict) and "__interrupt__" in response:

        interrupts = response["__interrupt__"]

        print(
            "[CHAT API] Graph interrupted -> HITL"
        )

        print(
            f"[CHAT API] Interrupt data: {interrupts}"
        )

        interrupt_data = {}

        if interrupts:

            first_interrupt = interrupts[0]

            # LangGraph Interrupt object
            if hasattr(
                first_interrupt,
                "value"
            ):

                interrupt_data = (
                    first_interrupt.value
                )

            elif isinstance(
                first_interrupt,
                dict
            ):

                interrupt_data = (
                    first_interrupt
                )

        # Do NOT persist incomplete assistant answer when interrupted!
        return {
            "status": "human-approval",
            "thread_id": thread_id,
            "interrupt": interrupt_data,
        }

    # ========================================================
    # NORMAL COMPLETED RESPONSE
    # ========================================================

    if not response.get("messages"):
        ai_response = "⚠️ No response generated."
    else:
        ai_response = extract_ai_text(
            response["messages"][-1]
        )

    # Persist final assistant response
    try:
        save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content=ai_response,
            message_id=assistant_mid,
            strict=True,
        )
    except ValueError as e:
        logger.error(f"[CHAT API] Failed to save assistant message: {e}")

    # Persist summary if generated/updated by graph
    if isinstance(response, dict) and response.get("summary"):
        save_thread_summary(thread_id, response["summary"], user_id=user_id)

    print(
        "[CHAT API] Normal response generated and persisted"
    )

    return {
        "status": "completed",
        "thread_id": thread_id,
        "response": ai_response,
    }

#  Threads 

@router.get("/threads") # done
def get_threads(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                thread_id,
                title,
                created_at
            FROM threads
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

    result = []

    for row in rows:
        created_val = row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]) if row[2] else None
        result.append({
            "thread_id": row[0],
            "title": row[1] or f"Chat {row[0][:6]}",
            "created_at": created_val
        })

    return result


#  New Thread 

@router.post("/new-thread") # done
def new_thread(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    thread_id = str(uuid.uuid4())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO threads (
                thread_id,
                user_id,
                title,
                created_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                thread_id,
                user_id,
                "New Chat"
            )
        )

    return {
        "thread_id": thread_id
    }


#  Title Generation 

@router.post("/generate-title") # done
def generate_title(data: dict):
    thread_id = data["thread_id"]
    message = data["message"]
    user_id1=data["user_id"]

    title = generate_chat_title(message)
    save_thread_title(thread_id,user_id1,title)

    return {"title": title}


# upload url

@router.post("/upload-url")
async def upload_url(url:str=Form(...),
                     thread_id:str=Form(...),
                     current_user: dict = Depends(get_current_user)
                     ):
    user_id=current_user["user_id"]

    with get_db_connection() as conn:
        cursor=conn.cursor()

        # verify the user first 
        cursor.execute("""
SELECT thread_id
FROM threads
WHERE thread_id=?
AND user_id=?
""",
(thread_id,user_id))
        thread=cursor.fetchone()
        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )
        from app.core.web_processor import ingest_web
        doc_id = str(uuid.uuid4())

        try:
            web_info = ingest_web(url=url, doc_id=doc_id, thread_id=thread_id)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to scrape and index web URL: {str(e)}"
            )

        cursor.execute("""
INSERT into documents (
doc_id,
user_id,
type,
content_hash,
source,
vectorstore_path,
filename
    )
    VALUES (?,?,?,?,?,?,?)
""",
(doc_id,
 user_id,
 web_info["type"],
 web_info["content_hash"],
 web_info["source"],
 web_info["vectorstore_path"],
 web_info["title"]
 )
)

        cursor.execute("""
INSERT INTO thread_documents
(
thread_id,
doc_id
)  
VALUES (? , ?)
""",
(thread_id,doc_id)
)

    clear_thread_retriever_cache(thread_id=thread_id)

    return {"status":"new",
            "doc_id":doc_id,
            "title":web_info["title"]
            }





@router.post("/upload-repo")
async def upload_repo(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    url = data.get("url", "").strip()
    thread_id = data.get("thread_id", "").strip()

    if not url:
        raise HTTPException(status_code=400, detail="Repository URL is required.")
    if not url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="URL must be a valid GitHub repository URL (https://github.com/owner/repo).")

    from app.repocore.github import parse_github_url
    from datetime import datetime, timezone

    info = parse_github_url(url)
    owner, repo_name = info["owner"], info["repo"]

    # --- Block 1: validate thread ownership, then release connection ---
    if thread_id:
        with get_db_connection() as val_conn:
            cursor = val_conn.cursor()
            cursor.execute(
                """
                SELECT thread_id
                FROM threads
                WHERE thread_id = ? AND user_id = ?
                """,
                (thread_id, user_id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Thread not found")

    # --- Long async operation: no connection held ---
    try:
        from app.repocore.rag import index_repo
        result = await index_repo(url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD REPO] Failed to index repository {url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index GitHub repository: {str(e)}"
        )

    # --- Block 2: persist document metadata ---
    try:
        with get_db_connection() as doc_conn:
            cursor = doc_conn.cursor()
            cursor.execute(
                "SELECT doc_id FROM documents WHERE source = ? AND user_id = ?",
                (url, user_id)
            )
            existing = cursor.fetchone()
            if existing:
                doc_id = existing[0]
                cursor.execute(
                    "UPDATE documents SET content_hash = ? WHERE doc_id = ?",
                    (result.get("commit_sha", ""), doc_id)
                )
            else:
                doc_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO documents (
                        doc_id, user_id, type, content_hash, source, vectorstore_path, filename, created_at
                    )
                    VALUES (?, ?, 'github', ?, ?, '', ?, ?)
                    """,
                    (
                        doc_id,
                        user_id,
                        result.get("commit_sha", ""),
                        url,
                        f"{owner}/{repo_name}",
                        datetime.now(timezone.utc).isoformat()
                    )
                )

            if thread_id:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO thread_documents (thread_id, doc_id)
                    VALUES (?, ?)
                    """,
                    (thread_id, doc_id)
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD REPO] Failed to persist document for {url}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save repository metadata: {str(e)}"
        )

    if thread_id:
        clear_thread_retriever_cache(thread_id=thread_id)

    return {
        "status": "completed",
        "doc_id": doc_id,
        "url": url,
        "filename": f"{owner}/{repo_name}",
        "file_count": result.get("file_count", 0),
        "commit_sha": result.get("commit_sha", ""),
        "message": "Repository indexed successfully"
    }


# get url

@router.get("/get_url/{thread_id}/{doc_id}")
def get_url(
    thread_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verify user owns thread and document belongs to thread
        cursor.execute(
            """
            SELECT d.source
            FROM documents d
            JOIN thread_documents td ON d.doc_id = td.doc_id
            JOIN threads t ON td.thread_id = t.thread_id
            WHERE d.type = 'web'
              AND d.doc_id = ?
              AND td.thread_id = ?
              AND t.user_id = ?
            """,
            (doc_id, thread_id, user_id)
        )
        row = cursor.fetchone()

    if not row or not row[0]:
        raise HTTPException(
            status_code=404,
            detail="URL not found for this thread"
        )

    return {"url": row[0]}

    

    



BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_pdfs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# upload pdf endpoint
@router.post("/upload-pdf") # done
async def upload_pdf(
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    # 2. Read PDF first (before acquiring DB connection)
    content = await file.read()
    from app.utils.hash_utils import hash_bytes
    doc_hash = hash_bytes(content)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Verify thread belongs to authenticated user

        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        # 3. Check whether THIS USER already has this document

        cursor.execute(
            """
            SELECT
                doc_id,
                vectorstore_path,
                source
            FROM documents
            WHERE content_hash = ?
              AND user_id = ?
            """,
            (
                doc_hash,
                user_id
            )
        )

        user_document = cursor.fetchone()

        # CASE 1:
        # Same user already owns this document
        
        if user_document:

            doc_id = user_document[0]

            cursor.execute(
                """
                INSERT OR IGNORE INTO thread_documents
                (
                    thread_id,
                    doc_id
                )
                VALUES (?, ?)
                """,
                (
                    thread_id,
                    doc_id
                )
            )

            clear_thread_retriever_cache(thread_id)

            return {
                "status": "reused",
                "doc_id": doc_id,
                "message": "Document already exists for this user and was linked to the thread."
            }

        # 4. Check whether the physical document already exists
        #    for ANOTHER user

        cursor.execute(
            """
            SELECT
                doc_id,
                source,
                vectorstore_path
            FROM documents
            WHERE content_hash = ?
            LIMIT 1
            """,
            (doc_hash,)
        )

        existing_document = cursor.fetchone()

        # CASE 2:
        # Same PDF exists for another user
        #
        # Reuse physical PDF + vectorstore,
        # but create a NEW documents row for this user.

        if existing_document:

            existing_doc_id = existing_document[0]
            file_path = existing_document[1]
            vectorstore_path = existing_document[2]

            # New document record for current user
            doc_id = str(uuid.uuid4())

            cursor.execute(
                """
                INSERT INTO documents (
                    doc_id,
                    user_id,
                    type,
                    content_hash,
                    source,
                    vectorstore_path,
                    filename
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    user_id,
                    "pdf",
                    doc_hash,
                    file_path,
                    vectorstore_path,
                    file.filename
                )
            )

            # Link user's thread to user's document record
            cursor.execute(
                """
                INSERT INTO thread_documents (
                    thread_id,
                    doc_id
                )
                VALUES (?, ?)
                """,
                (
                    thread_id,
                    doc_id
                )
            )

            clear_thread_retriever_cache(thread_id)

            return {
                "status": "reused_physical_file",
                "doc_id": doc_id,
                "message": "Existing PDF/vectorstore reused and linked to this user."
            }

        # CASE 3:
        # Completely new document

        doc_id = str(uuid.uuid4())

        file_path = os.path.join(
            "data/uploads_pdfs",
            f"{doc_hash}.pdf"
        )

        with open(file_path, "wb") as f:
            f.write(content)

        try:
            vectorstore_path = ingest_pdf(
                file_bytes=content,
                filename=file.filename,
                doc_id=doc_id
            )
        except ValueError as e:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process and index PDF: {str(e)}"
            )

        cursor.execute(
            """
            INSERT INTO documents (
                doc_id,
                user_id,
                type,
                content_hash,
                source,
                vectorstore_path,
                filename
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                user_id,
                "pdf",
                doc_hash,
                file_path,
                vectorstore_path,
                file.filename
            )
        )

        # Link document to thread

        cursor.execute(
            """
            INSERT INTO thread_documents (
                thread_id,
                doc_id
            )
            VALUES (?, ?)
            """,
            (
                thread_id,
                doc_id
            )
        )

    clear_thread_retriever_cache(thread_id)

    return {
        "status": "new",
        "doc_id": doc_id
    }

# docsument 



@router.get("/thread/{thread_id}/documents") # done
def get_thread_documents(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verify thread ownership

        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        thread = cursor.fetchone()

        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        # Get documents

        cursor.execute(
            """
            SELECT
                d.doc_id,
                d.type,
                d.source,
                d.created_at,
                d.filename
            FROM documents d
            JOIN thread_documents td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
              AND d.user_id = ?
            ORDER BY d.created_at DESC
            """,
            (thread_id, user_id)
        )

        rows = cursor.fetchall()

    documents = []

    for row in rows:
        title_or_name = row[4] or row[2] or "Document"
        documents.append({
            "doc_id": row[0],
            "type": row[1],
            "source": row[2],
            "created_at": row[3],
            "filename": title_or_name,
            "title": title_or_name,
            "status": "ready"
        })

    return {
        "thread_id": thread_id,
        "documents": documents
    }

# detail ............


@router.get("/thread/{thread_id}/details") # done
def get_thread_details(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verify thread belongs to authenticated user

        cursor.execute(
            """
            SELECT
                thread_id,
                title,
                checkpoint_synced
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        thread = cursor.fetchone()

        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        title = thread[1] or f"Chat {thread_id[:6]}"
        is_synced = bool(thread[2]) if len(thread) > 2 and thread[2] is not None else False

        # Load messages from durable storage
        stored_messages = get_thread_messages(thread_id, user_id, target_conn=conn)
        if not is_synced:
            # Check if there are any recoverable checkpoint messages missing from storage
            try:
                state = chatbot.get_state(
                    config={
                        "configurable": {
                            "thread_id": thread_id
                        }
                    }
                )
                checkpoint_messages = state.values.get("messages", []) if state else []
                if checkpoint_messages:
                    backfilled = backfill_thread_messages_from_checkpoint(
                        thread_id=thread_id,
                        user_id=user_id,
                        checkpoint_messages=checkpoint_messages,
                        target_conn=conn
                    )
                    if backfilled:
                        stored_messages = get_thread_messages(thread_id, user_id, target_conn=conn)

                # Mark checkpoint as synced so subsequent details calls read directly from storage
                cursor.execute(
                    "UPDATE threads SET checkpoint_synced = TRUE WHERE thread_id = ?",
                    (thread_id,)
                )
            except Exception as e:
                logger.warning(f"Failed to check or backfill legacy checkpoint messages: {e}")
                # Roll back the failed transaction so the connection is usable for the document query
                try:
                    conn.rollback()
                except Exception:
                    pass

        # Load thread summary
        thread_summary = get_thread_summary(thread_id, user_id=user_id, target_conn=conn)

        formatted_messages = [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in stored_messages
        ]

        # Get documents belonging to this thread

        cursor.execute(
            """
            SELECT
                d.doc_id,
                d.type,
                d.source,
                d.created_at,
                d.filename
            FROM documents d
            JOIN thread_documents td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
              AND d.user_id = ?
            ORDER BY d.created_at DESC
            """,
            (thread_id, user_id)
        )

        rows = cursor.fetchall()

    documents = []

    for row in rows:
        title_or_name = row[4] or row[2] or "Document"
        documents.append({
            "doc_id": row[0],
            "type": row[1],
            "source": row[2],
            "created_at": row[3],
            "filename": title_or_name,
            "title": title_or_name,
            "status": "ready"
        })

    return {
        "thread_id": thread_id,
        "title": title,
        "summary": thread_summary,
        "messages": formatted_messages,
        "documents": documents
    }

# get source ...........

@router.get("/thread/{thread_id}/sources") # done pending... not use till now
def get_thread_sources(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        thread = cursor.fetchone()

        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

    return thread_document_metadata(thread_id)



# get pdf 


@router.get("/get_pdf/{thread_id}/{doc_id}") # done
def get_pdf(
    thread_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verify thread belongs to user
        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        # Get specifically requested PDF
        cursor.execute(
            """
            SELECT d.source
            FROM documents d
            JOIN thread_documents td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
              AND td.doc_id = ?
              AND d.user_id = ?
              AND d.type = 'pdf'
            """,
            (thread_id, doc_id, user_id)
        )

        row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="PDF not found in this thread"
        )

    file_path = row[0]

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="PDF file not found"
        )

    return FileResponse(
        file_path,
        media_type="application/pdf"
    )



@router.get("/thread/{thread_id}/pdfs") # done thing to notic
def get_thread_pdfs(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Verify thread ownership
        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        # Get ALL PDFs belonging to this thread/user
        cursor.execute(
            """
            SELECT
                d.doc_id,
                d.filename,
                d.source,
                d.created_at
            FROM documents d
            JOIN thread_documents td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
              AND d.user_id = ?
              AND d.type = 'pdf'
            ORDER BY d.created_at ASC
            """,
            (thread_id, user_id)
        )

        rows = cursor.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No PDFs found for this thread"
        )

    pdfs = []

    for index, row in enumerate(rows, start=1):

        doc_id = row[0]
        filename=row[1]
        file_path = row[2]
        created_at=row[3]

        if not os.path.exists(file_path):
            continue

        pdfs.append({
            "doc_id": doc_id,
            "filename":filename or f"PDF {index}",
            "created_at": created_at
        })

    return {
        "thread_id": thread_id,
        "count": len(pdfs),
        "pdfs": pdfs
    }



# set youtube


@router.post("/set_youtube")  # done
def set_youtube(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    thread_id = data["thread_id"]
    youtube_url = data["youtube_url"]

    from app.utils.hash_utils import hash_string

    try:
        video_id = extract_video_id(youtube_url)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL"
        )

    doc_hash = hash_string(video_id)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        thread = cursor.fetchone()

        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        cursor.execute(
            """
            SELECT doc_id, vectorstore_path
            FROM documents
            WHERE content_hash = ?
            """,
            (doc_hash,)
        )

        row = cursor.fetchone()

        if row:
            doc_id = row[0]

            cursor.execute(
                """
                INSERT INTO thread_documents (
                    thread_id,
                    doc_id
                )
                VALUES (?, ?)
                """,
                (thread_id, doc_id)
            )

            clear_thread_retriever_cache(thread_id)

            return {
                "status": "reused",
                "doc_id": doc_id
            }

        # New YouTube document
        doc_id = str(uuid.uuid4())

        try:
            vectorstore_path = ingest_youtube(
                video_id,
                doc_id
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to ingest YouTube video transcript: {str(e)}"
            )

        # Save document with OWNER and filename
        cursor.execute(
            """
            INSERT INTO documents (
                doc_id,
                user_id,
                type,
                content_hash,
                source,
                vectorstore_path,
                filename
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                user_id,
                "youtube",
                doc_hash,
                video_id,
                vectorstore_path,
                f"YouTube ({video_id})"
            )
        )

        # Link document to thread

        cursor.execute(
            """
            INSERT INTO thread_documents (
                thread_id,
                doc_id
            )
            VALUES (?, ?)
            """,
            (thread_id, doc_id)
        )

    clear_thread_retriever_cache(thread_id)

    return {
        "status": "ok",
        "doc_id": doc_id
    }



# get youtube


@router.get("/get_youtube/{thread_id}") # done
def get_youtube(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT thread_id
            FROM threads
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id)
        )

        thread = cursor.fetchone()

        if thread is None:
            raise HTTPException(
                status_code=404,
                detail="Thread not found"
            )

        # Get YouTube videos belonging to this thread

        cursor.execute(
            """
            SELECT d.source
            FROM documents d
            JOIN thread_documents td
                ON d.doc_id = td.doc_id
            WHERE td.thread_id = ?
              AND d.user_id = ?
              AND d.type = 'youtube'
            ORDER BY d.created_at DESC
            """,
            (thread_id, user_id)
        )

        rows = cursor.fetchall()

    if not rows:
        return {
            "youtube_url": None
        }

    # Convert video IDs to YouTube URLs

    videos = [
        f"https://www.youtube.com/watch?v={row[0]}"
        for row in rows
    ]

    return {
        "thread_id": thread_id,
        "youtube_url": videos
    }



# resume chat on interput 
@router.post("/chat/resume")
def resume_chat(
    request: HITLResumeRequest,
    current_user: dict = Depends(get_current_user)
):

    thread_id = request.thread_id

    user_id = current_user["user_id"]

    decision = request.decision.lower().strip()

    # --------------------------------------------------------
    # Validate decision
    # --------------------------------------------------------

    if decision not in {"yes", "no"}:

        raise HTTPException(
            status_code=400,
            detail="Decision must be 'yes' or 'no'."
        )

    # --------------------------------------------------------
    # Verify thread ownership
    # --------------------------------------------------------

    if not verify_thread_ownership(thread_id, user_id):
        raise HTTPException(
            status_code=404,
            detail="Thread not found"
        )

    # --------------------------------------------------------
    # IMPORTANT: RESUME THE INTERRUPTED GRAPH
    # --------------------------------------------------------

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }

    try:
        result = chatbot.invoke(
            Command(
                resume=decision
            ),
            config=config
        )
    except Exception as e:
        logger.error(f"[RESUME CHAT] Error during graph resumption for thread {thread_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume graph execution: {str(e)}"
        )

    # --------------------------------------------------------
    # CHECK IF GRAPH IS STILL INTERRUPTED
    # --------------------------------------------------------
    if isinstance(result, dict) and "__interrupt__" in result:
        interrupts = result["__interrupt__"]
        interrupt_data = {}
        if interrupts:
            first_interrupt = interrupts[0]
            if hasattr(first_interrupt, "value"):
                interrupt_data = first_interrupt.value
            elif isinstance(first_interrupt, dict):
                interrupt_data = first_interrupt
        return {
            "status": "human-approval",
            "thread_id": thread_id,
            "interrupt": interrupt_data,
            "result": result
        }

    # --------------------------------------------------------
    # PERSIST FINAL ASSISTANT RESPONSE
    # --------------------------------------------------------
    messages = result.get("messages", []) if isinstance(result, dict) else []
    ai_response = "⚠️ No response generated."
    if messages:
        ai_response = extract_ai_text(messages[-1])

    # Determine message ID
    if request.message_id:
        resp_id = f"resp_{request.message_id}" if not request.message_id.startswith("resp_") else request.message_id
    else:
        # Check if the last message in this thread is already this exact assistant answer
        # to prevent duplicates upon repeated resume requests
        existing_msgs = get_thread_messages(thread_id, user_id, limit=1)
        if existing_msgs and existing_msgs[-1]["role"] == "assistant" and existing_msgs[-1]["content"] == ai_response:
            resp_id = existing_msgs[-1]["message_id"]
        else:
            resp_id = str(uuid.uuid4())

    try:
        save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content=ai_response,
            message_id=resp_id,
            strict=True,
        )
    except ValueError as e:
        logger.error(f"[RESUME CHAT] Failed to save assistant message: {e}")

    # Persist summary if generated/updated by graph upon resumption
    if isinstance(result, dict) and result.get("summary"):
        save_thread_summary(thread_id, result["summary"], user_id=user_id)

    return {
        "status": "completed",
        "thread_id": thread_id,
        "result": result
    }