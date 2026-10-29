# NexusAI Project Guide

This guide explains the project from the beginning: what the application does, how a request moves through it, and what each maintained file is responsible for. It is written for someone who is new to this codebase.

> **Scope note:** This repository contains application code as well as many generated or user-provided files. Source code, configuration, tests, and checked-in documentation are listed individually below. Repeated FAISS index files, PDFs, database snapshots, and logs are explained by file pattern because each copy has the same technical purpose and may contain private conversation or document data. Local environment files and virtual environments are not source code; never publish their secrets.

## 1. What this project does

NexusAI is a web chat application with a Python/FastAPI backend and a Next.js/React frontend. A user signs in, creates a chat thread, and asks questions. The assistant can use a language model, retrieve information from PDFs, web pages, YouTube transcripts, and GitHub repositories attached to the thread, and use tools such as web search or a calculator. It stores conversations and source metadata so a user can return to a thread later.

The project also contains **RepoGuide**, a GitHub repository question-answering feature. RepoGuide downloads and indexes a GitHub repository, searches its code, and generates answers grounded in the matching code.

### Important terms

- **API:** The backend's HTTP interface. The browser sends requests to API routes and receives JSON responses.
- **Thread:** One saved conversation. Messages, summary, and attached sources belong to a thread.
- **RAG (retrieval-augmented generation):** Search source material first, then give relevant excerpts to the language model so its answer can be grounded in that material.
- **Chunk:** A smaller piece of a long document or source file. Chunks are easier to search than entire documents.
- **Embedding:** A list of numbers representing the meaning of text; similar meanings can be found with vector search.
- **FAISS:** A local vector-index format used to search embedded PDF, web, and YouTube content.
- **BM25 / full-text search:** Keyword-based search that complements semantic vector search.
- **LangGraph:** The workflow engine connecting the assistant, tools, retrieval, approval, and final-answer steps.
- **CRAG:** The retrieval quality check that decides whether the retrieved evidence is good enough or whether another path is needed.
- **HITL:** “Human in the loop.” The graph can pause and ask the user to approve a web search before it continues.
- **JWT:** A signed token the frontend presents to authenticated API endpoints.
- **RepoGuide index:** PostgreSQL/pgvector records representing GitHub source-file chunks and their embeddings.

## 2. How the main pieces connect

```text
Browser (Next.js)
  ├─ login/signup pages and authentication state
  └─ chat, thread sidebar, source uploads, document viewers
                 │ HTTP requests + bearer token
                 ▼
FastAPI application (main.py)
  ├─ authentication routes
  ├─ chat/thread/source routes
  └─ RepoGuide routes
         │
         ├─ Chat graph (LangGraph)
         │    ├─ LLM chat node
         │    ├─ tools (RAG, web search, calculator, stocks, Python)
         │    ├─ document relevance grading and optional user approval
         │    └─ final response and memory summarization
         │
         ├─ Source ingestion → split text → embeddings → FAISS indexes
         └─ SQLite-compatible conversation/source storage and checkpoints

RepoGuide route → GitHub download/filter/chunk/embed → PostgreSQL + pgvector
                → hybrid search → context expansion/reranking → grounded answer
```

### Typical chat request

1. The frontend obtains the user's saved access token and calls the chat API.
2. The backend verifies the token and checks that the user owns the requested thread.
3. It saves the user message, then invokes the LangGraph chatbot with the thread and selected source IDs.
4. The graph lets the model answer directly or call a tool. For attached sources, the unified RAG tool retrieves relevant chunks.
5. The graph grades retrieved evidence. If it is insufficient, it can pause for human approval before web search.
6. The API saves a completed assistant response (but not an incomplete answer when the graph pauses) and returns the status to the frontend.
7. Conversation history, summaries, and checkpoints allow the thread to continue later.

## 3. Repository layout at a glance

- `app/` — Python backend and RepoGuide implementation.
- `frontend/` — Next.js pages, React components, API client, and frontend configuration.
- `tests/` — backend automated tests.
- `scripts/` — project scaffolding and data-migration utilities.
- `data/` — source uploads and local vector indexes.
- `database/` — SQLite conversation database and backups.
- `logs/` — application log output.
- Root configuration and startup files — dependency lists, environment templates, and FastAPI entry point.

## 4. Root files

