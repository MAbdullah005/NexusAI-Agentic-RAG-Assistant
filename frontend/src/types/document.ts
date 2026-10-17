export interface ThreadPdf {
  doc_id: string;
  filename: string;
  created_at: string;
}

export interface ThreadPdfsResponse {
  thread_id: string;
  count: number;
  pdfs: ThreadPdf[];
}

export interface UploadPdfResponse {
  status: string;
  doc_id: string;
}

export interface UploadUrlResponse {
  status: string;
  doc_id: string;
  title: string;
}

export interface SetYoutubeResponse {
  status: string;
  doc_id: string;
}

