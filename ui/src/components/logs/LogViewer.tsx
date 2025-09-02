"use client";

import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { ReportData, parseJSONLLogs } from "@/lib/report-generator";
import { SlideNavigation } from "./SlideNavigation";
import { AnalysisStep } from "./AnalysisStep";
import { ParameterDetection } from "./ParameterDetection";
import { StructuredExtraction } from "./StructuredExtraction";
import { CodeBlock } from "../common/CodeBlock";
import { format } from "date-fns";
import { Clock, DollarSign, Zap, Eye, Code, Search } from "lucide-react";
import { getJobLogFile } from "@/lib/s3";

interface LogViewerProps {
  jobId: string;
  isRawMode: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function LogViewer({
  jobId,
  isRawMode,
  autoRefresh = false,
  refreshInterval = 15000,
}: LogViewerProps) {
  const [logContent, setLogContent] = useState<string>("");
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollPosition = useRef<number>(0);
  const isRestoring = useRef<boolean>(false);

  // Store slide positions to persist across refreshes using sessionStorage
  const getStoredPositions = () => {
    try {
      const stored = sessionStorage.getItem(`slidePositions_${jobId}`);
      return stored
        ? JSON.parse(stored)
        : { analysis: 0, parameter: 0, extraction: 0 };
    } catch {
      return { analysis: 0, parameter: 0, extraction: 0 };
    }
  };

  const [slidePositions, setSlidePositions] =
    useState<Record<string, number>>(getStoredPositions);

  // Check if any part of the analysis is still pending
  const hasIncompleteAnalysis = () => {
    if (!reportData) return false;

    // Check if last code generation is still pending
    if (reportData.code_generations.length > 0) {
      const lastCodeGen =
        reportData.code_generations[reportData.code_generations.length - 1];
      if (lastCodeGen.status === "pending") {
        return true;
      }
    }

    // Check if any analysis step is still pending
    if (reportData.analysis_steps.length > 0) {
      const lastAnalysis =
        reportData.analysis_steps[reportData.analysis_steps.length - 1];
      if (lastAnalysis.status === "pending") {
        return true;
      }
    }

    // Check if any pagination detection is still pending
    if (reportData.pagination_detections.length > 0) {
      const lastPagination =
        reportData.pagination_detections[
          reportData.pagination_detections.length - 1
        ];
      if (lastPagination.status === "pending") {
        return true;
      }
    }

    return false;
  };

  // Save positions to sessionStorage whenever they change
  const updateSlidePosition = (section: string, index: number) => {
    const newPositions = { ...slidePositions, [section]: index };
    setSlidePositions(newPositions);
    try {
      sessionStorage.setItem(
        `slidePositions_${jobId}`,
        JSON.stringify(newPositions),
      );
    } catch {
      // Ignore storage errors
    }
  };

  const fetchLogs = async () => {
    // Get scroll position from sessionStorage (survives component re-renders)
    let savedPosition = scrollPosition.current;
    try {
      const stored = sessionStorage.getItem(`scrollPosition_${jobId}`);
      if (stored) {
        savedPosition = parseInt(stored, 10);
      }
    } catch {
      // Ignore storage errors
    }

    try {
      setError(null);
      const logs = await getJobLogFile(jobId);
      setLogContent(logs);
      setLastFetch(new Date());

      if (!isRawMode) {
        const parsed = parseJSONLLogs(logs);
        setReportData(parsed);
      }
    } catch (err) {
      console.error("Error fetching logs:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch logs");
      setLogContent("");
      setReportData(null);
    } finally {
      setLoading(false);

      // Restore scroll position after a delay
      if (savedPosition > 0) {
        isRestoring.current = true;
        setTimeout(() => {
          if (containerRef.current) {
            containerRef.current.scrollTop = savedPosition;
            isRestoring.current = false;
          }
        }, 50);
      }
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchLogs();
  }, [jobId]);

  // Auto refresh for pending jobs or incomplete analysis
  useEffect(() => {
    if (!autoRefresh) return;

    // Continue refreshing if analysis has incomplete parts, even if job status is "ready"
    const shouldKeepRefreshing = hasIncompleteAnalysis();
    if (!shouldKeepRefreshing) return;

    const interval = setInterval(() => {
      fetchLogs();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, jobId, reportData]);

  // Track scroll position as user scrolls
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (!isRestoring.current) {
        const newPosition = container.scrollTop;
        scrollPosition.current = newPosition;
        // Also store in sessionStorage to survive component re-renders
        try {
          sessionStorage.setItem(
            `scrollPosition_${jobId}`,
            newPosition.toString(),
          );
        } catch {
          // Ignore storage errors
        }
      }
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [reportData, logContent]); // Add dependencies so it runs after content is rendered

  // Re-parse when mode changes
  useEffect(() => {
    if (logContent && !isRawMode && !reportData) {
      try {
        const parsed = parseJSONLLogs(logContent);
        setReportData(parsed);
      } catch (err) {
        console.error("Error parsing logs:", err);
        setError("Failed to parse log data");
      }
    }
  }, [isRawMode, logContent, reportData]);

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading logs...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center mb-2">
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
          <h3 className="ml-2 text-sm font-medium text-red-800">
            Error Loading Logs
          </h3>
        </div>
        <p className="text-sm text-red-700">{error}</p>
        <button
          onClick={fetchLogs}
          className="mt-3 text-sm text-red-800 hover:text-red-900 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!logContent) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-center mb-2">
          <div className="flex-shrink-0">
            <svg
              className="h-5 w-5 text-yellow-400"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <h3 className="ml-2 text-sm font-medium text-yellow-800">
            No Logs Found
          </h3>
        </div>
        <p className="text-sm text-yellow-700">
          Logs for job {jobId} are not available yet. This might be normal if
          the job just started.
        </p>
        {autoRefresh && (
          <p className="text-xs text-yellow-600 mt-1">
            Auto-refreshing every {refreshInterval / 1000} seconds...
          </p>
        )}
      </div>
    );
  }

