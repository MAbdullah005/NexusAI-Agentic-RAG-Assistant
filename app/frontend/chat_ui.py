import json
import uuid

import streamlit as st
import fitz
from PIL import Image
import io

from api_client import (
    create_thread,
    get_threads,
    get_thread_details,
    get_thread_documents,
    get_thread_sources,
    send_message,
    get_thread_pdfs,
    set_youtube,
    get_youtube,
    upload_pdf,
    get_url,
    upload_url,
    generate_title,
    get_pdf,
)
from auth_ui import logout
import base64

# INITIALIZE CHAT STATE

def initialize_chat_state():

    if "message_history" not in st.session_state:
        st.session_state["message_history"] = []

    if "youtube_url" not in st.session_state:
        st.session_state["youtube_url"] = None

    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = None

    if "pdf_uploaded" not in st.session_state:
        st.session_state["pdf_uploaded"] = False

    if "youtube_loaded_for" not in st.session_state:
        st.session_state["youtube_loaded_for"] = None

    if "sources" not in st.session_state:
        st.session_state["sources"] = {}

    if "uploaded_file_name" not in st.session_state:
        st.session_state["uploaded_file_name"] = None

    if "selected_thread" not in st.session_state:
        st.session_state["selected_thread"] = None


# CREATE INITIAL THREAD

def ensure_thread():

    if st.session_state.get("thread_id"):
        return

    token = st.session_state["access_token"]

    response = create_thread(token)

    if response is None:
        st.error("Unable to connect to backend.")
        st.stop()

    if response.status_code != 200:
        st.error(
            f"Failed to create thread: "
            f"{response.text}"
        )
        st.stop()

    data = response.json()

    st.session_state["thread_id"] = data["thread_id"]


# RESET THREAD STATE

def reset_thread_state():

    st.session_state["message_history"] = []
    st.session_state["youtube_url"] = None
    st.session_state["pdf_uploaded"] = False
    st.session_state["youtube_loaded_for"] = None
    st.session_state["sources"] = {}
    st.session_state["uploaded_file_name"] = None


# CREATE NEW CHAT

def create_new_chat():

    token = st.session_state["access_token"]

    response = create_thread(token)

    if response is None:
        st.sidebar.error(
            "Unable to connect to backend."
        )
        return

    if response.status_code != 200:
        st.sidebar.error(
            "Failed to create new chat."
        )
        return

    data = response.json()

    st.session_state["thread_id"] = data["thread_id"]

    reset_thread_state()

    st.rerun()


# LOAD THREAD

def load_thread(thread_id):

    token = st.session_state["access_token"]

    response = get_thread_details(
        token,
        thread_id
    )

    if response is None:
        st.error(
            "Unable to connect to backend."
        )
        return

    if response.status_code != 200:

        # Token may have expired.
        if response.status_code == 401:
            logout()
            return

        st.error(
            f"Failed to load thread: "
            f"{response.text}"
        )
        return

    details = response.json()

    st.session_state["thread_id"] = thread_id

    st.session_state["message_history"] = (
        details.get("messages", [])
    )

    # Load YouTube

    try:

        yt_response = get_youtube(
            token,
            thread_id
        )

        if (
            yt_response is not None
            and yt_response.status_code == 200
        ):

            yt_data = yt_response.json()

            urls = yt_data.get(
                "youtube_url"
            )

            if urls:
                st.session_state["youtube_url"] = urls[0]
            else:
                st.session_state["youtube_url"] = None

    except Exception:

        st.session_state["youtube_url"] = None

    # Load PDF state

    try:

        docs_response = get_thread_documents(
            token,
            thread_id
        )

        if (
            docs_response is not None
            and docs_response.status_code == 200
        ):

            docs_data = docs_response.json()

            documents = docs_data.get(
                "documents",
                []
            )
            print("Here is the document got for this thread ", documents)

            st.session_state["pdf_uploaded"] = any(
                doc.get("type") == "pdf"
                for doc in documents
            )

    except Exception:

        st.session_state["pdf_uploaded"] = False

    st.session_state["selected_thread"] = None

    st.rerun()


# CHAT MESSAGE API