- `main.py` — Creates the FastAPI application, configures CORS, and mounts the main chat API, authentication API, and RepoGuide API. This is the module used by `uvicorn main:app`.
- `requirements.txt` — Python package dependencies for the main backend (FastAPI, LangChain/LangGraph, database adapters, model providers, document processing, and related libraries).
- `.env.example` — Example environment-variable names and placeholder values for database, model, email, JWT, search, and frontend configuration. Copy it to a local `.env` and replace placeholders; do not commit real keys.
- `.env` — Local runtime settings, if present. It can contain credentials and is not a file to document by value, share, or commit.
- `.gitignore` — Tells Git which local/generated files should not be tracked, such as secrets, virtual environments, caches, and build artifacts.
- `README.md` — The main setup guide, feature summary, architecture diagram, API overview, configuration reference, and test instructions.
- `alembic.ini` — Alembic migration configuration at the repository root. It configures database migration tooling for the main application setup.
- `__init__.py` — Empty root package marker; it does not contain application logic.
- `test.py` — A manual web-ingestion smoke test. It sends a fixed Wikipedia URL through `ingest_web`, then prints the extracted title, source/type, vector-store path, document ID, content hash, and content. Running it can make a network request and create/update a local index.
- `check.py` — A small manual inspection script that calls `thread_document_metadata` for a fixed thread ID and prints the source types. Its older commented-out sample shows how SQLite/checkpoint data was inspected.
- `template.py` — A legacy project-structure generator. It creates a predefined set of directories and empty placeholder files; that template does not match the current project layout in every detail.
- `garbage.py` — Empty Python file; it currently has no behavior.
- `test1.ipynb` — Jupyter notebook for interactive experiments. Notebook cells are exploratory rather than part of the production server.
- `projecrguide.md` — Existing misspelled, empty guide file. The requested guide is this correctly named `projectguide.md`.

## 5. Main backend: `app/`

### Package markers

- `app/__init__.py` — Marks `app` as a Python package.
- `app/api/__init__.py` — Marks the API package.
- `app/auth/__init__.py` — Marks the authentication package.
- `app/core/__init__.py` — Marks the source-processing and retrieval package.
- `app/db/__init__.py` — Marks the database package.
- `app/graph/__init__.py` — Marks the LangGraph workflow package.
- `app/llm/__init__.py` — Marks model configuration code.
- `app/memory/__init__.py` — Marks conversation persistence and memory code.
- `app/services/__init__.py` — Marks document and external-service integrations.
- `app/tools/__init__.py` — Marks agent tools.
- `app/utils/__init__.py` — Marks shared helper utilities.
- `app/repocore/__init__.py` — Marks RepoGuide's backend package.

### API routes — `app/api/`

- `app/api/main.py` — Smaller API application/entry-point module for the chat API package. The repository's root `main.py` is the combined application entry point.
- `app/api/routes.py` — Defines the main chat and thread endpoints: chat execution/resume, thread creation and history, title generation, PDF/URL/YouTube ingestion, source listing, and source-file retrieval. It checks user/thread ownership, persists messages, invokes the graph, and translates graph interrupts into API responses.

### Authentication — `app/auth/`

- `app/auth/dependencies.py` — FastAPI dependencies that read and validate the incoming bearer token and provide the authenticated user to protected routes.
- `app/auth/email_service.py` — Configures outgoing email delivery for verification and password-reset messages.
- `app/auth/jwt_utils.py` — Creates and validates JSON Web Tokens used to authenticate requests.
- `app/auth/routes.py` — HTTP endpoints for signup, email verification, login, current-user lookup, forgotten-password requests, and password reset.
- `app/auth/security.py` — Password security helpers, such as hashing passwords and checking a submitted password against its stored hash.
- `app/auth/test_mail.py` — Manual email-service test/helper; not an application route or normal automated test suite.
- `app/auth/token_utils.py` — Helpers for creating, validating, and managing authentication tokens used by the auth flow.

### Source ingestion and retrieval — `app/core/`

