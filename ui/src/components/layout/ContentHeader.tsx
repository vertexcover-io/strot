"use client";

import { ArrowPathIcon, PlusIcon } from "@heroicons/react/24/outline";
import { ActiveTab } from "./Sidebar";

interface ContentHeaderProps {
  activeTab: ActiveTab;
  title: string;
  onRefresh?: () => void;
  onCreate?: () => void;
  isLoading?: boolean;
}

export function ContentHeader({
  activeTab,
  title,
  onRefresh,
  onCreate,
  isLoading = false,
}: ContentHeaderProps) {
  const getCreateButtonText = () => {
    return activeTab === "jobs" ? "Create Job" : "Create Label";
  };

  return (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-600 mt-1">
            {activeTab === "jobs"
              ? "Manage and monitor your analysis jobs"
              : "Configure labels for data extraction"}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Refresh Button - Only show if onRefresh is provided */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className={`inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors ${
                isLoading ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              <ArrowPathIcon
                className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          )}

          {/* Create Button - Only show if onCreate is provided */}
          {onCreate && (
            <button
              onClick={onCreate}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              <PlusIcon className="h-4 w-4 mr-2" />
              {getCreateButtonText()}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
