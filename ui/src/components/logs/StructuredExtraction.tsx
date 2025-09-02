"use client";

import { CodeGeneration as StructuredExtractionType } from "@/lib/report-generator";
import { LLMCall } from "./LLMCall";
import { CodeBlock } from "../common/CodeBlock";
import { CheckCircle, XCircle, AlertCircle, Clock } from "lucide-react";

interface StructuredExtractionProps {
  extraction: StructuredExtractionType;
  index: number;
  totalExtractions: number;
}

export function StructuredExtraction({
  extraction,
  index,
  totalExtractions,
}: StructuredExtractionProps) {
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
      <div className="bg-green-50 p-4 rounded-lg border border-green-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold bg-green-100 text-green-800">
              {index + 1}
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                {totalExtractions === 1
                  ? "Structured Extraction"
                  : `Extraction Attempt ${index + 1}`}
              </div>
              <div className="text-sm text-gray-600">
                Generating Python structured extraction code from API response
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(extraction.status)}
            <span
              className={`text-sm font-medium px-2 py-1 rounded-full ${
                extraction.status === "success"
                  ? "bg-green-100 text-green-800"
                  : extraction.status === "failed"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {extraction.status || "Unknown"}
            </span>
          </div>
        </div>
      </div>

      {/* 1. Input Information */}
      {(extraction.response_length !== undefined ||
        extraction.preprocessor) && (
        <div className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {extraction.response_length !== undefined && (
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                <div className="text-xs font-medium text-gray-600 mb-1">
                  Response Length
                </div>
                <div className="text-lg font-bold text-gray-900">
                  {extraction.response_length.toLocaleString()}
                </div>
                <div className="text-xs text-gray-600">
                  characters processed
                </div>
              </div>
            )}

            {extraction.preprocessor && (
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                <div className="text-xs font-medium text-gray-600 mb-1">
                  Preprocessor Configuration
                </div>
                <div className="text-xs text-gray-900 font-mono max-h-20 overflow-y-auto">
                  {JSON.stringify(extraction.preprocessor, null, 2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. LLM Analysis */}
      {extraction.llm_completion && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">
            LLM Analysis
          </h4>
          <LLMCall call={extraction.llm_completion} />
        </div>
      )}

      {/* 3. Generated Code */}
      {extraction.code && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">
            Generated Python Code
            {extraction.default_limit !== undefined && (
              <span className="ml-2 text-sm font-normal text-blue-600">
                (Legacy default limit: {extraction.default_limit})
              </span>
            )}
            {extraction.default_entity_count !== undefined && (
              <span className="ml-2 text-sm font-normal text-blue-600">
                (Default entity count: {extraction.default_entity_count})
              </span>
            )}
          </h4>
          <CodeBlock
            title="extract_data.py"
            language="python"
            maxHeight="max-h-96"
            theme="dark"
          >
            {extraction.code}
          </CodeBlock>
        </div>
      )}

      {/* 4. Result/Error Information */}
      <div className="space-y-4">
        {extraction.reason && (
          <div>
            <span className="text-sm font-medium text-gray-700">
              {extraction.status === "success"
                ? "Generation Result:"
                : "Error Details:"}
            </span>
            <div
              className={`text-sm mt-1 p-3 rounded border ${
                extraction.status === "success"
                  ? "text-green-900 bg-green-50 border-green-200"
                  : extraction.status === "failed"
                  ? "text-red-900 bg-red-50 border-red-200"
                  : "text-gray-900 bg-gray-50 border-gray-200"
              }`}
            >
              {extraction.reason}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
