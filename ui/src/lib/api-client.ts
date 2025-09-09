import {
  JobListResponse,
  GetJobResponse,
  CreateJobRequest,
  CreateJobResponse,
  LabelListResponse,
  LabelResponse,
  LabelCreate,
  LabelUpdate,
  APIError,
} from "@/types";
import { getAppConfig } from "./config";

class APIClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || getAppConfig().api.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const isFormData = options.body instanceof FormData;
    const headers: HeadersInit = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    };
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorData: APIError = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // If we can't parse the error response, use the default message
      }
      throw new Error(errorMessage);
    }

    // Check if response has content before trying to parse JSON
    const contentLength = response.headers.get("content-length");
    const contentType = response.headers.get("content-type");

    // If no content or content-length is 0, return null instead of trying to parse JSON
    if (
      contentLength === "0" ||
      response.status === 204 ||
      !contentType?.includes("application/json")
    ) {
      return null as T;
    }

    return response.json();
  }

  // Jobs API
  async listJobs(
    params: {
      limit?: number;
      offset?: number;
      status?: string;
      label?: string;
      search?: string;
    } = {},
  ): Promise<JobListResponse> {
    const searchParams = new URLSearchParams();

    if (params.limit) searchParams.set("limit", params.limit.toString());
    if (params.offset) searchParams.set("offset", params.offset.toString());
    if (params.status) searchParams.set("status", params.status);
    if (params.label) searchParams.set("label", params.label);
    if (params.search) searchParams.set("search", params.search);

    const queryString = searchParams.toString();
    const endpoint = `/v1/jobs${queryString ? `?${queryString}` : ""}`;

    return this.request<JobListResponse>(endpoint);
  }

  async getJob(jobId: string): Promise<GetJobResponse> {
    return this.request<GetJobResponse>(`/v1/jobs/${jobId}`);
  }

  async fetchJobData(
    jobId: string,
    options: {
      limit?: number;
      offset?: number;
      dynamicParams?: Record<string, string>;
    } = {},
  ): Promise<{ data: any[]; error?: string }> {
    const searchParams = new URLSearchParams();

    // Add limit and offset as query parameters
    if (options.limit !== undefined) {
      searchParams.set("limit", options.limit.toString());
    }
    if (options.offset !== undefined) {
      searchParams.set("offset", options.offset.toString());
    }

    const queryString = searchParams.toString();
    const endpoint = `/v1/jobs/${jobId}/fetch${
      queryString ? `?${queryString}` : ""
    }`;

    // Prepare form data for dynamic parameters
    const formData = new FormData();
    if (options.dynamicParams) {
      Object.entries(options.dynamicParams).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    return this.request<{ data: any[]; error?: string }>(endpoint, {
      method: "POST",
      headers: {}, // Let fetch set the correct Content-Type for FormData
      body: formData,
    });
  }

  async createJob(jobData: CreateJobRequest): Promise<CreateJobResponse> {
    return this.request<CreateJobResponse>("/v1/jobs", {
      method: "POST",
      body: JSON.stringify(jobData),
    });
  }

  async deleteJob(jobId: string): Promise<void> {
    await this.request(`/v1/jobs/${jobId}`, {
      method: "DELETE",
    });
  }

  // Labels API
  async listLabels(
    params: {
      limit?: number;
      offset?: number;
      search?: string;
    } = {},
  ): Promise<LabelListResponse> {
    const searchParams = new URLSearchParams();

    if (params.limit) searchParams.set("limit", params.limit.toString());
    if (params.offset) searchParams.set("offset", params.offset.toString());
    if (params.search) searchParams.set("search", params.search);

    const queryString = searchParams.toString();
    const endpoint = `/labels${queryString ? `?${queryString}` : ""}`;

    return this.request<LabelListResponse>(endpoint);
  }

  async getLabel(labelId: string): Promise<LabelResponse> {
    return this.request<LabelResponse>(`/labels/${labelId}`);
  }

  async createLabel(labelData: LabelCreate): Promise<LabelResponse> {
    return this.request<LabelResponse>("/labels", {
      method: "POST",
      body: JSON.stringify(labelData),
    });
  }

  async updateLabel(
    labelId: string,
    labelData: LabelUpdate,
  ): Promise<LabelResponse> {
    return this.request<LabelResponse>(`/labels/${labelId}`, {
      method: "PUT",
      body: JSON.stringify(labelData),
    });
  }

  async deleteLabel(labelId: string, force: boolean = false): Promise<void> {
    const searchParams = new URLSearchParams();
    if (force) searchParams.set("force", "true");

    const queryString = searchParams.toString();
    const endpoint = `/labels/${labelId}${
      queryString ? `?${queryString}` : ""
    }`;

    await this.request(endpoint, {
      method: "DELETE",
    });
  }
}

// Export a singleton instance
export const apiClient = new APIClient();
export default apiClient;