- `app/core/retriever.py` — Builds and caches a retriever for documents attached to a thread. It loads FAISS indexes, combines results across sources, and supports semantic plus keyword-style retrieval, document filtering, and source metadata.
- `app/core/source_router.py` — Detects whether a question mentions PDF/document/file content or YouTube/video/transcript content and returns the matching source kind. If it is ambiguous or neither applies, it returns no source kind.
- `app/core/splitter.py` — Splits long source text into smaller, overlapping chunks and keeps chunk metadata needed for citations.
- `app/core/vectorstore.py` — Shared helpers for creating, saving, loading, or managing FAISS vector stores.
- `app/core/web_processor.py` — Processes fetched web-page content into normalized document data and indexed chunks; this is the processing path used by `test.py`.

### Database — `app/db/`

- `app/db/connection_adapter.py` — Provides a common database connection interface so code can work with the configured database backend through a consistent API.
- `app/db/models.py` — Defines the main application's database entities/tables and their relationships (users, threads, messages, source documents, and related records).
- `app/db/session.py` — Creates database sessions/connections and the LangGraph checkpointer used to persist workflow state.

### API data schemas — `app/schemas/`

- `app/schemas/auth_schema.py` — Pydantic models for authentication request and response data, including the fields and validation rules expected by auth endpoints.
- `app/schemas/chat.py` — Pydantic models describing chat/thread API payloads and responses.
- `app/schemas/resume_chat.py` — Pydantic model for resuming an interrupted chat, including the user's approval/decline decision.

### Chat graph — `app/graph/`

- `app/graph/agent_graph.py` — Assembles the LangGraph state machine and its conditional routes. It decides when to call tools, grade RAG evidence, ask for approval, produce a final answer, or summarize old conversation history.
- `app/graph/crag_grader.py` — Evaluates whether retrieved source chunks are relevant enough to answer the current question and records the retrieval grade.
- `app/graph/fin_ans.py` — Produces the user-facing final response from the available conversation and retrieved evidence.
- `app/graph/hitl.py` — Pauses the graph and requests a human decision, typically whether the assistant may continue with web search.
- `app/graph/message_cleanup.py` — Removes internal tool messages/artifacts or otherwise normalizes graph messages before they are exposed as conversation history.
- `app/graph/nodes.py` — Implements the main model/chat node. It assembles system instructions, source metadata, summaries, historical context, and messages before asking the LLM what to do next.
- `app/graph/not_found.py` — Produces a response for the case where the attached sources do not contain enough information and web search was not approved or is unavailable.
- `app/graph/state.py` — Defines the typed state shared by graph nodes, including messages, retrieval results, approval decisions, and memory fields.
- `app/graph/tool_node.py` — Defines the tools available to the chat model and executes requested tool calls.
- `app/graph/web_serach.py` — Implements the web-search graph node (the filename contains the existing spelling `serach`). It performs the approved search and returns results to the graph.
- `app/graph/graph_vis_1.png` — Image visualization of a graph/workflow version; documentation/diagnostic asset, not executable code.
- `app/graph/graph_vis_2.png` — Another graph/workflow visualization image.

### Model configuration — `app/llm/`

- `app/llm/embeddings.py` — Selects/configures the text-embedding model used to turn sources and queries into vectors.
- `app/llm/llm_config.py` — Selects and configures the chat-model provider and model settings, including configured fallbacks.
- `app/llm/title_generator.py` — Uses the model to generate a short title for a new conversation from its first message.

### Conversation memory — `app/memory/`

- `app/memory/config.py` — Reads and validates environment-driven memory and RAG settings, including summary thresholds, retrieval limits, and chunk/retrieval options.
- `app/memory/historical_retriever.py` — Searches older messages in the same conversation using semantic and keyword ranking, merges rankings, filters duplicates/current messages, and formats relevant history for the model.
- `app/memory/postgres_memory.py` — Persistence helpers for messages, thread ownership, summaries, titles, source-related data, and message embeddings using the configured SQLAlchemy database.
- `app/memory/sqlite_memory.py` — SQLite persistence implementation/helpers used by SQLite-based application paths and compatibility workflows.
- `app/memory/stm.py` — Short-term conversation-memory operations, including summarizing longer chat histories and retaining recent messages.
- `app/memory/thread_titles.py` — Helpers for reading/writing or maintaining thread titles.

### Model prompts — `app/prompts/`

- `app/prompts/chat.py` — System instructions for the general assistant: behavior, tool usage, thread/source context, and answer expectations.
- `app/prompts/mem.py` — Instructions used when summarizing conversation history into persistent memory.
- `app/prompts/rag.py` — Instructions for answering from retrieved documents and formatting source-grounded/cited answers.

