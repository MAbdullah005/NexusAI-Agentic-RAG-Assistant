export interface ChatMessage {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
  pending?: boolean;
  error?: boolean;
  is_research?: boolean;
  research_sources?: ResearchSource[];
}

export interface Thread {
  thread_id: string;
  title: string;
  created_at: string;
  is_pinned?: boolean;
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
  deep_research?: boolean;
  config?: DeepResearchConfig;
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
  sources?: ResearchSource[];
  sub_queries?: string[];
}

export interface ResearchSource {
  title: string;
  url: string;
  source_type?: "web" | "arxiv" | "document" | string;
  published_date?: string | null;
  authors?: string[];
}

export interface DeepResearchConfig {
  search_count?: number;
  report_length?: "short" | "medium" | "long";
  citation_style?: "APA" | "MLA" | "Harvard";
  iterations?: number;
  subqueries_count?: number;
  instructions?: string;
}

export interface ResearchStageUpdate {
  stage: "planning" | "searching" | "extracting" | "filtering" | "generating" | "completed" | "error";
  stage_message: string;
  sub_queries?: string[];
  sources?: ResearchSource[];
  evidence_count?: number;
  report?: string;
}

export interface ResearchRequest {
  message: string;
  thread_id: string;
  client_message_id?: string;
  selected_doc_ids?: string[];
  config?: DeepResearchConfig;
}

export interface ResearchResponse {
  status: "completed" | "error";
  thread_id: string;
  response: string;
  sources?: ResearchSource[];
  sub_queries?: string[];
  detail?: string;
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

