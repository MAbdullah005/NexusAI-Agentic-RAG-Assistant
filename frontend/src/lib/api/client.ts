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
  ResearchRequest,
  ResearchResponse,
  ResearchStageUpdate,
  ResearchSource,
  DeepResearchConfig,
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

  async renameThread(threadId: string, title: string): Promise<{ thread_id: string; title: string }> {
    return request<{ thread_id: string; title: string }>(
      `/thread/${encodeURIComponent(threadId)}/rename`,
      { method: "PATCH", body: JSON.stringify({ title }) }
    );
  },

  async pinThread(threadId: string, pinned: boolean): Promise<{ thread_id: string; is_pinned: boolean }> {
    return request<{ thread_id: string; is_pinned: boolean }>(
      `/thread/${encodeURIComponent(threadId)}/pin`,
      { method: "PATCH", body: JSON.stringify({ pinned }) }
    );
  },

  async deleteThread(threadId: string): Promise<{ deleted: boolean; thread_id: string }> {
    return request<{ deleted: boolean; thread_id: string }>(
      `/thread/${encodeURIComponent(threadId)}`,
      { method: "DELETE" }
    );
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

  async sendResearch(data: ResearchRequest): Promise<ResearchResponse> {
    return request<ResearchResponse>("/chat/research", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  streamResearch(
    data: ResearchRequest,
    onStageUpdate: (update: ResearchStageUpdate) => void,
    onComplete: (report: string, sources?: ResearchSource[]) => void,
    onError: (error: any) => void
  ): () => void {
    const controller = new AbortController();
    const token = getAccessToken();
    const url = `${API_BASE_URL}/chat/research/stream`;

    (async () => {
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(data),
          signal: controller.signal,
        });

        if (!response.ok) {
          let errText = `Research stream failed with status ${response.status}`;
          try {
            const errJson = await response.json();
            if (errJson?.detail) errText = errJson.detail;
          } catch {
            // ignore
          }
          throw new Error(errText);
        }

        if (!response.body) {
          throw new Error("No response body received from research stream");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let finalReport = "";
        let collectedSources: ResearchSource[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;

            const payloadStr = trimmed.replace(/^data:\s*/, "");
            if (payloadStr === "[DONE]") {
              if (finalReport) {
                onComplete(finalReport, collectedSources);
              }
              return;
            }

            try {
              const parsed: ResearchStageUpdate = JSON.parse(payloadStr);
              if (parsed.sources && parsed.sources.length > 0) {
                collectedSources = parsed.sources;
              }
              if (parsed.report) {
                finalReport = parsed.report;
              }

              onStageUpdate(parsed);

              if (parsed.stage === "completed" && parsed.report) {
                onComplete(parsed.report, parsed.sources || collectedSources);
              } else if (parsed.stage === "error") {
                onError(new Error(parsed.stage_message || "Research failed"));
              }
            } catch (jsonErr) {
              console.warn("Failed to parse SSE research chunk:", payloadStr, jsonErr);
            }
          }
        }

        // Handle trailing buffer if any
        if (buffer.trim().startsWith("data:")) {
          const payloadStr = buffer.trim().replace(/^data:\s*/, "");
          if (payloadStr !== "[DONE]") {
            try {
              const parsed: ResearchStageUpdate = JSON.parse(payloadStr);
              if (parsed.report) finalReport = parsed.report;
              onStageUpdate(parsed);
              if (parsed.stage === "completed" && parsed.report) {
                onComplete(parsed.report, parsed.sources || collectedSources);
              }
            } catch {
              // ignore
            }
          }
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          console.log("Research stream aborted by user");
          return;
        }
        onError(err);
      }
    })();

    return () => controller.abort();
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