### Ingestion and external services — `app/services/`

- `app/services/email.py` — Email-related service functions used by application flows.
- `app/services/pdf_ingest.py` — Extracts text/metadata from uploaded PDFs, splits it into chunks, embeds it, and stores the resulting index/source metadata.
- `app/services/web_loader.py` — Fetches and extracts readable text and metadata from a web URL.
- `app/services/youtube_ingest.py` — Retrieves a YouTube transcript, prepares it as source content, and indexes it.
- `app/services/youtube_loader.py` — YouTube URL/video-ID parsing and transcript-loading helpers used by ingestion and API code.

### Agent tools — `app/tools/`

- `app/tools/calculator_tool.py` — Exposes arithmetic/calculation as a callable assistant tool.
- `app/tools/python_executor.py` — Exposes Python execution as an assistant tool. Treat execution of untrusted code as a security-sensitive operation.
- `app/tools/search_tool.py` — Exposes external web search to the graph, using the configured search service.
- `app/tools/stock_tool.py` — Fetches stock quote/market information through its configured external provider.
- `app/tools/unified_rag_tool.py` — Agent-facing retrieval tool. It searches sources attached to the current thread and returns relevant context with metadata suitable for citations.

### Shared helpers — `app/utils/`

- `app/utils/common.py` — General-purpose helpers shared by application modules, including extraction/normalization of model output.
- `app/utils/hash_utils.py` — Hashing helpers for stable content identifiers or duplicate detection.
- `app/utils/logger.py` — Configures structured/request-aware logging and helper methods for timing, agent steps, and tool usage.
- `app/utils/thread_utils.py` — Helpers for generating thread IDs, manipulating thread lists, checking thread existence, and converting messages into UI-friendly formats.

## 6. RepoGuide backend: `app/repocore/`

RepoGuide is a separate feature area mounted by root `main.py`. It indexes GitHub source files and answers questions by searching the indexed code.

### RepoGuide application and logic

- `app/repocore/README.md` — RepoGuide feature overview, setup notes, and architecture description. Some paths/versions in this feature README may describe a different deployment layout than the current integrated repository.
- `app/repocore/main.py` — FastAPI routes for indexing repositories, listing accessible repositories/conversations, managing RepoGuide conversations, and asking repository questions. It also synchronizes repository sources with NexusAI thread/source records.
- `app/repocore/auth.py` — RepoGuide authentication helpers: password verification/hashing, access and refresh token creation/validation, and current-user dependency.
- `app/repocore/config.py` — Loads RepoGuide database, model, embedding, GitHub, and reranking settings from environment variables.
- `app/repocore/database.py` — Creates RepoGuide's asynchronous SQLAlchemy database engine/session and provides its FastAPI database dependency.
- `app/repocore/models.py` — SQLAlchemy models for RepoGuide users, repositories, access relationships, conversations, messages, source references, and refresh tokens.
- `app/repocore/schemas.py` — Pydantic request/response types and input validation for RepoGuide endpoints.
- `app/repocore/github.py` — Parses GitHub repository URLs, obtains repository metadata, downloads source files, filters unsuitable files, and handles GitHub API access.
- `app/repocore/file_filter.py` — Determines which repository files should be indexed and which generated, binary, or irrelevant files should be skipped.
- `app/repocore/chunking.py` — Splits repository files into line-aware chunks and attaches file path/line/commit metadata for search results and source links.
- `app/repocore/embeddings.py` — Creates vectors for repository code chunks and user search queries.
- `app/repocore/vector_storage.py` — Stores and searches repository chunks in PostgreSQL/pgvector. It supports semantic queries, file-path matching, keyword/full-text search, and synchronous/asynchronous access helpers.
- `app/repocore/reranking.py` — Optionally reorders candidate code chunks using a reranking service/model so the most useful evidence is passed to the answer generator.
- `app/repocore/llm.py` — Configures the RepoGuide language model and generates grounded explanations and conversation summaries.
- `app/repocore/prompts.py` — System/task prompts that constrain repository answers to retrieved source context and guide conversation summaries.
- `app/repocore/rag.py` — Coordinates the RepoGuide indexing and question-answering pipelines: download/filter, chunk/embed/store, hybrid retrieval, neighboring-code expansion, reranking, and answer generation.
- `app/repocore/requirements.txt` — Dependency list for the RepoGuide feature/deployment. The root requirements file is the main integrated-backend dependency manifest.

