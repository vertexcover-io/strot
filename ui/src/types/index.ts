// Job related types
export type JobStatus = "pending" | "ready" | "failed";

export interface JobListItem {
  id: string;
  url: string;
  label_name: string;
  status: JobStatus;
  initiated_at: string;
  completed_at?: string;
  usage_count: number;
  last_used_at?: string;
  error?: string;
}

export interface JobListResponse {
  jobs: JobListItem[];
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
}

export interface CreateJobRequest {
  url: string;
  label: string;
}

export interface CreateJobResponse {
  job_id: string;
}

export interface GetJobResponse {
  url: string;
  label: string;
  job_id: string;
  initiated_at: string;
  status: JobStatus;
  completed_at?: string;
  error?: string;
  source?: any;
  result?: any;
}

// Label related types
export interface LabelResponse {
  id: string;
  name: string;
  requirement: string;
  output_schema: any;
  created_at: string;
  updated_at: string;
}

export interface LabelListResponse {
  labels: LabelResponse[];
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
}

export interface LabelCreate {
  name: string;
  requirement: string;
  output_schema: any;
}

export interface LabelUpdate {
  requirement?: string;
  output_schema?: any;
}

// Report response (for S3 logs)
export interface ReportResponse {
  jobId: string;
  logContent: string;
  reportHtml?: string;
}

// API Error type
export interface APIError {
  detail: string;
}
