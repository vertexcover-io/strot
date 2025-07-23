export interface Job {
  id: string;
  url: string;
  tag: string;
  status: "pending" | "ready" | "failed";
  message: string;
  outputId?: string;
  createdAt: string;
  completedAt?: string;
  output?: Output;
}

export interface Output {
  id: string;
  url: string;
  tag: string;
  value: unknown; // The JSON output from the analysis
  usageCount: number;
  lastUsedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface JobsResponse {
  jobs: Job[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

export interface ReportResponse {
  jobId: string;
  logContent: string;
  reportHtml?: string;
}