### RepoGuide database migrations

- `app/repocore/alembic.ini` — Alembic configuration for RepoGuide's database schema migrations.
- `app/repocore/alembic/README` — Short explanation of the Alembic migration directory.
- `app/repocore/alembic/env.py` — Connects Alembic to RepoGuide's model metadata and database configuration when migrations run.
- `app/repocore/alembic/script.py.mako` — Template used by Alembic when generating a new migration script.
- `app/repocore/alembic/versions/5a91aeca01ba_ceate_initial_tables.py` — Initial RepoGuide tables (the existing filename says `ceate`); establishes the first schema revision.
- `app/repocore/alembic/versions/16ae8f1b33a1_add_user_repositories_and_remove_user_.py` — Adds/changes repository ownership and user-to-repository access relationships.
- `app/repocore/alembic/versions/6f83a1c2dd41_unique_repository_github_url.py` — Adds a uniqueness rule for a repository's GitHub URL/identity.
- `app/repocore/alembic/versions/7a1c4f3e8b2d_create_message_sources.py` — Adds schema support for associating conversation messages with source references.
- `app/repocore/alembic/versions/c4b1a8f90123_update_embedding_dimensions_to_gemini.py` — Adjusts stored vector dimensions for the configured Gemini embedding model.
- `app/repocore/alembic/versions/d5bf5270848c_add_refresh_tokens_table.py` — Adds persistent refresh-token storage for authentication.
- `app/repocore/alembic/versions/df181132cd96_add_pgvector_chunks_table.py` — Adds the pgvector-backed repository-chunk storage table.
- `app/repocore/alembic/versions/e7c3d91a2b4f_add_full_text_search_on_chunks.py` — Adds database full-text search support for indexed chunks.
- `app/repocore/alembic/versions/f8a2b3c4d5e6_create_nexusai_unified_tables.py` — Adds/updates schema objects that allow RepoGuide and NexusAI to share or synchronize selected data.

## 7. Frontend: `frontend/`

### Frontend configuration and assets

- `frontend/package.json` — Names the Next.js app, lists JavaScript dependencies, and defines development/build/start/lint/test commands.
- `frontend/package-lock.json` — Exact npm dependency resolution used for repeatable installs. Normally update this through npm when dependencies change.
- `frontend/next.config.mjs` — Next.js build/runtime configuration.
- `frontend/next-env.d.ts` — Type declarations generated/maintained for Next.js integration; usually not edited by hand.
- `frontend/postcss.config.js` — Configures PostCSS, including Tailwind CSS processing.
- `frontend/tailwind.config.js` — Tailwind theme/content configuration used when generating utility CSS.
- `frontend/tsconfig.json` — TypeScript compiler settings and file inclusion rules.
- `frontend/tsconfig.tsbuildinfo` — TypeScript incremental-build cache; generated build metadata, not application logic.
- `frontend/NexusAI Connected Logo Emblem.png` — Branding image asset used by the frontend/design.
- `frontend/Screenshot.png` — Project screenshot/visual reference.
- `frontend/public/nexus-logo.png` — Publicly served NexusAI logo asset.

### Pages and global layout — `frontend/src/app/`

- `frontend/src/app/layout.tsx` — Root Next.js layout. Sets shared document metadata and wraps pages in common application providers.
- `frontend/src/app/globals.css` — Global styles, Tailwind layers, base typography, colors, and application-wide visual rules.
- `frontend/src/app/page.tsx` — Main application/chat page. It provides the entry screen and integrates the chat workspace after authentication.
- `frontend/src/app/login/page.tsx` — Login form page; submits credentials and routes the user after successful authentication.
- `frontend/src/app/signup/page.tsx` — Account registration form and submission flow.
- `frontend/src/app/verify-email/page.tsx` — Reads the email-verification token and asks the backend to verify the new account.
- `frontend/src/app/forgot-password/page.tsx` — Form for requesting a password-reset email.
- `frontend/src/app/reset-password/page.tsx` — Form that submits a new password together with the reset token.

### Chat components — `frontend/src/components/chat/`

