"use client";

import { ReportData } from "@/lib/report-generator";
import { SlideNavigation } from "./SlideNavigation";
import { AnalysisStep } from "./AnalysisStep";
import { PaginationDetection } from "./PaginationDetection";
import { CodeGeneration } from "./CodeGeneration";
import { format } from "date-fns";
import { Clock, DollarSign, Zap, Eye, Code, Search } from "lucide-react";

interface ReportViewerProps {
  reportData: ReportData;
}

export function ReportViewer({ reportData }: ReportViewerProps) {
  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-400 shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Analysis Report</h1>
          <div className="text-sm text-gray-700">
            Generated on {format(new Date(), "PPpp")}
          </div>
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

      {/* Site Analysis */}
      <SlideNavigation
        items={reportData.analysis_steps}
        title="Site Analysis"
        icon={Eye}
        renderItem={(step, index) => <AnalysisStep step={step} />}
        getItemTitle={(step) =>
          `Step ${step.step_count} (${step.status || "unknown"})`
        }
      />

      {/* Pagination Detection */}
      {reportData.pagination_detections.length > 0 && (
        <SlideNavigation
          items={reportData.pagination_detections}
          title="Pagination Detection"
          icon={Search}
          renderItem={(detection, index) => (
            <PaginationDetection detection={detection} index={index} />
          )}
          getItemTitle={(detection, index) =>
            `Attempt ${index + 1} (${detection.status || "unknown"})`
          }
        />
      )}

      {/* Code Generation */}
      {reportData.code_generations.length > 0 && (
        <SlideNavigation
          items={reportData.code_generations}
          title="Code Generation"
          icon={Code}
          renderItem={(generation, index) => (
            <CodeGeneration
              generation={generation}
              index={index}
              totalGenerations={reportData.code_generations.length}
            />
          )}
          getItemTitle={(generation, index) =>
            `Generation ${index + 1} (${generation.status || "unknown"})`
          }
        />
      )}
    </div>
  );
}
