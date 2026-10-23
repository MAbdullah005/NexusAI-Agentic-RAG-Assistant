import asyncio
import os
import uuid
import sqlite3
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from .schemas import (
    RepoRequest, RepoResponse, ConversationInfo, MessageInfo, RepoInfo,
    ChatRequest, ChatResponse, RegisterRequest, LoginRequest, TokenResponse,
    RefreshRequest
)
from .database import get_db
from .rag import index_repo, ask, latest_commit_sha
from .github import parse_github_url
from .llm import summarize_conversation
from .models import User, Repository, Conversation, Message, MessageSource, UserRepository, RefreshToken
from .auth import (
    password_hash, verify_password, create_access_token,
    create_refresh_token, get_valid_refresh_token, hash_token, current_user
)

router = APIRouter()

def sync_repo_to_db(user_id: int, url: str, owner: str, repo: str, thread_id: str | None = None) -> str:
    """Register the GitHub repository as an attached document in NexusAI's PostgreSQL database."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Document, ThreadDocument, utc_now

        with SessionLocal() as db:
            doc = db.query(Document).filter(
                Document.source == url,
                Document.user_id == user_id,
            ).first()

            if doc:
                doc_id = doc.doc_id
            else:
                doc_id = str(uuid.uuid4())
                new_doc = Document(
                    doc_id=doc_id,
                    user_id=user_id,
                    filename=f"{owner}/{repo}",
                    source=url,
                    type="github",
                    created_at=utc_now(),
                )
                db.add(new_doc)
                db.flush()

            if thread_id:
                td = db.query(ThreadDocument).filter(
                    ThreadDocument.thread_id == thread_id,
                    ThreadDocument.doc_id == doc_id,
                ).first()
                if not td:
                    db.add(ThreadDocument(thread_id=thread_id, doc_id=doc_id))

            db.commit()

        if thread_id:
            try:
                from app.core.retriever import clear_thread_retriever_cache
                clear_thread_retriever_cache(thread_id)
            except Exception:
                pass
        return doc_id
    except Exception as e:
        print(f"[REPO SYNC] Failed to sync document to DB: {e}")
        return str(uuid.uuid4())

sync_repo_to_sqlite = sync_repo_to_db

async def get_user_repo_access(db: AsyncSession, user_id: int, repository_id: int):
    result = await db.execute(
        select(UserRepository).where(
            UserRepository.user_id == user_id,
            UserRepository.repository_id == repository_id,
        )
    )
    return result.scalar_one_or_none()


@router.get("/")
async def root():
    return {"message": "RepoGuide running inside NexusAI"}


# POST /index and POST /upload-repo — download, filter, chunk, embed, store a repo

@router.post("/index", response_model=RepoResponse)
@router.post("/upload-repo", response_model=RepoResponse)
async def index(
    request: RepoRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)]
):
    try:
        info = parse_github_url(request.url)
        owner, repo_name = info["owner"], info["repo"]

        existing_repo = (await db.execute(
            select(Repository).where(
                Repository.owner == owner,
                Repository.repo_name == repo_name,
            )
        )).scalar_one_or_none()

        if existing_repo is not None:
            access = await get_user_repo_access(db, user.id, existing_repo.id)
            if access is not None:
                doc_id = sync_repo_to_sqlite(user.id, request.url, owner, repo_name, request.thread_id)
                return RepoResponse(
                    url=request.url,
                    status="success",
                    message="Repository already indexed and accessible",
                    file_count=0,
                    doc_id=doc_id,
                )

            current_sha = await asyncio.to_thread(
                latest_commit_sha, owner, repo_name, existing_repo.branch
            )
            file_count = 0
            if current_sha != existing_repo.commit_sha:
                result = await index_repo(request.url)
                existing_repo.commit_sha = result["commit_sha"]
                existing_repo.status = "indexed"
                file_count = result["file_count"]

            db.add(UserRepository(user_id=user.id, repository_id=existing_repo.id))
            await db.commit()
            doc_id = sync_repo_to_sqlite(user.id, request.url, owner, repo_name, request.thread_id)
            return RepoResponse(
                url=request.url,
                status="success",
                message="Repository indexed successfully" if file_count else "Repository already indexed and accessible",
                file_count=file_count,
                doc_id=doc_id,
            )

        result = await index_repo(request.url)
        new_repo = Repository(
            github_url=request.url,
            owner=result["owner"],
            repo_name=result["repo"],
            branch=result["branch"],
            commit_sha=result["commit_sha"],
            status="indexed",
        )
        db.add(new_repo)
        await db.flush()
        db.add(UserRepository(user_id=user.id, repository_id=new_repo.id))
        await db.commit()

        doc_id = sync_repo_to_sqlite(user.id, request.url, owner, repo_name, request.thread_id)

        return RepoResponse(
            url=request.url,
            status="success",
            message="Repository indexed successfully",
            file_count=result["file_count"],
            doc_id=doc_id,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/repositories", response_model=list[RepoInfo])
async def get_repositories(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    try:
        result = await db.execute(
            select(Repository)
            .join(UserRepository, UserRepository.repository_id == Repository.id)
            .where(UserRepository.user_id == user.id)
        )
        repositories = result.scalars().all()
        return repositories
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/repositories/{repo_id}", response_model=RepoInfo)
async def get_repository(repo_id: int, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    try:
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repository = result.scalar_one_or_none()
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        access = await get_user_repo_access(db, user.id, repo_id)
        if access is None:
            raise HTTPException(status_code=403, detail="Not authorized to access this repository")
        return repository
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/conversations", response_model=list[ConversationInfo])
async def get_all_conversations(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    try:
        result = await db.execute(select(Conversation).where(Conversation.user_id == user.id))
        conversations = result.scalars().all()
        return conversations
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/conversations/{repo_id}", response_model=list[ConversationInfo])
async def get_conversations(repo_id: int, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    try:
        repo = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = repo.scalar_one_or_none()
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        access = await get_user_repo_access(db, user.id, repo_id)
        if access is None:
            raise HTTPException(status_code=403, detail="Not authorized to access this repository")
        result = await db.execute(select(Conversation).where(
            Conversation.repository_id == repo_id,
            Conversation.user_id == user.id,
        ))
        conversations = result.scalars().all()
        return conversations
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/messages/{conversation_id}", response_model=list[MessageInfo])
async def get_messages(conversation_id: int, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    try:
        conversation = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = conversation.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
        result = await db.execute(select(Message).options(selectinload(Message.sources)).where(
            Message.conversation_id == conversation_id,
            Message.role != "summary",
        ).order_by(Message.created_at))
        messages = result.scalars().all()
        return messages
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/chat", response_model=ChatResponse)
async def repo_chat(request: ChatRequest, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    repo = await db.execute(select(Repository).where(Repository.github_url == request.url))
    repo = repo.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    access = await get_user_repo_access(db, user.id, repo.id)
    if access is None:
        raise HTTPException(status_code=403, detail="Not authorized to access this repository")
    conversation = None
    if request.conversation_id != 0:
        conversation = await db.execute(select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user.id,
        ))
        conversation = conversation.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.repository_id != repo.id:
            raise HTTPException(status_code=404, detail="Conversation does not belong to this repository")

    try:
        RETAIN = 8
        history = []
        if conversation is not None:
            all_msgs = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )).scalars().all()
            summary_row = None
            raw_msgs = []
            for m in all_msgs:
                if m.role == "summary":
                    summary_row = m
                else:
                    raw_msgs.append(m)

            overflow = len(raw_msgs) + 2 - RETAIN
            if overflow > 0:
                cohort = raw_msgs[:overflow]
                new_summary = await asyncio.to_thread(
                    summarize_conversation,
                    summary_row.content if summary_row else "",
                    [{"role": m.role, "content": m.content} for m in cohort],
                )
                if summary_row:
                    summary_row.content = new_summary
                else:
                    db.add(Message(
                        conversation_id=conversation.id,
                        role="summary",
                        content=new_summary,
                    ))
                raw_msgs = raw_msgs[overflow:]

            history = [{"role": "summary", "content": summary_row.content}] if summary_row else []
            history += [
                {"role": m.role, "content": m.content}
                for m in raw_msgs[-RETAIN:]
            ]

        result = await ask(request.question, request.url, history=history)
        if conversation is None:
            conversation = Conversation(repository_id=repo.id, title=repo.repo_name, user_id=user.id)
            db.add(conversation)
            await db.flush()

        question_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.question,
        )
        answer_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result["answer"],
        )
        db.add_all([question_message, answer_message])
        await db.flush()

        for s in result["sources"]:
            db.add(MessageSource(
                message_id=answer_message.id,
                file_path=s["file_path"],
                start_line=s["start_line"],
                end_line=s["end_line"],
                commit_sha=s["commit_sha"],
                score=s["score"],
            ))
        await db.commit()
        return ChatResponse(
            answer=result["answer"],
            conversation_id=conversation.id,
            sources=result["sources"],
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Register a new user and return a JWT token"""
    try:
        existing_user = await db.execute(select(User).where(User.username == request.username))
        existing_user = existing_user.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        hashed_password = password_hash(request.password)
        new_user = User(username=request.username, password_hash=hashed_password)
        db.add(new_user)
        await db.flush()
        token = create_access_token(new_user.id)
        refresh_token = await create_refresh_token(db, new_user.id)
        await db.commit()
        return TokenResponse(access_token=token, refresh_token=refresh_token, token_type="bearer")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Login a user and return a JWT token"""
    try:
        user = await db.execute(select(User).where(User.username == request.username))
        user = user.scalar_one_or_none()
        password_valid = verify_password(request.password, user.password_hash) if user else False
        if not user or not password_valid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
        token = create_access_token(user.id)
        refresh_token = await create_refresh_token(db, user.id)
        await db.commit()
        return TokenResponse(access_token=token, refresh_token=refresh_token, token_type="bearer")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Exchange a valid refresh token for a new access token (rotating the refresh token)"""
    try:
        row = await get_valid_refresh_token(db, request.refresh_token)
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
        row.revoked = True
        token = create_access_token(row.user_id)
        refresh_token = await create_refresh_token(db, row.user_id)
        await db.commit()
        return TokenResponse(access_token=token, refresh_token=refresh_token, token_type="bearer")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/logout", response_model=TokenResponse)
async def logout(request: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Revoke a refresh token so it can no longer be used"""
    try:
        row = await get_valid_refresh_token(db, request.refresh_token)
        if row is not None:
            row.revoked = True
            await db.commit()
        return TokenResponse(access_token="", refresh_token="", token_type="bearer")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router)
