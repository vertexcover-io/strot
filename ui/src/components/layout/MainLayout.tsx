"use client";

import { useState } from "react";
import { Sidebar, ActiveTab } from "./Sidebar";

interface MainLayoutProps {
  children: React.ReactNode;
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export function MainLayout({
  children,
  activeTab,
  onTabChange,
}: MainLayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={onTabChange}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={handleToggleSidebar}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">{children}</div>
    </div>
  );
}
