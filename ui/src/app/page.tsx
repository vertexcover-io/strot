"use client";

import { useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { ContentHeader } from "@/components/layout/ContentHeader";
import { JobsView } from "@/components/views/JobsView";
import { LabelsView } from "@/components/views/LabelsView";
import { CreateLabelOverlay } from "@/components/overlays/CreateLabelOverlay";
import { EditLabelOverlay } from "@/components/overlays/EditLabelOverlay";
import { FullPageJobView } from "@/components/views/FullPageJobView";
import { ActiveTab } from "@/components/layout/Sidebar";
import { JobListItem, LabelResponse } from "@/types";

export default function Home() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("jobs");
  const [isLoading, setIsLoading] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Overlay states
  const [showCreateLabel, setShowCreateLabel] = useState(false);
  const [showEditLabel, setShowEditLabel] = useState(false);
  const [showJobDetail, setShowJobDetail] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<LabelResponse | null>(
    null,
  );
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const handleRefresh = async () => {
    setIsLoading(true);
    setRefreshTrigger((prev) => prev + 1);
    // Add a small delay to show loading state
    setTimeout(() => setIsLoading(false), 500);
  };

  const handleCreate = () => {
    setShowCreateLabel(true);
  };

  const handleJobClick = (job: JobListItem) => {
    setSelectedJobId(job.id);
    setShowJobDetail(true);
  };

  const handleLabelClick = (label: LabelResponse) => {
    setSelectedLabel(label);
    setShowEditLabel(true);
  };

  const handleJobCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleLabelCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleLabelUpdated = () => {
    setRefreshTrigger((prev) => prev + 1);
    setSelectedLabel(null);
  };

  const handleCloseEditLabel = () => {
    setShowEditLabel(false);
    setSelectedLabel(null);
  };

  const handleCloseJobDetail = () => {
    setShowJobDetail(false);
    setSelectedJobId(null);
  };

  const getTabTitle = (tab: ActiveTab) => {
    return tab === "jobs" ? "Jobs" : "Labels";
  };

  return (
    <>
      <MainLayout activeTab={activeTab} onTabChange={setActiveTab}>
        {/* Content Header */}
        <ContentHeader
          activeTab={activeTab}
          title={getTabTitle(activeTab)}
          onRefresh={activeTab === "labels" ? handleRefresh : undefined}
          onCreate={activeTab === "labels" ? handleCreate : undefined}
          isLoading={isLoading}
        />

        {/* Main Content Area */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full p-6">
            {activeTab === "jobs" ? (
              <JobsView
                onJobClick={handleJobClick}
                refreshTrigger={refreshTrigger}
                onJobCreated={handleJobCreated}
                onRefresh={handleRefresh}
                isLoading={isLoading}
              />
            ) : (
              <LabelsView
                onLabelClick={handleLabelClick}
                refreshTrigger={refreshTrigger}
              />
            )}
          </div>
        </div>
      </MainLayout>

      {/* Overlays */}

      <CreateLabelOverlay
        isOpen={showCreateLabel}
        onClose={() => setShowCreateLabel(false)}
        onLabelCreated={handleLabelCreated}
      />

      <EditLabelOverlay
        isOpen={showEditLabel}
        onClose={handleCloseEditLabel}
        onLabelUpdated={handleLabelUpdated}
        label={selectedLabel}
      />

      {selectedJobId && (
        <FullPageJobView
          isOpen={showJobDetail}
          onClose={handleCloseJobDetail}
          jobId={selectedJobId}
        />
      )}
    </>
  );
}
