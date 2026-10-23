import { getAccessToken } from "../auth/token";
import type {
  LoginRequest,
  LoginResponse,
  MessageResponse,
  SignupRequest,
  User,
  ResetPasswordRequest,
} from "../../types/auth";
import type {
  ChatRequest,
  ChatResponse,
  HITLResumeRequest,
  HITLResumeResponse,
  Thread,
  ThreadDetails,
} from "../../types/chat";
import type {
  SetYoutubeResponse,
  ThreadPdfsResponse,
  UploadPdfResponse,
  UploadUrlResponse,
  UploadRepoResponse,
} from "../../types/document";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // If body is not FormData, ensure Content-Type is json
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorData = null;
    try {
      errorData = await response.json();
      if (typeof errorData?.detail === "string") {
        errorDetail = errorData.detail;
      } else if (typeof errorData?.message === "string") {
        errorDetail = errorData.message;
      } else if (Array.isArray(errorData?.detail)) {
        errorDetail = errorData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
      }
    } catch {
      // not JSON
      try {
        const text = await response.text();
        if (text) errorDetail = text;
      } catch {
        // ignore
      }
    }

    throw new ApiError(errorDetail, response.status, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Auth
  async signup(data: SignupRequest): Promise<MessageResponse> {
    return request<MessageResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async login(data: LoginRequest): Promise<LoginResponse> {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me");
  },

  async forgotPassword(email: string): Promise<MessageResponse> {
    return request<MessageResponse>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(data: ResetPasswordRequest): Promise<MessageResponse> {
    return request<MessageResponse>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async verifyEmail(token: string): Promise<MessageResponse> {
    return request<MessageResponse>(`/auth/verify-email?token=${encodeURIComponent(token)}`);
  },

  // Threads
  async getThreads(): Promise<Thread[]> {
    return request<Thread[]>("/threads");
  },

  async createThread(): Promise<{ thread_id: string }> {
    return request<{ thread_id: string }>("/new-thread", {
      method: "POST",
    });
  },

  async getThreadDetails(threadId: string): Promise<ThreadDetails> {
    return request<ThreadDetails>(`/thread/${encodeURIComponent(threadId)}/details`);
  },

  async generateTitle(threadId: string, userId: number, message: string): Promise<{ title: string }> {
    return request<{ title: string }>("/generate-title", {
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        user_id: userId,
        message,
      }),
    });
  },

  // Chat
  async sendMessage(data: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async resumeChat(data: HITLResumeRequest): Promise<HITLResumeResponse> {
    return request<HITLResumeResponse>("/chat/resume", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Documents & Media
  async uploadPdf(file: File, threadId: string): Promise<UploadPdfResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("thread_id", threadId);

    return request<UploadPdfResponse>("/upload-pdf", {
      method: "POST",
      body: formData,
    });
  },

  async uploadUrl(url: string, threadId: string): Promise<UploadUrlResponse> {
    const formData = new FormData();
    formData.append("url", url);
    formData.append("thread_id", threadId);

    return request<UploadUrlResponse>("/upload-url", {
      method: "POST",
      body: formData,
    });
  },

  async setYoutube(youtubeUrl: string, threadId: string): Promise<SetYoutubeResponse> {
    return request<SetYoutubeResponse>("/set_youtube", {
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        youtube_url: youtubeUrl,
      }),
    });
  },

  async uploadRepo(url: string, threadId: string): Promise<UploadRepoResponse> {
    return request<UploadRepoResponse>("/upload-repo", {
      method: "POST",
      body: JSON.stringify({
        url,
        thread_id: threadId,
      }),
    });
  },

  async indexRepo(url: string, threadId?: string): Promise<UploadRepoResponse> {
    return request<UploadRepoResponse>("/index", {
      method: "POST",
      body: JSON.stringify({
        url,
        thread_id: threadId,
      }),
    });
  },

  async getRepositories(): Promise<any[]> {
    return request<any[]>("/api/repositories");
  },

  async getThreadDocuments(threadId: string): Promise<{ thread_id: string; documents: any[] }> {
    return request<{ thread_id: string; documents: any[] }>(
      `/thread/${encodeURIComponent(threadId)}/documents`
    );
  },

  async getThreadPdfs(threadId: string): Promise<ThreadPdfsResponse> {
    return request<ThreadPdfsResponse>(`/thread/${encodeURIComponent(threadId)}/pdfs`);
  },

  async getPdfBlob(threadId: string, docId: string): Promise<Blob> {
    const token = getAccessToken();
    const url = `${API_BASE_URL}/get_pdf/${encodeURIComponent(threadId)}/${encodeURIComponent(docId)}`;
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new ApiError(`Failed to load PDF (${response.status})`, response.status);
    }
    return response.blob();
  },

  getPdfUrl(threadId: string, docId: string): string {
    return `${API_BASE_URL}/get_pdf/${encodeURIComponent(threadId)}/${encodeURIComponent(docId)}`;
  },
};
