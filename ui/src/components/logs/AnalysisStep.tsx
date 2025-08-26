"use client";

import { AnalysisStep as AnalysisStepType } from "@/lib/report-generator";
import { LLMCall } from "./LLMCall";
import { CodeBlock } from "../common/CodeBlock";
import { CheckCircle, XCircle, AlertCircle, Clock } from "lucide-react";

interface AnalysisStepProps {
  step: AnalysisStepType;
}

export function AnalysisStep({ step }: AnalysisStepProps) {
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="border border-gray-300 rounded-lg">
      {/* Step Header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold bg-blue-100 text-blue-800">
              {step.step_count}
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                Step {step.step_count}
              </div>
              {step.method && step.url && (
                <div className="text-sm text-gray-600">
                  {step.method} {step.url}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(step.status)}
            <span
              className={`text-sm font-medium px-2 py-1 rounded-full ${
                step.status === "success"
                  ? "bg-green-100 text-green-800"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {step.status == "success" ? "Response Match" : "No Response"}
            </span>
          </div>
        </div>
      </div>

      {/* Step Content */}
      <div className="px-4 py-4">
        {/* 1. LLM Completions (exclude pending) */}
        {step.sub_events.filter(
          (event) =>
            event.action === "llm-completion" && event.status !== "pending",
        ).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              LLM Analysis
            </h4>
            <div className="space-y-3">
              {step.sub_events
                .filter(
                  (event) =>
                    event.action === "llm-completion" &&
                    event.status !== "pending",
                )
                .map((event, idx) => (
                  <LLMCall key={idx} call={event} />
                ))}
            </div>
          </div>
        )}

        {/* 2. Performed Actions with Context */}
        {step.sub_events.filter(
          (event) => event.context && event.action !== "llm-completion",
        ).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-semibold text-gray-800 mb-3">
              Actions Performed
            </h4>
            <div className="space-y-6">
              {step.sub_events
                .filter(
                  (event) => event.context && event.action !== "llm-completion",
                )
                .slice(0, 2) // Max 2 actions
                .map((event, idx) => (
                  <div
                    key={idx}
                    className="bg-blue-50 p-6 rounded-lg border border-blue-200"
                  >
                    {/* Large Screenshot */}
                    <div className="mb-4">
                      <img
                        src={`data:image/png;base64,${event.context}`}
                        alt={`${event.action} screenshot`}
                        className="w-full h-auto border rounded-lg shadow-md cursor-pointer hover:shadow-lg transition-shadow max-h-[500px] object-contain mx-auto"
                        onClick={(e) => {
                          const img = e.target as HTMLImageElement;
                          window.open(img.src, "_blank");
                        }}
                      />
                    </div>

                    {/* Centered Step Name */}
                    {event.step && (
                      <div className="text-center mb-2">
                        <span className="text-lg font-semibold text-blue-900 bg-blue-100 px-3 py-1 rounded-full">
                          {event.step}
                        </span>
                      </div>
                    )}

                    {/* Centered Action Details */}
                    <div className="text-center space-y-1">
                      <div className="text-base font-medium text-blue-800 capitalize">
                        {event.action}
                        {event.point && (
                          <span className="ml-2 text-sm font-mono bg-blue-100 px-2 py-1 rounded">
                            {typeof event.point === "string"
                              ? event.point
                              : `{"x": ${Math.round(
                                  event.point.x,
                                )}, "y": ${Math.round(event.point.y)}}`}
                          </span>
                        )}
                      </div>

                      {/* Target selector (if exists) */}
                      {event.target && (
                        <div className="text-xs text-blue-600 font-mono bg-blue-100 px-2 py-1 rounded inline-block max-w-full truncate">
                          {event.target}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 3. Step Metadata */}
        <div className="space-y-4">
          {step.reason && (
            <div>
              <span className="text-sm font-medium text-gray-700">Reason:</span>
              <div className="text-sm text-gray-900 mt-1 bg-gray-50 p-2 rounded">
                {step.reason}
              </div>
            </div>
          )}

          {step.method && step.url && (
            <div>
              <span className="text-sm font-medium text-gray-700">
                API Request:
              </span>
              <div className="text-sm text-gray-900 mt-1 bg-gray-50 p-2 rounded font-mono">
                {step.method} {step.url}
              </div>
            </div>
          )}

          {step.queries && Object.keys(step.queries).length > 0 && (
            <div>
              <span className="text-sm font-medium text-gray-700">
                Query Parameters:
              </span>
              <div className="mt-2">
                <CodeBlock
                  title="query_parameters.json"
                  language="json"
                  maxHeight="max-h-40"
                >
                  {JSON.stringify(step.queries, null, 2)}
                </CodeBlock>
              </div>
            </div>
          )}

          {step.data && (
            <div>
              <span className="text-sm font-medium text-gray-700">
                Post Data:
              </span>
              <div className="mt-2">
                <CodeBlock
                  title="post_data.json"
                  language="json"
                  maxHeight="max-h-48"
                >
                  {typeof step.data === "string"
                    ? step.data
                    : JSON.stringify(step.data, null, 2)}
                </CodeBlock>
              </div>
            </div>
          )}

          {step.request_type && (
            <div>
              <span className="text-sm font-medium text-gray-700">
                Request Type:
              </span>
              <div className="text-sm text-gray-900 mt-1 bg-gray-50 p-2 rounded">
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    step.request_type === "ajax"
                      ? "bg-blue-100 text-blue-800"
                      : step.request_type === "ssr"
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {step.request_type.toUpperCase()}
                </span>
              </div>
            </div>
          )}

          {step.response_preprocessor && (
            <div>
              <span className="text-sm font-medium text-gray-700">
                Response Preprocessor:
              </span>
              <div className="mt-2">
                <CodeBlock
                  title="preprocessor_config.json"
                  language="json"
                  maxHeight="max-h-32"
                >
                  {JSON.stringify(step.response_preprocessor, null, 2)}
                </CodeBlock>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