def call_chat_api(user_input, thread_id):

    token = st.session_state["access_token"]

    response = send_message(
        token,
        user_input,
        thread_id
    )

    if response is None:
        return "❌ Unable to connect to backend."

    if response.status_code == 401:
        logout()
        return "❌ Session expired. Please login again."

    if response.status_code != 200:

        try:
            detail = response.json().get(
                "detail",
                "Unknown API error"
            )
        except Exception:
            detail = response.text

        return f"❌ API Error: {detail}"

    try:

        return response.json().get(
            "response",
            "⚠️ No response"
        )

    except Exception:

        return "⚠️ Invalid response from server."


# SIDEBAR
def render_sidebar():

    token = st.session_state["access_token"]
    user = st.session_state["user"]

    st.sidebar.title(
        "LangGraph Multi-Tool Chatbot"
    )

    # User

    st.sidebar.write(
        f"👤 {user.get('email', 'User')}"
    )

    st.sidebar.divider()

    # Current Thread

    thread_id = st.session_state["thread_id"]

    if thread_id:

        st.sidebar.markdown(
            f"**Thread ID:** `{thread_id[:8]}`"
        )

    # New Chat

    if st.sidebar.button(
        "➕ New Chat",
        use_container_width=True
    ):

        create_new_chat()

    # Clear Conversation

    if st.sidebar.button(
        "🗑️ Clear Conversation",
        use_container_width=True
    ):

        st.session_state[
            "message_history"
        ] = []

        st.rerun()
    if st.sidebar.button(f"⬇️ Download Chat History",
                         use_container_width=True):
        render_download()

    st.sidebar.divider()

    # PDF

    uploaded_pdf = st.sidebar.file_uploader(
        "Upload PDF",
        type=["pdf"]
    )

    if uploaded_pdf:

        if (
            uploaded_pdf.name
            != st.session_state["uploaded_file_name"]
        ):

            response = upload_pdf(
                token,
                thread_id,
                uploaded_pdf
            )

            if response is None:

                st.sidebar.error(
                    "Unable to connect to backend."
                )

            elif response.status_code == 200:

                st.session_state[
                    "pdf_uploaded"
                ] = True

                st.session_state[
                    "uploaded_file_name"
                ] = uploaded_pdf.name

                st.sidebar.success(
                    "✅ PDF uploaded successfully"
                )

            elif response.status_code == 401:

                logout()

            else:

                try:
                    detail = response.json().get(
                        "detail",
                        "PDF upload failed."
                    )
                except Exception:
                    detail = "PDF upload failed."

                st.sidebar.error(detail)

    st.sidebar.divider()

    # YOUTUBE

    st.sidebar.subheader(
        "🎥 YouTube Video"
    )

    youtube_url = st.sidebar.text_input(
        "Paste YouTube URL",
        key="youtube_input"
    )

    if st.sidebar.button(
        "Load Video",
        use_container_width=True
    ):

        if not youtube_url:

            st.sidebar.warning(
                "Please enter a YouTube URL."
            )

        else:

            response = set_youtube(
                token,
                thread_id,
                youtube_url
            )

            if response is None:

                st.sidebar.error(
                    "Unable to connect to backend."
                )

            elif response.status_code == 200:

                st.session_state[
                    "youtube_url"
                ] = youtube_url

                st.session_state[
                    "youtube_loaded_for"
                ] = thread_id

                st.sidebar.success(
                    "✅ Video loaded successfully"
                )

            elif response.status_code == 401:

                logout()

            else:

                try:
                    detail = response.json().get(
                        "detail",
                        "Failed to load video."
                    )
                except Exception:
                    detail = "Failed to load video."

                st.sidebar.error(detail)


    ## upload URL Box

    # ============================================================
