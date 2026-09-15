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
from app.services.youtube_ingest import ingest_youtube
from app.auth.dependencies import get_current_user

from app.utils.logger import get_logger
from app.core.retriever import thread_document_metadata
from app.graph.agent_graph import chatbot
from app.services.pdf_ingest import ingest_pdf
from app.utils.common import extract_ai_text
from app.memory.sqlite_memory import  get_thread_title_db, save_thread_title
from app.llm.title_generator import generate_chat_title
from langgraph.checkpoint.sqlite import SqliteSaver
from fastapi import HTTPException
logger = get_logger(__name__)

router = APIRouter()

DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "chatbot_conv.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)

checkpointer = SqliteSaver(conn=conn)


#  Chat Endpoint 

@router.post("/chat") # done
async def chat_endpoint(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    user_input = data["message"]
    thread_id = data["thread_id"]


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

    # LangGraph configuration

    CONFIG = {
        "configurable": {
            "thread_id": thread_id
        },
        "run_name": "chat_turn",
    }

    # Run chatbot

    response = chatbot.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ]
        },
        config=CONFIG,
    )

    ai_response = extract_ai_text(
        response["messages"][-1]
    )

    return {
        "thread_id": thread_id,
        "response": ai_response
    }


#  Threads 

@router.get("/threads") # done
def get_threads(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

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
        result.append({
            "thread_id": row[0],
            "title": row[1] or f"Chat {row[0][:6]}",
            "created_at": row[2]
        })

    return result


#  New Thread 

@router.post("/new-thread") # done
def new_thread(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    thread_id = str(uuid.uuid4())

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO threads (
            thread_id,
            user_id,
            title
        )
        VALUES (?, ?, ?)
        """,
        (
            thread_id,
            user_id,
            "New Chat"
        )
    )

    conn.commit()

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

    web_info=ingest_web(url=url,
                        doc_id=doc_id,
                        thread_id=thread_id)

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
    
    conn.commit()
    clear_thread_retriever_cache(thread_id=thread_id)

    return {"status":"new",
            "doc_id":doc_id,
            "title":web_info["title"]
            }




# get url

@router.get("get_url/{thread_id}/{doc_id}")
def get_url(thread_id:str,
            doc_id:str,
            current_user:dict=Depends(get_current_user)):
    user_id=current_user["user_id"]
    cursor=conn.cursor()
    # verify user belong to that therad

    cursor.execute("""
SELECT thread_id,
doc_id,
WHERE thread_id=?,
doc_id=?
""",
(thread_id,doc_id)
)
    if cursor.fetchall() is None:
        raise HTTPException(
            status_code=404,
            detail="Thread not found"
        )

    cursor.execute("""
SELECT d.source
from documents as d
WHERE d.type="web"
AND d.user_id=?
AND d.doc_id=?
AND d.thread_id=?
""",(user_id,doc_id,thread_id)
)
    row=cursor.fetchall()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="URL not found for this Thread"
        )

    url_source=row[0]
    if url_source is None:
        raise HTTPException(
            status_code=404,
            detail="URL Not found for this thread"
        )

    return {"url":url_source}

    

    



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

    # 2. Read PDF

    content = await file.read()

    from app.utils.hash_utils import hash_bytes

    doc_hash = hash_bytes(content)

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

        conn.commit()

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

        conn.commit()

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


    vectorstore_path = ingest_pdf(
        file_bytes=content,
        filename=file.filename,
        doc_id=doc_id
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

    conn.commit()

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
            d.created_at
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
        documents.append({
            "doc_id": row[0],
            "type": row[1],
            "source": row[2],
            "created_at": row[3]
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

    cursor = conn.cursor()

    # Verify thread belongs to authenticated user

    cursor.execute(
        """
        SELECT
            thread_id,
            title
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

    # Get LangGraph messages

    state = chatbot.get_state(
        config={
            "configurable": {
                "thread_id": thread_id
            }
        }
    )

    messages = state.values.get("messages", [])

    formatted_messages = []

    for msg in messages:

        role = (
            "user"
            if isinstance(msg, HumanMessage)
            else "assistant"
        )

        formatted_messages.append(
            {
                "role": role,
                "content": msg.content
            }
        )

    # Get documents belonging to this thread

    cursor.execute(
        """
        SELECT
            d.doc_id,
            d.type,
            d.source
        FROM documents d
        JOIN thread_documents td
            ON d.doc_id = td.doc_id
        WHERE td.thread_id = ?
          AND d.user_id = ?
        """,
        (thread_id, user_id)
    )

    rows = cursor.fetchall()

    documents = []

    for row in rows:

        documents.append({
            "doc_id": row[0],
            "type": row[1],
            "source": row[2]
        })


    return {
        "thread_id": thread_id,
        "title": title,
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


    from app.utils.hash_utils import hash_string

    video_id = extract_video_id(youtube_url)

    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL"
        )

    doc_hash = hash_string(video_id)

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
            INSERT  INTO thread_documents (
                thread_id,
                doc_id
            )
            VALUES (?, ?)
            """,
            (thread_id, doc_id)
        )

        conn.commit()

        clear_thread_retriever_cache(thread_id)

        return {
            "status": "reused",
            "doc_id": doc_id
        }

    # New YouTube document

    doc_id = str(uuid.uuid4())

    vectorstore_path = ingest_youtube(
        video_id,
        doc_id
    )

    # Save document with OWNER

    cursor.execute(
        """
        INSERT INTO documents (
            doc_id,
            user_id,
            type,
            content_hash,
            source,
            vectorstore_path
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            user_id,
            "youtube",
            doc_hash,
            video_id,
            vectorstore_path
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

    conn.commit()

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
