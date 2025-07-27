"use client";

import { useState, useEffect, useRef } from "react";
import {
  MagnifyingGlassIcon,
  PencilIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { LabelResponse } from "@/types";
import { apiClient } from "@/lib/api-client";

interface LabelsViewProps {
  onLabelClick: (label: LabelResponse) => void;
  refreshTrigger?: number;
}

export function LabelsView({ onLabelClick, refreshTrigger }: LabelsViewProps) {
  const [labels, setLabels] = useState<LabelResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters and pagination
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);

  const limit = 20;
  const searchInputRef = useRef<HTMLInputElement>(null);

  const fetchLabels = async (offset: number = 0) => {
    const activeElement = document.activeElement;
    const wasSearchFocused = activeElement === searchInputRef.current;

    try {
      setLoading(true);
      const response = await apiClient.listLabels({
        limit,
        offset,
        search: search || undefined,
      });

      setLabels(response.labels);
      setTotalCount(response.total);
      setHasNext(response.has_next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch labels");
    } finally {
      setLoading(false);

      // Restore focus after search completes
      setTimeout(() => {
        if (wasSearchFocused && searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 0);
    }
  };

  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setCurrentPage(0);
      fetchLabels(0);
    }, 300); // 300ms debounce

    return () => clearTimeout(timeoutId);
  }, [search, refreshTrigger]);

  // Handle pagination
  useEffect(() => {
    fetchLabels(currentPage * limit);
  }, [currentPage]);

  const handleDeleteLabel = async (labelId: string, labelName: string) => {
    if (
      !confirm(
        `Are you sure you want to delete the label "${labelName}"? This will also delete any associated jobs.`,
      )
    ) {
      return;
    }

    try {
      await apiClient.deleteLabel(labelId, true); // force delete
      // Refresh the list
      fetchLabels(currentPage * limit);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete label");
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const truncateText = (text: string, maxLength: number = 100) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + "...";
  };

  if (loading && labels.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow">
        <div className="p-6">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Search */}
      <div className="p-4 border-b border-gray-200">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search by name or requirement..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400 text-gray-900 bg-white"
          />
        </div>
      </div>

      {/* Labels List */}
      <div className="overflow-auto max-h-[calc(100vh-30rem)]">
        {error && (
          <div className="p-4 bg-red-50 border-l-4 border-red-400">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {labels.length === 0 && !loading ? (
          <div className="p-8 text-center text-gray-500">
            <p>No labels found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {labels.map((label) => (
              <div
                key={label.id}
                className="p-6 hover:bg-gray-50 cursor-pointer transition-colors"
                onClick={() => onLabelClick(label)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-lg font-medium text-gray-900">
                        {label.name}
                      </h3>
                      <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                        Label
                      </span>
                    </div>

                    <p className="text-sm text-gray-600 mb-3">
                      {truncateText(label.requirement)}
                    </p>

                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span>Created: {formatDate(label.created_at)}</span>
                      <span>Updated: {formatDate(label.updated_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onLabelClick(label);
                      }}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                      title="Edit label"
                    >
                      <PencilIcon className="h-4 w-4" />
                    </button>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteLabel(label.id, label.name);
                      }}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                      title="Delete label"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {labels.length > 0 && (
        <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing {currentPage * limit + 1} to{" "}
            {Math.min((currentPage + 1) * limit, totalCount)} of {totalCount}{" "}
            results
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0 || loading}
              className="px-3 py-1 text-sm text-gray-700 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-700">
              Page {currentPage + 1}
            </span>
            <button
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={!hasNext || loading}
              className="px-3 py-1 text-sm text-gray-700 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
