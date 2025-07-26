"use client";

import { useState, useEffect, useRef } from "react";
import {
  MagnifyingGlassIcon,
  TrashIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";
import { JobListItem, JobStatus, LabelResponse } from "@/types";
import { apiClient } from "@/lib/api-client";
import { CreateJobForm } from "../forms/CreateJobForm";

interface JobsViewProps {
  onJobClick: (job: JobListItem) => void;
  refreshTrigger?: number;
  onJobCreated?: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export function JobsView({
  onJobClick,
  refreshTrigger,
  onJobCreated,
  onRefresh,
  isLoading,
}: JobsViewProps) {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters and pagination
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [labelFilter, setLabelFilter] = useState<string>("");
  const [currentPage, setCurrentPage] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);

  // Labels for dropdown
  const [labels, setLabels] = useState<LabelResponse[]>([]);
  const [labelsLoading, setLabelsLoading] = useState(false);

  const limit = 20;
  const searchInputRef = useRef<HTMLInputElement>(null);

  const fetchJobs = async (offset: number = 0) => {
    const activeElement = document.activeElement;
    const wasSearchFocused = activeElement === searchInputRef.current;

    try {
      setLoading(true);
      const response = await apiClient.listJobs({
        limit,
        offset,
        search: search || undefined,
        status: statusFilter || undefined,
        label: labelFilter || undefined,
      });

      setJobs(response.jobs);
      setTotalCount(response.total);
      setHasNext(response.has_next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch jobs");
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

  const fetchLabels = async () => {
    try {
      setLabelsLoading(true);
      const response = await apiClient.listLabels({ limit: 100 });
      setLabels(response.labels);
    } catch (err) {
      console.error("Failed to fetch labels:", err);
    } finally {
      setLabelsLoading(false);
    }
  };

  // Fetch labels on component mount
  useEffect(() => {
    fetchLabels();
  }, []);

  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setCurrentPage(0);
      fetchJobs(0);
    }, 300); // 300ms debounce

    return () => clearTimeout(timeoutId);
  }, [search, statusFilter, labelFilter, refreshTrigger]);

  // Handle pagination
  useEffect(() => {
    if (currentPage > 0) {
      fetchJobs(currentPage * limit);
    }
  }, [currentPage]);

  const handleDeleteJob = async (jobId: string, status: JobStatus) => {
    if (status === "pending") {
      alert(
        "Cannot delete job in pending state. Wait for it to complete or fail.",
      );
      return;
    }

    if (!confirm("Are you sure you want to delete this job?")) {
      return;
    }

    try {
      await apiClient.deleteJob(jobId);
      // Refresh the list
      fetchJobs(currentPage * limit);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete job");
    }
  };

  const getStatusBadge = (status: JobStatus) => {
    const baseClasses = "px-2 py-1 text-xs font-medium rounded-full";
    switch (status) {
      case "pending":
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      case "ready":
        return `${baseClasses} bg-green-100 text-green-800`;
      case "failed":
        return `${baseClasses} bg-red-100 text-red-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow">
        <div className="p-6">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Create Job Form */}
      <CreateJobForm onJobCreated={onJobCreated || (() => {})} />

      {/* Jobs List */}
      <div className="bg-white rounded-lg shadow">
        {/* Search and Filters */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Search by URL..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400 text-gray-900 bg-white"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className={`px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                !statusFilter ? "text-gray-500" : "text-gray-900"
              }`}
            >
              <option value="" className="text-gray-400">
                All Status
              </option>
              <option value="pending" className="text-gray-900">
                Pending
              </option>
              <option value="ready" className="text-gray-900">
                Ready
              </option>
              <option value="failed" className="text-gray-900">
                Failed
              </option>
            </select>

            {/* Label Filter */}
            {labelsLoading ? (
              <div className="px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500">
                Loading labels...
              </div>
            ) : (
              <select
                value={labelFilter}
                onChange={(e) => setLabelFilter(e.target.value)}
                className={`px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                  !labelFilter ? "text-gray-500" : "text-gray-900"
                }`}
              >
                <option value="" className="text-gray-400">
                  All Labels
                </option>
                {labels.map((label) => (
                  <option
                    key={label.id}
                    value={label.name}
                    className="text-gray-900"
                  >
                    {label.name}
                  </option>
                ))}
              </select>
            )}

            {/* Refresh Button */}
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
          </div>
        </div>

        {/* Jobs List */}
        <div className="overflow-x-auto">
          {error && (
            <div className="p-4 bg-red-50 border-l-4 border-red-400">
              <p className="text-red-700">{error}</p>
            </div>
          )}

          {jobs.length === 0 && !loading ? (
            <div className="p-8 text-center text-gray-500">
              <p>No jobs found</p>
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    URL
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Label
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Usage
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => onJobClick(job)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div
                        className="text-sm text-gray-900 max-w-xs truncate"
                        title={job.url}
                      >
                        {job.url}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {job.label_name}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={getStatusBadge(job.status)}>
                        {job.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(job.initiated_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {job.usage_count} times
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteJob(job.id, job.status);
                        }}
                        disabled={job.status === "pending"}
                        className={`p-1 rounded-md transition-colors ${
                          job.status === "pending"
                            ? "text-gray-400 cursor-not-allowed"
                            : "text-red-600 hover:bg-red-50"
                        }`}
                        title={
                          job.status === "pending"
                            ? "Cannot delete pending job"
                            : "Delete job"
                        }
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {jobs.length > 0 && (
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
    </div>
  );
}