  // Raw mode - show plain text logs
  if (isRawMode) {
    const logTitle = `Raw Logs - Job: ${jobId}${
      lastFetch ? ` | Last updated: ${format(lastFetch, "HH:mm:ss")}` : ""
    }`;

    return (
      <div className="h-full p-4">
        <CodeBlock
          language="text"
          title={logTitle}
          theme="dark"
          maxHeight="h-full"
          className="h-full"
        >
          {logContent}
        </CodeBlock>
      </div>
    );
  }

  // Rendered mode - show parsed report
  if (!reportData) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <p className="text-gray-600">
          Unable to parse log data for rendering. Switch to Raw mode to view the
          logs directly.
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-y-auto">
      <div className="space-y-6 p-1">
        {/* Header with last update info */}
        {lastFetch && (
          <div className="text-right text-xs text-gray-500 border-b pb-2">
            Last updated: {format(lastFetch, "PPpp")}
            {autoRefresh && (
              <span className="ml-2">
                (Auto-refreshing every {refreshInterval / 1000}s)
              </span>
            )}
          </div>
        )}

        {/* Header */}
        <div className="bg-white rounded-lg border border-gray-400 shadow-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">
              Analysis Report
            </h1>
            <div className="text-sm text-gray-700">Job ID: {jobId}</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-600">
                  Total Cost
                </span>
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {formatCost(reportData.total_cost)}
              </div>
            </div>

            <div className="bg-green-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <Zap className="w-4 h-4 text-green-600" />
                <span className="text-sm font-medium text-green-600">
                  Input Tokens
                </span>
              </div>
              <div className="text-2xl font-bold text-green-900">
                {formatTokens(reportData.total_input_tokens)}
              </div>
            </div>

            <div className="bg-purple-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <Zap className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-600">
                  Output Tokens
                </span>
              </div>
              <div className="text-2xl font-bold text-purple-900">
                {formatTokens(reportData.total_output_tokens)}
              </div>
            </div>

            <div className="bg-orange-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-4 h-4 text-orange-600" />
                <span className="text-sm font-medium text-orange-600">
                  Duration
                </span>
              </div>
              <div className="text-2xl font-bold text-orange-900">
                {reportData.analysis_duration}
              </div>
            </div>
          </div>
        </div>

        {/* Request Detection */}
        <SlideNavigation
          items={reportData.analysis_steps}
          title="Request Detection"
          icon={Eye}
          renderItem={(step, index) => <AnalysisStep step={step} />}
          getItemTitle={(step) =>
            `Step ${step.step_count} (${step.status || "unknown"})`
          }
          currentIndex={slidePositions.analysis}
          onIndexChange={(index) => updateSlidePosition("analysis", index)}
        />

        {/* Pagination Detection */}
        {reportData.pagination_detections.length > 0 && (
          <SlideNavigation
            items={reportData.pagination_detections}
            title="Parameter Detection"
            icon={Search}
            renderItem={(detection, index) => (
              <ParameterDetection detection={detection} index={index} />
            )}
            getItemTitle={(detection, index) =>
              `Attempt ${index + 1} (${detection.status || "unknown"})`
            }
            currentIndex={slidePositions.parameter}
            onIndexChange={(index) => updateSlidePosition("parameter", index)}
          />
        )}

        {/* Code Generation */}
        {reportData.code_generations.length > 0 && (
          <SlideNavigation
            items={reportData.code_generations}
            title="Structured Extraction"
            icon={Code}
            renderItem={(generation, index) => (
              <StructuredExtraction
                extraction={generation}
                index={index}
                totalExtractions={reportData.code_generations.length}
              />
            )}
            getItemTitle={(generation, index) =>
              `Extraction ${index + 1} (${generation.status || "unknown"})`
            }
            currentIndex={slidePositions.extraction}
            onIndexChange={(index) => updateSlidePosition("extraction", index)}
          />
        )}
      </div>
    </div>
  );
}
