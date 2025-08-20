"use client";

import { PaginationDetection as PaginationDetectionType } from "@/lib/report-generator";
import { LLMCall } from "./LLMCall";
import { CodeBlock } from "../common/CodeBlock";
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
      {detection.potential_pagination_parameters &&
        Object.keys(detection.potential_pagination_parameters).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              Potential Pagination Parameters Analyzed
            </h4>
            <CodeBlock
              title="potential_pagination_parameters.json"
              language="json"
              maxHeight="max-h-40"
            >
              {JSON.stringify(
                detection.potential_pagination_parameters,
                null,
                2,
              )}
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

        {/* Pagination Strategy Info */}
        {detection.status === "success" && detection.strategy && (
          <div>
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              Strategy Info
            </h4>
            <CodeBlock title="info.json" language="json" maxHeight="max-h-40">
              {JSON.stringify(detection.strategy, null, 2)}
            </CodeBlock>
          </div>
        )}
      </div>
    </div>
  );
}
