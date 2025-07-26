"use client";

import { LogEvent } from "@/lib/report-generator";
import { CheckCircle, XCircle, Clock } from "lucide-react";
import { CodeBlock } from "../common/CodeBlock";

interface LLMCallProps {
  call: LogEvent;
}

export function LLMCall({ call }: LLMCallProps) {
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();

  return (
    <div className="bg-purple-50 p-3 rounded border">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {getStatusIcon(call.status)}
          {call.provider && call.model && (
            <span className="text-sm font-medium text-purple-700">
              {call.provider} / {call.model}
            </span>
          )}
        </div>
        {(call.input_tokens || call.output_tokens) && (
          <div className="text-sm text-gray-700">
            {formatTokens((call.input_tokens || 0) + (call.output_tokens || 0))}{" "}
            tokens
            {call.cost && ` • ${formatCost(call.cost)}`}
          </div>
        )}
      </div>
      {call.result && (
        <CodeBlock
          title="LLM Response"
          language="json"
          maxHeight="max-h-32"
          showCopy={true}
        >
          {call.result}
        </CodeBlock>
      )}
    </div>
  );
}
