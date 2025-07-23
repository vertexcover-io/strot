"use client";

import { PaginationDetection as PaginationDetectionType } from "@/lib/report-generator";
import { LLMCall } from "./LLMCall";
import { CodeBlock } from "./CodeBlock";
import { CheckCircle, XCircle, AlertCircle, Clock } from "lucide-react";

interface PaginationDetectionProps {
  detection: PaginationDetectionType;
  index: number;
}

export function PaginationDetection({
  detection,
  index,
}: PaginationDetectionProps) {
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" />;
      case "pending":
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold bg-purple-100 text-purple-800">
              {index + 1}
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                Pagination Detection Attempt {index + 1}
              </div>
              <div className="text-sm text-gray-600">
                Analyzing API request structure for pagination patterns
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(detection.status)}
            <span
              className={`text-sm font-medium px-2 py-1 rounded-full ${
                detection.status === "success"
                  ? "bg-green-100 text-green-800"
                  : detection.status === "failed"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {detection.status || "Unknown"}
            </span>
          </div>
        </div>

        {/* Strategy Result */}
        {detection.strategy && (
          <div className="text-center">
            <span className="text-lg font-semibold text-purple-900 bg-purple-100 px-4 py-2 rounded-full">
              Strategy: {detection.strategy}
            </span>
          </div>
        )}
      </div>

      {/* 1. LLM Analysis (exclude pending) */}
      {detection.llm_calls.filter((call) => call.status !== "pending").length >
        0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">
            LLM Analysis
          </h4>
          <div className="space-y-3">
            {detection.llm_calls
              .filter((call) => call.status !== "pending")
              .map((call, idx) => (
                <LLMCall key={idx} call={call} />
              ))}
          </div>
        </div>
      )}

      {/* 2. Request Parameters Analysis */}
      {detection.request_parameters &&
        Object.keys(detection.request_parameters).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              Request Parameters Analyzed
            </h4>
            <CodeBlock
              title="request_parameters.json"
              language="json"
              maxHeight="max-h-40"
            >
              {JSON.stringify(detection.request_parameters, null, 2)}
            </CodeBlock>
          </div>
        )}

      {/* 3. Detection Results */}
      <div className="space-y-4">
        {detection.reason && (
          <div>
            <span className="text-sm font-medium text-gray-700">
              Analysis Result:
            </span>
            <div className="text-sm text-gray-900 mt-1 bg-gray-50 p-3 rounded border">
              {detection.reason}
            </div>
          </div>
        )}

        {/* Pagination Strategy Details */}
        {detection.status === "success" && detection.strategy && (
          <div>
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              Strategy Details
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(() => {
                // Define strategy-specific fields based on ayejax/pagination/strategy.py
                const strategyFields = {
                  "page-based": ["page_key", "limit_key"],
                  "page-offset": ["page_key", "offset_key", "base_offset"],
                  "limit-offset": ["limit_key", "offset_key"],
                  "cursor-based": ["cursor_key", "limit_key"],
                };

                const relevantFields =
                  strategyFields[
                    detection.strategy as keyof typeof strategyFields
                  ] || [];

                return Object.entries(detection as any)
                  .filter(
                    ([key, value]) =>
                      relevantFields.includes(key) &&
                      value !== undefined &&
                      value !== null &&
                      value !== "",
                  )
                  .map(([key, value]) => {
                    const isObject =
                      typeof value === "object" && value !== null;
                    const displayKey = key
                      .split("_")
                      .map(
                        (word) => word.charAt(0).toUpperCase() + word.slice(1),
                      )
                      .join(" ");

                    return (
                      <div
                        key={key}
                        className="bg-green-50 p-3 rounded-lg border border-green-200"
                      >
                        <span className="text-sm font-medium text-green-700">
                          {displayKey}:
                        </span>
                        {isObject ? (
                          <CodeBlock
                            title={`${key}.json`}
                            language="json"
                            maxHeight="max-h-32"
                            showCopy={false}
                            className="mt-1"
                          >
                            {JSON.stringify(value, null, 2)}
                          </CodeBlock>
                        ) : (
                          <div className="text-sm font-mono text-green-900 mt-1 bg-green-100 px-2 py-1 rounded">
                            {String(value)}
                          </div>
                        )}
                      </div>
                    );
                  });
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
