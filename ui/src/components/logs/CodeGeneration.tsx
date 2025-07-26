"use client";

import { CodeGeneration as CodeGenerationType } from "@/lib/report-generator";
import { LLMCall } from "./LLMCall";
import { CodeBlock } from "../common/CodeBlock";
import { CheckCircle, XCircle, AlertCircle, Clock } from "lucide-react";

interface CodeGenerationProps {
  generation: CodeGenerationType;
  index: number;
  totalGenerations: number;
}

export function CodeGeneration({
  generation,
  index,
  totalGenerations,
}: CodeGenerationProps) {
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
                {totalGenerations === 1
                  ? "Code Generation"
                  : `Generation Attempt ${index + 1}`}
              </div>
              <div className="text-sm text-gray-600">
                Generating Python extraction code based on analysis
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(generation.status)}
            <span
              className={`text-sm font-medium px-2 py-1 rounded-full ${
                generation.status === "success"
                  ? "bg-green-100 text-green-800"
                  : generation.status === "failed"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {generation.status || "Unknown"}
            </span>
          </div>
        </div>
      </div>

      {/* 1. LLM Analysis */}
      {generation.llm_completion && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">
            LLM Analysis
          </h4>
          <LLMCall call={generation.llm_completion} />
        </div>
      )}

      {/* 2. Generated Code */}
      {generation.code && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">
            Generated Python Code
          </h4>
          <CodeBlock
            title="extraction_code.py"
            language="python"
            maxHeight="max-h-96"
            theme="dark"
          >
            {generation.code}
          </CodeBlock>
        </div>
      )}

      {/* 3. Result/Error Information */}
      <div className="space-y-4">
        {generation.reason && (
          <div>
            <span className="text-sm font-medium text-gray-700">
              {generation.status === "success"
                ? "Generation Result:"
                : "Error Details:"}
            </span>
            <div
              className={`text-sm mt-1 p-3 rounded border ${
                generation.status === "success"
                  ? "text-green-900 bg-green-50 border-green-200"
                  : generation.status === "failed"
                  ? "text-red-900 bg-red-50 border-red-200"
                  : "text-gray-900 bg-gray-50 border-gray-200"
              }`}
            >
              {generation.reason}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
