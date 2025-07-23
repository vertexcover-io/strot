"use client";

import { Job } from "@/types";
import { formatDistanceToNow } from "date-fns";
import {
  Clock,
  ExternalLink,
  CheckCircle,
  XCircle,
  Loader,
} from "lucide-react";

interface JobCardProps {
  job: Job;
  onClick: (job: Job) => void;
}

export function JobCard({ job, onClick }: JobCardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ready":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "failed":
        return <XCircle className="w-5 h-5 text-red-500" />;
      case "pending":
        return <Loader className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = "px-2 py-1 rounded-full text-xs font-medium";
    switch (status) {
      case "ready":
        return `${baseClasses} bg-green-100 text-green-800`;
      case "failed":
        return `${baseClasses} bg-red-100 text-red-800`;
      case "pending":
        return `${baseClasses} bg-blue-100 text-blue-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  const truncateUrl = (url: string, maxLength: number = 60) => {
    if (url.length <= maxLength) return url;
    return `${url.substring(0, maxLength)}...`;
  };

  return (
    <div
      className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onClick(job)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {getStatusIcon(job.status)}
          <div>
            <h3 className="font-medium text-gray-900">{job.tag}</h3>
            <p className="text-sm text-gray-600 flex items-center gap-1">
              <ExternalLink className="w-4 h-4" />
              {truncateUrl(job.url)}
            </p>
          </div>
        </div>
        <span className={getStatusBadge(job.status)}>{job.status}</span>
      </div>

      <div className="text-sm text-gray-600 mb-3">{job.message}</div>

      <div className="flex items-center justify-between text-sm text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="w-4 h-4" />
          {formatDistanceToNow(new Date(job.createdAt), { addSuffix: true })}
        </div>
        {job.completedAt && (
          <div>
            Completed{" "}
            {formatDistanceToNow(new Date(job.completedAt), {
              addSuffix: true,
            })}
          </div>
        )}
      </div>

      {job.output && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-sm text-blue-600">
            ✓ Output available ({job.output.usageCount} uses)
          </div>
        </div>
      )}
    </div>
  );
}