# WEBSITE URL
# ============================================================

    st.sidebar.divider()

    st.sidebar.subheader(
      "🌐 Website / Article"
    )

    website_url = st.sidebar.text_input(
      "Paste Website URL",
       placeholder="https://example.com/article",
       key="website_url_input"
    )


    if st.sidebar.button(
    "📥 Load Website",
    use_container_width=True
    ):

      if not website_url:
  
          st.sidebar.warning(
              "Please enter a website URL."
          )

      else:

        with st.sidebar.spinner(
            "Extracting website content..."
        ):

            response = upload_url(
                token=token,
                thread_id=thread_id,
                url=website_url
            )

        if response is None:

            st.sidebar.error(
                "Unable to connect to backend."
            )

        elif response.status_code == 200:

            data = response.json()

            st.sidebar.success(
                "✅ Website loaded successfully!"
            )

            st.sidebar.caption(
                f"Document ID: {data.get('doc_id', '')[:8]}"
            )

        elif response.status_code == 401:

            logout()

        else:

            try:

                detail = response.json().get(
                    "detail",
                    "Failed to load website."
                )

            except Exception:

                detail = "Failed to load website."

            st.sidebar.error(detail)


    # PAST CONVERSATIONS

    st.sidebar.divider()

    st.sidebar.subheader(
        "💬 Past Conversations"
    )

    response = get_threads(token)

    if response is not None:

        if response.status_code == 200:

            threads = response.json()

            for thread in threads:

                title = (
                    thread.get("title")
                    or f"Chat {thread['thread_id'][:6]}"
                )

                if st.sidebar.button(
                    title,
                    key=f"thread_{thread['thread_id']}",
                    use_container_width=True
                ):

                    load_thread(
                        thread["thread_id"]
                    )

        elif response.status_code == 401:

            logout()

        else:

            st.sidebar.error(
                "Failed to load conversations."
            )

    # LOGOUT

    st.sidebar.divider()

    if st.sidebar.button(
        "🚪 Logout",
        use_container_width=True
    ):

        logout()


# CHAT AREA

def render_chat():

    thread_id = st.session_state["thread_id"]

    st.subheader("💬 Chat")

    # CHAT HISTORY CONTAINER

    with st.container(
        height=800,
        border=True
    ):

        for message in st.session_state[
            "message_history"
        ]:

            with st.chat_message(
                message["role"]
            ):

                st.write(
                    message["content"]
                )

    # CHAT INPUT

    user_input = st.chat_input(
        "Ask something..."
    )

    if user_input:

        st.session_state[
            "message_history"
        ].append(
            {
                "role": "user",
                "content": user_input
            }
        )

        st.session_state[
            "message_history"
        ].append(
            {
                "role": "assistant",
                "content": "⏳ Thinking..."
            }
        )

        st.rerun()

    # PROCESS PENDING MESSAGE

    if st.session_state["message_history"]:

        last_message = (
            st.session_state[
                "message_history"
            ][-1]
        )

        if (
            last_message["role"] == "assistant"
            and
            last_message["content"] == "⏳ Thinking..."
        ):

            user_message = (
                st.session_state[
                    "message_history"
                ][-2]["content"]
            )

            ai_message = call_chat_api(
                user_message,
                thread_id
            )

            st.session_state[
                "message_history"
            ][-1]["content"] = ai_message

            # GENERATE TITLE AFTER FIRST MESSAGE

            if len(
                st.session_state[
                    "message_history"
                ]
            ) == 2:

                user = st.session_state["user"]

                try:

                    generate_title(
                        st.session_state[
                            "access_token"
                        ],
                        thread_id,
                        user["user_id"],
                        user_message
                    )

                except Exception:
                    pass

            st.rerun()

# VIDEO + PDF

def render_pdf_page(
    pdf_bytes,
    page_number,
    zoom=1.2
):
    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    page = doc.load_page(page_number)

    matrix = fitz.Matrix(
        zoom,
        zoom
    )

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    image = Image.open(
        io.BytesIO(
            pix.tobytes("png")
        )
    )

    doc.close()

    return image



def render_pdf_viewer(
    pdf_bytes,
    pdf_name="PDF"
):
    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    total_pages = len(doc)

    doc.close()

    st.caption(
        f"📄 {pdf_name} — {total_pages} pages"
    )

    # Page search
    page_number = st.number_input(
        "Go to page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"page_{pdf_name}"
    )

    # Scrollable PDF box
    with st.container(
        height=700,
        border=True
    ):

        for page_number_index in range(
            total_pages
        ):

            image = render_pdf_page(
                pdf_bytes,
                page_number_index,
                zoom=1.2
            )

            st.image(
                image,
                width="stretch"
            )

            st.caption(
                f"Page {page_number_index + 1} / {total_pages}"
            )


