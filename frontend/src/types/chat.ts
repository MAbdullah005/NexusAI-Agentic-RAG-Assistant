export interface ChatMessage {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
  pending?: boolean;
  error?: boolean;
}

export interface Thread {
  thread_id: string;
  title: string;
  created_at: string;
}

export interface AttachedDocument {
  doc_id: string;
  type: "pdf" | "youtube" | "web" | string;
  source: string;
  filename?: string;
  title?: string;
  created_at?: string;
  status?: "ready" | "processing" | "failed";
}

export interface ThreadDetails {
  thread_id: string;
  title: string;
  summary: string | null;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
  documents: AttachedDocument[];
}

export interface ChatRequest {
  message: string;
  thread_id: string;
  client_message_id?: string;
  selected_doc_ids?: string[];
}

export interface HITLInterruptData {
  message?: string;
  question?: string;
  [key: string]: any;
}

export interface ChatResponse {
  status: "completed" | "human-approval" | "error";
  thread_id: string;
  response?: string;
  interrupt?: HITLInterruptData;
  detail?: string;
  message?: string;
}

export interface HITLResumeRequest {
  thread_id: string;
  decision: "yes" | "no";
  message_id?: string;
}

export interface HITLResumeResponse {
  status: "completed" | "human-approval" | "error";
  thread_id: string;
  result?: {
    messages?: Array<{
      content?: string;
      role?: string;
    }>;
    summary?: string;
    [key: string]: any;
  };
  interrupt?: HITLInterruptData;
  detail?: string;
}

