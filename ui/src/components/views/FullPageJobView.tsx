"use client";

import { useState, useEffect, useRef } from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { GetJobResponse } from "@/types";
import { apiClient } from "@/lib/api-client";
import { LogViewer } from "../logs/LogViewer";
import { CodeBlock } from "../common/CodeBlock";
import { format } from "date-fns";
import { getAppConfig } from "@/lib/config";

interface FullPageJobViewProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string;
}

type TabType = "logs" | "preview";

export function FullPageJobView({
  isOpen,
  onClose,
  jobId,
}: FullPageJobViewProps) {
  const [jobData, setJobData] = useState<GetJobResponse | null>(null);
  const [sampleData, setSampleData] = useState<{
    data: any[];
    error?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("logs");
  const [isRawMode, setIsRawMode] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const fetchJobData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getJob(jobId);
      setJobData(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch job details",
      );
    } finally {
      setLoading(false);
    }
  };

  // Fetch job data when overlay opens or refresh trigger changes
  useEffect(() => {
    console.log("FullPageJobView useEffect:", {
      isOpen,
      jobId,
      refreshTrigger,
    });
    if (isOpen && jobId) {
      console.log("Calling fetchJobData for jobId:", jobId);
      fetchJobData();
    }
  }, [isOpen, jobId, refreshTrigger]);

  // Auto-refresh for pending jobs every 15 seconds
  useEffect(() => {
    if (!isOpen || !jobData || jobData.status !== "pending") return;

    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, 15000);

    return () => clearInterval(interval);
  }, [isOpen, jobData?.status]);

  // Trigger final refresh when job status changes from pending to ready/failed
  const previousStatus = useRef<string | null>(null);
  useEffect(() => {
    if (!isOpen || !jobData) return;

    // Only trigger final refresh if status changed FROM "pending" TO "ready/failed"
    if (
      previousStatus.current === "pending" &&
      (jobData.status === "ready" || jobData.status === "failed")
    ) {
      const timer = setTimeout(() => {
        setRefreshTrigger((prev) => prev + 1);
      }, 1000); // Small delay to ensure logs are written

      previousStatus.current = jobData.status;
      return () => clearTimeout(timer);
    }

    // Update previous status
    previousStatus.current = jobData.status;
  }, [isOpen, jobData?.status]);

  const fetchSampleData = async () => {
    if (!jobData || jobData.status !== "ready" || !jobData.source) return;

    try {
      setSampleLoading(true);
      const data = await apiClient.fetchJobData(jobId, { limit: 5, offset: 0 });
      setSampleData(data);
    } catch (err) {
      console.error("Failed to fetch sample data:", err);
    } finally {
      setSampleLoading(false);
    }
  };

  // Fetch sample data when switching to preview tab
  useEffect(() => {
    if (
      activeTab === "preview" &&
      jobData?.status === "ready" &&
      jobData?.source &&
      !sampleData
    ) {
      fetchSampleData();
    }
  }, [activeTab, jobData]);

  const handleClose = () => {
    setJobData(null);
    setSampleData(null);
    setError(null);
    setActiveTab("logs");
    setIsRawMode(false);
    onClose();
  };

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isOpen) {
        handleClose();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const getStatusBadge = (status: string) => {
    const baseClasses = "px-3 py-1 text-sm font-medium rounded-full";
    switch (status) {
      case "pending":
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      case "ready":
        return `${baseClasses} bg-green-100 text-green-800`;
      case "failed":
        return `${baseClasses} bg-red-100 text-red-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), "PPpp");
  };

  const generateCurlCommand = () => {
    if (!jobData || !jobData.source) return "";

    const apiUrl = getAppConfig().api.baseUrl;
    const endpoint = `${apiUrl}/v1/jobs/${jobId}/fetch?limit=5&offset=0`;

    return `curl -X POST "${endpoint}"`;
  };

  const shouldAutoRefresh =
    jobData?.status === "pending" || jobData?.status === "ready";

  // For header display, only show auto-refresh indicator when actually needed
  const shouldShowAutoRefreshIndicator = jobData?.status === "pending";
  const hasSource = jobData?.status === "ready" && jobData?.source;

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-50 to-gray-50 border-b border-gray-200 px-6 py-6 flex-shrink-0">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            {jobData && (
              <div className="space-y-4">
                {/* Title Row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-3">
                      <div className="bg-white rounded-lg px-3 py-2 shadow-sm border">
                        <h1 className="text-xl font-bold text-slate-800">
                          Job {jobId}
                        </h1>
                      </div>
                      <span className={getStatusBadge(jobData.status)}>
                        {jobData.status}
                      </span>
                    </div>
                    {shouldShowAutoRefreshIndicator && (
                      <div className="flex items-center bg-amber-50 border border-amber-200 rounded-full px-3 py-1">
                        <div className="animate-pulse w-2 h-2 bg-amber-400 rounded-full mr-2"></div>
                        <span className="text-sm font-medium text-amber-700">
                          Auto-refreshing
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-3">
                  <div className="flex items-center space-x-3">
                    <svg
                      className="w-5 h-5 text-blue-600 flex-shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                      />
                    </svg>
                    <a
                      href={jobData.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-800 break-all font-mono hover:underline transition-colors duration-200 flex items-center space-x-2"
                    >
                      <span>{jobData.url}</span>
                      <svg
                        className="w-4 h-4 flex-shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                        />
                      </svg>
                    </a>
                  </div>

                  <div className="flex items-center space-x-3">
                    <svg
                      className="w-5 h-5 text-purple-600 flex-shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                      />
                    </svg>
                    <span className="text-sm text-gray-900 font-medium">
                      {jobData.label}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-white hover:shadow-sm rounded-lg transition-all duration-200 flex-shrink-0 bg-white/50"
          >
            <XMarkIcon className="h-6 w-6 text-gray-500" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="mt-4">
          <nav className="flex space-x-8">
            <button
              onClick={() => setActiveTab("logs")}
              className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "logs"
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              Log Viewer
              {activeTab === "logs" && (
                <div className="ml-3 inline-flex">
                  <div className="bg-gray-100 rounded-lg p-1 flex">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsRawMode(false);
                      }}
                      className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                        !isRawMode
                          ? "bg-white text-blue-600 shadow-sm"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      Render
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsRawMode(true);
                      }}
                      className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                        isRawMode
                          ? "bg-white text-blue-600 shadow-sm"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      Raw
                    </button>
                  </div>
                </div>
              )}
            </button>

            {hasSource && (
              <button
                onClick={() => setActiveTab("preview")}
                className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === "preview"
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                Preview
              </button>
            )}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-3 text-gray-600">Loading job details...</span>
          </div>
        ) : error ? (
          <div className="p-6 overflow-y-auto h-full">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
              <h3 className="text-red-800 font-medium mb-2">
                Error Loading Job
              </h3>
              <p className="text-red-700">{error}</p>
              <button
                onClick={fetchJobData}
                className="mt-3 text-sm text-red-800 hover:text-red-900 underline"
              >
                Try again
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Tab Content */}

            {activeTab === "preview" && hasSource && jobData && (
              <div className="p-6 overflow-y-auto h-full">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
                  {/* Left Column - cURL and Preview */}
                  <div className="space-y-6">
                    <div>
                      <p className="text-sm text-gray-600 mb-3">
                        Use the following command to fetch data directly from
                        the API:
                      </p>
                      <CodeBlock
                        language="bash"
                        title="cURL Command"
                        theme="dark"
                        maxHeight="max-h-32"
                      >
                        {generateCurlCommand()}
                      </CodeBlock>
                    </div>

                    <div>
                      {sampleLoading ? (
                        <div className="flex items-center justify-center h-32 bg-gray-50 border border-gray-200 rounded-lg">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                          <span className="ml-3 text-gray-600">
                            Loading preview...
                          </span>
                        </div>
                      ) : sampleData ? (
                        <div className="space-y-3">
                          {sampleData.error && (
                            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                              <div className="flex items-start">
                                <div className="flex-shrink-0">
                                  <svg
                                    className="h-5 w-5 text-red-400"
                                    viewBox="0 0 20 20"
                                    fill="currentColor"
                                  >
                                    <path
                                      fillRule="evenodd"
                                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                      clipRule="evenodd"
                                    />
                                  </svg>
                                </div>
                                <div className="ml-3">
                                  {sampleData.data.length > 0 ? (
                                    <h3 className="text-sm font-medium text-red-800">
                                      Partial Data Retrieved
                                    </h3>
                                  ) : (
                                    <h3 className="text-sm font-medium text-red-800">
                                      Data fetch failed
                                    </h3>
                                  )}
                                  <div className="mt-2 text-sm text-red-700">
                                    {sampleData.error}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {sampleData.data && sampleData.data.length > 0 ? (
                            <CodeBlock
                              language="json"
                              title={`JSON Response (${
                                sampleData.data.length
                              } items${
                                sampleData.error ? " - Partial Data" : ""
                              })`}
                              theme="dark"
                              maxHeight="max-h-96"
                            >
                              {JSON.stringify(sampleData.data, null, 2)}
                            </CodeBlock>
                          ) : (
                            <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
                              <p className="text-gray-600">
                                No preview data available
                              </p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
                          <p className="text-gray-600">
                            No preview data available
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Column - Source Information */}
                  <div>
                    <CodeBlock
                      language="json"
                      title="Source Information"
                      theme="light"
                      maxHeight="max-h-128"
                      showCopy={true}
                    >
                      {JSON.stringify(jobData.source, null, 2)}
                    </CodeBlock>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "logs" && (
              <div className="h-full px-25">
                <LogViewer
                  key={`logviewer-${jobId}`}
                  jobId={jobId}
                  isRawMode={isRawMode}
                  autoRefresh={shouldAutoRefresh}
                  refreshInterval={15000}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
