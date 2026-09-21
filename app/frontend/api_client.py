import requests
import streamlit as st

# API CONFIGURATION

API_BASE_URL = "http://localhost:8000"


# AUTH Eenpoint

API_LOGIN = f"{API_BASE_URL}/auth/login"
API_SIGNUP = f"{API_BASE_URL}/auth/signup"
API_ME = f"{API_BASE_URL}/auth/me"
API_FORGOT_PASSWORD = f"{API_BASE_URL}/auth/forgot-password"
API_RESET_PASSWORD = f"{API_BASE_URL}/auth/reset-password"


# Chat endpoint
API_CHAT = f"{API_BASE_URL}/chat"
API_NEW_THREAD = f"{API_BASE_URL}/new-thread"
API_THREADS = f"{API_BASE_URL}/threads"

API_GENERATE_TITLE = f"{API_BASE_URL}/generate-title"

API_UPLOAD_PDF = f"{API_BASE_URL}/upload-pdf"
#API_GET_PDF1 = f"{API_BASE_URL}/get_pdf/{{thread_id}}"

API_THREAD_PDFS = f"{API_BASE_URL}/thread/{{}}/pdfs"
API_GET_PDF = f"{API_BASE_URL}/get_pdf/{{}}/{{}}"

API_UPLOAD_URL=f"{API_BASE_URL}/upload-url"
API_GET_URL=f"{API_BASE_URL}/get_url/{{}}/{{}}"

API_SET_YOUTUBE = f"{API_BASE_URL}/set_youtube"
API_GET_YOUTUBE = f"{API_BASE_URL}/get_youtube/{{thread_id}}"

# resume chat on interput

API_CHAT_RESUME=f"{API_BASE_URL}/chat/resume"

# api get details

API_THREAD_DETAILS = f"{API_BASE_URL}/thread/{{thread_id}}/details"
API_THREAD_DOCUMENTS = f"{API_BASE_URL}/thread/{{thread_id}}/documents"
API_THREAD_SOURCES = f"{API_BASE_URL}/thread/{{thread_id}}/sources"


# AUTH Header

def auth_headers(token: str | None):
    """
    Return Authorization headers for protected API requests.
    """

    if not token:
        return {}

    return {
        "Authorization": f"Bearer {token}"
    }


# LOGIN

def login(email: str, password: str):
    """
    Login user and return API response.
    """

    try:
        response = requests.post(
            API_LOGIN,
            json={
                "email": email,
                "password": password
            },
            timeout=60
        )

        return response

    except requests.RequestException as e:
        return None


# SIGNUP

