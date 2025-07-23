"use client";

import { useState, useEffect } from "react";
import { Job, JobsResponse } from "@/types";
import { JobCard } from "./JobCard";
import { Loader, RefreshCw } from "lucide-react";

interface JobListProps {
  onJobSelect: (job: Job) => void;
}

export function JobList({ onJobSelect }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const fetchJobs = async (pageNum = 1, status = "") => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        page: pageNum.toString(),
        limit: "20",
      });

      if (status) {
        params.set("status", status);
      }

      const response = await fetch(`/api/jobs?${params}`);
      if (!response.ok) {
        throw new Error("Failed to fetch jobs");
      }

      const data: JobsResponse = await response.json();
      setJobs(data.jobs);
      setTotalPages(data.pagination.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs(page, statusFilter);
  }, [page, statusFilter]);

  const handleStatusFilter = (status: string) => {
    setStatusFilter(status);
    setPage(1);
  };

  const handleRefresh = () => {
    fetchJobs(page, statusFilter);
  };

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-red-600 mb-4">{error}</div>
        <button
          onClick={handleRefresh}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with filters and refresh */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Ayejax Jobs</h1>
        <div className="flex items-center gap-4">
          <select
            value={statusFilter}
            onChange={(e) => handleStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="ready">Ready</option>
            <option value="failed">Failed</option>
          </select>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader className="w-6 h-6 animate-spin text-blue-600" />
          <span className="ml-2 text-gray-600">Loading jobs...</span>
        </div>
      )}

      {/* Jobs grid */}
      {!loading && jobs.length > 0 && (
        <div className="grid gap-4">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} onClick={onJobSelect} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && jobs.length === 0 && (
        <div className="text-center py-8">
          <div className="text-gray-500 mb-4">No jobs found</div>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      )}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