- `frontend/src/components/chat/ChatComposer.tsx` — Message input, send action, and composer controls for the active thread.
- `frontend/src/components/chat/ChatContainer.tsx` — Coordinates chat history, sending messages, loading states, and approval/resume behavior.
- `frontend/src/components/chat/ChatMessageItem.tsx` — Renders one chat message, including formatted assistant output and associated UI details.
- `frontend/src/components/chat/HITLBanner.tsx` — Displays the graph's human-approval request and provides approve/decline actions.
- `frontend/src/components/chat/SourceCitations.tsx` — Renders source citations/links associated with an answer.

### Sidebar — `frontend/src/components/sidebar/`

- `frontend/src/components/sidebar/Sidebar.tsx` — Thread navigation and controls for selecting/creating conversations and accessing source management.
- `frontend/src/components/sidebar/SourceIngestModal.tsx` — Modal UI for adding a PDF, web URL, YouTube source, or repository to a thread.

### Source workspace — `frontend/src/components/sources/`

- `frontend/src/components/sources/SourceWorkspace.tsx` — Lists and manages sources attached to the thread, including selecting which documents should be used for a question and opening previews.

### Reusable UI controls — `frontend/src/components/ui/`

- `frontend/src/components/ui/badge.tsx` — Small label/badge visual component.
- `frontend/src/components/ui/button.tsx` — Reusable button with shared styles/variants.
- `frontend/src/components/ui/card.tsx` — Reusable card container and card subcomponents.
- `frontend/src/components/ui/dialog.tsx` — Reusable modal/dialog primitives and accessibility behavior.
- `frontend/src/components/ui/input.tsx` — Styled reusable text input.
- `frontend/src/components/ui/tabs.tsx` — Reusable tab context, tab-list, tab-trigger, and tab-content components.
- `frontend/src/components/ui/textarea.tsx` — Styled reusable multiline text input.

### Document preview — `frontend/src/components/viewer/`

- `frontend/src/components/viewer/DocumentViewerModal.tsx` — Modal viewer for attached source content such as PDFs, web pages, or YouTube details.

### Frontend hooks, API, and shared types

- `frontend/src/hooks/useAuth.ts` — Hook exposing authentication state/actions from the auth context.
- `frontend/src/lib/api/client.ts` — Central HTTP client for backend requests. It selects the backend base URL, attaches auth credentials where needed, and exposes API calls to UI code.
- `frontend/src/lib/auth/AuthContext.tsx` — React context/provider that tracks the signed-in user and exposes login/logout/authentication actions throughout the app.
- `frontend/src/lib/auth/token.ts` — Browser-side helpers for reading, storing, and clearing the authentication token.
- `frontend/src/lib/utils.ts` — Shared frontend utilities, including class-name/style composition helpers.
- `frontend/src/middleware.ts` — Next.js request middleware for route-level checks or redirects, especially for pages that require authentication.
- `frontend/src/types/auth.ts` — TypeScript types for users, login/signup data, and authentication responses.
- `frontend/src/types/chat.ts` — TypeScript types for chat messages, threads, and chat API request/response data.
- `frontend/src/types/document.ts` — TypeScript types for attached documents/source metadata and related API data.

### Frontend utility scripts

- `frontend/scripts/db_helper.py` — Python helper script associated with local database inspection/maintenance for the frontend integration workflow; it is not part of the browser bundle.
- `frontend/scripts/e2e_integration_test.js` — End-to-end integration test script that exercises the running application through a browser/test workflow.

## 8. Tests and scripts

### Python tests — `tests/`

- `tests/test_agent.py` — Tests the assistant graph/agent behavior and its tool-routing expectations.
- `tests/test_memory_persistence.py` — Tests that conversation memory and message data persist and can be retrieved.
- `tests/test_phase2_integration.py` — Integration tests for chat message persistence, interrupted/resumed turns, idempotent retries, ownership isolation, and history behavior.
- `tests/test_phase3_memory.py` — Tests the rolling-summary/short-term memory behavior introduced in the memory phase.
- `tests/test_phase4_historical_retrieval.py` — Tests retrieval of relevant older conversation messages, ranking, filtering, and formatting.
- `tests/test_phase5_rag_quality.py` — Tests chunking, ingestion metadata, hybrid retrieval, citations, RAG prompts, relevance grading, and graph integration.
- `tests/test_rag.py` — Tests the retrieval-augmented generation path and its supporting behavior.
- `tests/test_tools.py` — Tests the callable assistant tools.