def signup(email: str, password: str):
    """
    Create a new user account.
    """

    try:
        response = requests.post(
            API_SIGNUP,
            json={
                "email": email,
                "password": password
            },
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def get_current_user(token: str):
    """
    Get authenticated user information.
    """

    try:
        response = requests.get(
            API_ME,
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def forgot_password(email: str):
    """
    Request a password reset email.
    """

    try:
        response = requests.post(
            API_FORGOT_PASSWORD,
            json={
                "email": email
            },
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def reset_password(token: str, new_password: str):
    """
    Reset password using the token received by email.
    """

    try:
        response = requests.post(
            API_RESET_PASSWORD,
            json={
                "token": token,
                "new_password": new_password
            },
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def send_message(token: str, message: str, thread_id: str):
    """
    Send a chat message.
    """

    try:
        response = requests.post(
            API_CHAT,
            json={
                "message": message,
                "thread_id": thread_id
            },
            headers=auth_headers(token),
            timeout=300
        )

        return response

    except requests.RequestException:
        return None



def create_thread(token: str):
    """
    Create a new chat thread.
    """

    try:
        response = requests.post(
            API_NEW_THREAD,
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def get_threads(token: str):
    """
    Get all threads belonging to the authenticated user.
    """

    try:
        response = requests.get(
            API_THREADS,
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def get_thread_details(token: str, thread_id: str):
    """
    Get messages and documents for a thread.
    """

    try:
        response = requests.get(
            API_THREAD_DETAILS.format(thread_id=thread_id),
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def set_youtube(token: str, thread_id: str, youtube_url: str):
    """
    Load a YouTube video into a thread.
    """

    try:
        response = requests.post(
            API_SET_YOUTUBE,
            json={
                "thread_id": thread_id,
                "youtube_url": youtube_url
            },
            headers=auth_headers(token),
            timeout=300
        )

        return response

    except requests.RequestException:
        return None


def get_youtube(token: str, thread_id: str):
    """
    Get YouTube videos associated with a thread.
    """

    try:
        response = requests.get(
            API_GET_YOUTUBE.format(thread_id=thread_id),
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


#pdf

def upload_pdf(token: str, thread_id: str, uploaded_file):
    """
    Upload PDF to a thread.
    """

    try:
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf"
            )
        }

        data = {
            "thread_id": thread_id
        }

        response = requests.post(
            API_UPLOAD_PDF,
            files=files,
            data=data,
            headers=auth_headers(token),
            timeout=300
        )

        return response

    except requests.RequestException:
        return None


def get_auth_headers():
    token = st.session_state.get("access_token")

    if not token:
        return {}

    return {
        "Authorization": f"Bearer {token}"
    }

def get_pdf(thread_id: str, doc_id: str):

    try:
        response = requests.get(
            API_GET_PDF.format(
                thread_id,
                doc_id
            ),
            headers=get_auth_headers(),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None

def get_thread_pdfs(thread_id: str):
    try:
        response = requests.get(
            API_THREAD_PDFS.format(thread_id),
            headers=get_auth_headers(),
            timeout=30
        )

        return response

    except requests.RequestException as e:
        print(f"[PDF API] Request failed: {repr(e)}")
        return None

    
def get_thread_documents(token: str, thread_id: str):
    """
    Get documents associated with a thread.
    """

    try:
        response = requests.get(
            API_THREAD_DOCUMENTS.format(
                thread_id=thread_id
            ),
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


def get_thread_sources(token: str, thread_id: str):
    """
    Get sources associated with a thread.
    """

    try:
        response = requests.get(
            API_THREAD_SOURCES.format(
                thread_id=thread_id
            ),
            headers=auth_headers(token),
            timeout=60
        )

        return response

    except requests.RequestException:
        return None


# Title

def generate_title(
    token: str,
    thread_id: str,
    user_id: int,
    message: str
):
    """
    Generate a title for a thread.
    """

    try:
        response = requests.post(
            API_GENERATE_TITLE,
            json={
                "thread_id": thread_id,
                "user_id": user_id,
                "message": message
            },
            headers=auth_headers(token),
            timeout=300
        )

        return response

    except requests.RequestException:
        return None



# set url

def upload_url(token, thread_id, url):
    """
    Upload a website URL to the current thread.
    The backend extracts the website content and
    creates a vectorstore for RAG.
    """

    try:

        data = {
            "thread_id": thread_id,
            "url": url
        }

        response = requests.post(
            API_UPLOAD_URL,
            data=data,
            headers=auth_headers(token=token),
            timeout=300
        )

        return response

    except requests.RequestException:
        return None

# get url

def get_url(token,thread_id,doc_id):
    "Get Url specifc to that thread"
    try:

        responce=requests.get(
            API_GET_URL,
            thread_id,
            doc_id,
            headers=auth_headers(token=token),
            timeout=300
        )

        return responce
    except requests.RequestException:
        return None



# resume caht fun

def resume_chat(
    thread_id: str,
    decision: str
):
    try:

        response = requests.post(
            API_CHAT_RESUME,
            json={
                "thread_id": thread_id,
                "decision": decision
            },
            headers=get_auth_headers(),
            timeout=400
        )

        return response

    except requests.RequestException as e:

        print(
            f"[HITL] Resume request failed: {repr(e)}"
        )

        return None