"use client";

import { useState, useEffect } from "react";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  BriefcaseIcon,
  TagIcon,
} from "@heroicons/react/24/outline";

export type ActiveTab = "jobs" | "labels";

interface SidebarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({
  activeTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [windowWidth, setWindowWidth] = useState<number>(0);

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    // Set initial width
    setWindowWidth(window.innerWidth);

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Auto-collapse on small screens (768px threshold)
  const shouldAutoCollapse = windowWidth > 0 && windowWidth < 768;

  const tabs = [
    {
      id: "jobs" as ActiveTab,
      name: "Jobs",
      icon: BriefcaseIcon,
    },
    {
      id: "labels" as ActiveTab,
      name: "Labels",
      icon: TagIcon,
    },
  ];

  const effectiveCollapsed = shouldAutoCollapse || isCollapsed;

  return (
    <div
      className={`bg-white border-r border-gray-200 flex flex-col transition-all duration-300 ${
        effectiveCollapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        {!effectiveCollapsed && (
          <h1 className="text-lg font-semibold text-gray-900">Strot UI</h1>
        )}
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded-md hover:bg-gray-100 transition-colors"
          disabled={shouldAutoCollapse}
        >
          {effectiveCollapsed ? (
            <ChevronRightIcon className="h-5 w-5 text-gray-600" />
          ) : (
            <ChevronLeftIcon className="h-5 w-5 text-gray-600" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        <div className="space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`w-full flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive
                    ? "bg-blue-50 text-blue-700 border-r-2 border-blue-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
                title={effectiveCollapsed ? tab.name : undefined}
              >
                <Icon className="h-5 w-5 flex-shrink-0" />
                {!effectiveCollapsed && (
                  <span className="ml-3">{tab.name}</span>
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      {!effectiveCollapsed && (
        <div className="p-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">Strot UI v1.0</p>
        </div>
      )}
    </div>
  );
}
