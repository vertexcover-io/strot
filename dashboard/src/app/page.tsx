"use client";

import { useState } from "react";
import { Job } from "@/types";
import { JobList } from "@/components/JobList";
import { JobDetail } from "@/components/JobDetail";

export default function Home() {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const handleRefreshJob = async () => {
    if (!selectedJob) return;

    try {
      const response = await fetch(`/api/jobs/${selectedJob.id}`);
      if (!response.ok) {
        throw new Error("Failed to fetch job details");
      }
      const updatedJob: Job = await response.json();
      setSelectedJob(updatedJob);
    } catch (error) {
      console.error("Error refreshing job:", error);
      // You could add toast notification here
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {selectedJob ? (
          <JobDetail
            job={selectedJob}
            onBack={() => setSelectedJob(null)}
            onRefresh={handleRefreshJob}
          />
        ) : (
          <JobList onJobSelect={setSelectedJob} />
        )}
      </div>
    </main>
  );
}