def render_pdf():

    # 1. Check whether a PDF exists

    if not st.session_state.get("pdf_uploaded", False):

        st.info("📄 Upload a PDF to view it here.")
        return

    thread_id = st.session_state.get("thread_id")

    if not thread_id:

        st.warning("No active thread.")
        return

    # 2. Get ALL PDFs for this thread

    pdf_response_list = get_thread_pdfs(thread_id)

    if (
        pdf_response_list is None
        or pdf_response_list.status_code != 200
    ):

        if pdf_response_list is None:

            st.error("Failed to connect to PDF list API.")

        else:

            try:
                detail = pdf_response_list.json().get(
                    "detail",
                    "Unknown error"
                )
            except Exception:
                detail = pdf_response_list.text

            st.error(
                f"PDF List Error "
                f"({pdf_response_list.status_code}): {detail}"
            )

        return

    # 3. Convert response -> dictionary

    pdf_data = pdf_response_list.json()

    pdfs = pdf_data.get("pdfs", [])

    if not pdfs:

        st.info("No PDFs found for this thread.")
        return

    # 4. PDF selector

    pdf_options = {
        pdf["doc_id"]: pdf.get(
            "filename",
            f"PDF {index + 1}"
        )
        for index, pdf in enumerate(pdfs)
    }

    selected_doc_id = st.selectbox(
        "📚 Select PDF",
        options=list(pdf_options.keys()),
        format_func=lambda doc_id: pdf_options[doc_id],
        key=f"selected_pdf_{thread_id}"
    )

    # 5. Get selected PDF

    pdf_response = get_pdf(
        thread_id,
        doc_id=selected_doc_id
    )

    if (
        pdf_response is None
        or pdf_response.status_code != 200
    ):

        if pdf_response is None:

            st.error("Failed to connect to PDF API.")

        else:

            try:
                detail = pdf_response.json().get(
                    "detail",
                    "Unknown error"
                )
            except Exception:
                detail = pdf_response.text

            st.error(
                f"PDF Error "
                f"({pdf_response.status_code}): "
                f"{detail}"
            )

        return

    # 6. Read PDF

    pdf_bytes = pdf_response.content

    try:

        doc = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        total_pages = len(doc)

        doc.close()

    except Exception as e:

        st.error(
            f"Unable to open PDF: {e}"
        )

        return

    if total_pages == 0:

        st.warning(
            "The PDF contains no pages."
        )

        return

    # 7. PDF information

    selected_pdf_name = pdf_options[selected_doc_id]

    st.markdown(
        f"### 📄 {selected_pdf_name}"
    )

    st.caption(
        f"{total_pages} page(s)"
    )

    # 8. Quick page search

    page_number = st.number_input(
        "🔎 Go to page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=f"pdf_page_{thread_id}_{selected_doc_id}"
    )

    # 9. Scrollable PDF BOOK

    st.markdown(
        "📖 **Document Viewer**"
    )

    with st.container(
        height=700,
        border=True
    ):

        for page_index in range(total_pages):

            try:

                image = render_pdf_page(
                    pdf_bytes,
                    page_index,
                    zoom=1.2
                )

                st.image(
                    image,
                    width="stretch"
                )

                st.caption(
                    f"Page {page_index + 1} / {total_pages}"
                )

            except Exception as e:

                st.error(
                    f"Failed to render page "
                    f"{page_index + 1}: {e}"
                )



    st.caption(
        f"Selected page: {page_number} / {total_pages}"
    )


def render_media():

    thread_id = st.session_state["thread_id"]

    st.subheader(
        "🎥 Video + 📄 Document"
    )

    if st.session_state.get("youtube_url"):

        st.video(
            st.session_state["youtube_url"]
        )

    else:

        st.info(
            "No video loaded"
        )

    st.markdown(
        "<div style='margin-top:10px'></div>",
        unsafe_allow_html=True
    )


    render_pdf()


def render_download():

    st.divider()

    chat_json = json.dumps(
        st.session_state[
            "message_history"
        ],
        indent=2
    )

    st.download_button(
        label="⬇️ Download Chat History",
        data=chat_json,
        file_name="chat_history.json",
        mime="application/json"
    )


def render_chat_ui():

    initialize_chat_state()

    ensure_thread()

   
    st.markdown(
      """
      <style>

    .block-container {
        padding: 0rem !important;
    }

    .main > div {
        gap: 0rem !important;
    }

    section[data-testid="stSidebar"] {
        width: 240px !important;
    }

    div[data-testid="column"] {
        padding: 0px !important;
    }

    .element-container {
        margin-bottom: 0px !important;
    }

    </style>
    """,
      unsafe_allow_html=True 
    )

    render_sidebar()

    st.title(
        "Multi Utility Chatbot"
    )


    split_ratio = st.slider(
        "Resize Chat ↔ Video",
        10,
        90,
        70
    )

    col_video, col_chat = st.columns(
        [
            100 - split_ratio,
            split_ratio
        ],
        gap="small"
    )


    with col_chat:

        render_chat()


    with col_video:

        render_media()
        