Run the Python tests from the project root using the command in `README.md`: `python -m unittest discover -s tests`.

### Scripts — `scripts/`

- `scripts/create_project_structure.py` — Creates a predefined (older) directory/file scaffold. It is a setup helper, not a required application startup command.
- `scripts/migrate_sqlite_to_postgres.py` — Copies supported records from an existing SQLite database into PostgreSQL, including timestamp conversion and corresponding database rows. Review the target database and back up data before using it.

## 9. Runtime data and generated files

These are data, indexes, caches, or logs rather than source code. Their contents can be specific to the local machine or user.

- `data/uploads_pdfs/<hash>.pdf` — Uploaded PDF originals. The hashed name is used as a stored filename/identifier.
- `data/pdf/vectorstores/<id>/index.faiss` — FAISS vector index for an ingested PDF or document source.
- `data/pdf/vectorstores/<id>/index.pkl` — FAISS document-store metadata paired with the corresponding `index.faiss`.
- `data/web/<page title>/vectorstores/<id>/index.faiss` and `index.pkl` — Vector index and document metadata for ingested web pages.
- `data/yt/vectorstores/<id>/index.faiss` and `index.pkl` — Vector index and document metadata for YouTube transcript sources.
- `database/chatbot_conv.db` — SQLite conversation/source database used by local or compatibility code paths.
- `database/chatbot_conv.db-wal` — SQLite write-ahead log; pending/recent database changes while WAL mode is active.
- `database/chatbot_conv.db-shm` — SQLite shared-memory coordination file used with the WAL.
- `database/backups/*.db` — SQLite backup snapshots. The date/phase suffix identifies the backup's purpose/time; do not treat them as code.
- `logs/app.log` — Runtime application log output. It may contain request diagnostics and should be handled as operational data.
- `__pycache__/*` and `*.pyc` — Python bytecode caches generated when modules are imported.
- `.pytest_cache/*` — Cache files created by pytest.
- `frontend/node_modules/*` (if installed) — Third-party JavaScript dependencies installed by npm; these files are not maintained application source.
- `frontend/.next/*` (if built) — Generated Next.js build/cache output.
- `myenv/*` or `.venv/*` — Local Python virtual environment and installed third-party packages.

FAISS `index.pkl` files are paired with indexes and contain serialized metadata; only load indexes created by a trusted source. Back up or remove runtime data only when you understand which local conversations and uploads depend on it.

## 10. Where to start reading the code

If you are new to the project, this order gives a practical path:

1. `README.md` — learn how to configure and run the project.
2. `main.py` — see how the backend application is assembled.
3. `app/api/routes.py` — follow a chat request from HTTP entry to graph invocation and persistence.
4. `app/graph/agent_graph.py` and `app/graph/nodes.py` — learn how the assistant decides what to do.
5. `app/tools/unified_rag_tool.py` and `app/core/retriever.py` — see how attached sources are searched.
6. `app/services/pdf_ingest.py`, `app/services/web_loader.py`, and `app/services/youtube_ingest.py` — follow how source material enters the system.
7. `app/memory/postgres_memory.py` and `app/memory/historical_retriever.py` — understand saved and recalled conversation history.
8. `frontend/src/app/page.tsx`, `frontend/src/components/chat/ChatContainer.tsx`, and `frontend/src/lib/api/client.ts` — trace the browser side of a chat request.
9. `app/repocore/main.py` and `app/repocore/rag.py` — explore the separate GitHub repository Q&A flow.
10. `tests/` — see expected behavior in executable examples.

## 11. Running the application

The exact setup requirements and environment variables are in `README.md` and `.env.example`. In short:

1. Create a Python virtual environment and install root `requirements.txt`.
2. Configure a local `.env` with the required model/database/security settings.
3. Start the backend from the repository root with `uvicorn main:app --reload`.
4. In `frontend/`, install npm dependencies and start Next.js with `npm run dev`.
5. Open the frontend in a browser. The FastAPI interactive API documentation is normally at `http://127.0.0.1:8000/docs`.

The standalone RepoGuide feature may require PostgreSQL with pgvector and its own environment settings; consult `app/repocore/README.md` and the migration files before setting up its database.
