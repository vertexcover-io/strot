"use client";

import { useState } from "react";
import { Job, ReportResponse } from "@/types";
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Download,
  Eye,
  RefreshCw,
} from "lucide-react";
import { format } from "date-fns";
import { ReportViewer } from "./ReportViewer";
import { CodeBlock } from "./CodeBlock";
import { parseJSONLLogs } from "@/lib/report-generator";

interface JobDetailProps {
  job: Job;
  onBack: () => void;
  onRefresh?: () => Promise<void>;
}

export function JobDetail({ job, onBack, onRefresh }: JobDetailProps) {
  const [activeTab, setActiveTab] = useState<
    "details" | "output" | "report" | "logs"
  >("details");
  const [reportData, setReportData] = useState<ReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchReport = async () => {
    if (reportData) return; // Already loaded

    setReportLoading(true);
    setReportError(null);

    try {
      const response = await fetch(`/api/jobs/${job.id}/report`);
      if (!response.ok) {
        throw new Error("Failed to fetch report");
      }

      const data: ReportResponse = await response.json();
      setReportData(data);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setReportLoading(false);
    }
  };

  const handleTabClick = (tab: typeof activeTab) => {
    setActiveTab(tab);
    if (tab === "report" || tab === "logs") {
      fetchReport();
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
        return "text-green-600 bg-green-100";
      case "failed":
        return "text-red-600 bg-red-100";
      case "pending":
        return "text-blue-600 bg-blue-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Jobs
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{job.tag}</h1>
          <div className="flex items-center gap-2 mt-1">
            <ExternalLink className="w-4 h-4 text-gray-400" />
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 break-all"
            >
              {job.url}
            </a>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
              job.status,
            )}`}
          >
            {job.status}
          </span>
          {onRefresh && (
            <button
              onClick={async () => {
                setIsRefreshing(true);
                try {
                  // Clear report data so it gets refetched
                  setReportData(null);
                  setReportError(null);
                  await onRefresh();
                  // If we're on report or logs tab, refetch the report
                  if (activeTab === "report" || activeTab === "logs") {
                    await fetchReport();
                  }
                } finally {
                  setIsRefreshing(false);
                }
              }}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw
                className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: "details", label: "Details", icon: FileText },
            {
              id: "output",
              label: "Output",
              icon: Download,
              disabled: !job.output,
            },
            { id: "report", label: "Report", icon: Eye },
            { id: "logs", label: "Logs", icon: FileText },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id as typeof activeTab)}
                disabled={tab.disabled}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? "border-blue-500 text-blue-600"
                    : tab.disabled
                    ? "border-transparent text-gray-400 cursor-not-allowed"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div
        className={`${
          activeTab === "report"
            ? ""
            : "bg-white rounded-lg border border-gray-200 p-6"
        }`}
      >
        {activeTab === "details" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-lg font-semibold mb-4">Job Information</h3>
                <dl className="space-y-3">
                  <div>
                    <dt className="text-sm font-medium text-gray-600">
                      Job ID
                    </dt>
                    <dd className="text-sm text-gray-900 font-mono">
                      {job.id}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-600">
                      Status
                    </dt>
                    <dd className="text-sm text-gray-900">{job.status}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-600">
                      Message
                    </dt>
                    <dd className="text-sm text-gray-900">{job.message}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-600">
                      Created At
                    </dt>
                    <dd className="text-sm text-gray-900">
                      {format(new Date(job.createdAt), "PPpp")}
                    </dd>
                  </div>
                  {job.completedAt && (
                    <div>
                      <dt className="text-sm font-medium text-gray-600">
                        Completed At
                      </dt>
                      <dd className="text-sm text-gray-900">
                        {format(new Date(job.completedAt), "PPpp")}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              {job.output && (
                <div>
                  <h3 className="text-lg font-semibold mb-4">
                    Output Information
                  </h3>
                  <dl className="space-y-3">
                    <div>
                      <dt className="text-sm font-medium text-gray-600">
                        Output ID
                      </dt>
                      <dd className="text-sm text-gray-900 font-mono">
                        {job.output.id}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-600">
                        Usage Count
                      </dt>
                      <dd className="text-sm text-gray-900">
                        {job.output.usageCount}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-600">
                        Last Used
                      </dt>
                      <dd className="text-sm text-gray-900">
                        {job.output.lastUsedAt
                          ? format(new Date(job.output.lastUsedAt), "PPpp")
                          : "Never"}
                      </dd>
                    </div>
                  </dl>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "output" && job.output && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Output Data</h3>
            <CodeBlock
              title="output_data.json"
              language="json"
              maxHeight="max-h-96"
            >
              {JSON.stringify(job.output.value, null, 2)}
            </CodeBlock>
          </div>
        )}

        {activeTab === "report" && (
          <div className="space-y-4">
            {reportLoading && (
              <div className="text-center py-8">
                <div className="text-gray-600">Loading report...</div>
              </div>
            )}
            {reportError && (
              <div className="text-center py-8">
                <div className="text-red-600">{reportError}</div>
              </div>
            )}
            {reportData && (
              <ReportViewer
                reportData={parseJSONLLogs(reportData.logContent)}
              />
            )}
          </div>
        )}

        {activeTab === "logs" && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Raw Logs</h3>
            {reportLoading && (
              <div className="text-center py-8">
                <div className="text-gray-600">Loading logs...</div>
              </div>
            )}
            {reportError && (
              <div className="text-center py-8">
                <div className="text-red-600">{reportError}</div>
              </div>
            )}
            {reportData && (
              <CodeBlock
                title="job_logs.jsonl"
                language="json"
                maxHeight="max-h-96"
                theme="dark"
              >
                {reportData.logContent}
              </CodeBlock>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
