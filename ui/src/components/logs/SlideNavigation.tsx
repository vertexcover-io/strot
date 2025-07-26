"use client";

import { useState, useEffect, useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

interface SlideNavigationProps<T> {
  items: T[];
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  renderItem: (item: T, index: number) => React.ReactNode;
  getItemTitle?: (item: T, index: number) => string;
  className?: string;
  currentIndex?: number; // External state control
  onIndexChange?: (index: number) => void; // External state control
}

export function SlideNavigation<T>({
  items,
  title,
  icon: Icon,
  renderItem,
  getItemTitle,
  className = "",
  currentIndex: externalCurrentIndex,
  onIndexChange,
}: SlideNavigationProps<T>) {
  const [internalCurrentIndex, setInternalCurrentIndex] = useState(0);

  // Use external state if provided, otherwise use internal state
  const currentIndex =
    externalCurrentIndex !== undefined
      ? externalCurrentIndex
      : internalCurrentIndex;
  const setCurrentIndex = (index: number) => {
    if (onIndexChange) {
      onIndexChange(index);
    } else {
      setInternalCurrentIndex(index);
    }
  };

  // Adjust index if it's out of bounds
  useEffect(() => {
    if (currentIndex >= items.length && items.length > 0) {
      setCurrentIndex(items.length - 1);
    }
  }, [items.length, currentIndex]);

  if (items.length === 0) {
    return null;
  }

  const goToPrevious = () => {
    setCurrentIndex(Math.max(0, currentIndex - 1));
  };

  const goToNext = () => {
    setCurrentIndex(Math.min(items.length - 1, currentIndex + 1));
  };

  const goToSlide = (index: number) => {
    setCurrentIndex(index);
  };

  return (
    <div
      className={`bg-white rounded-lg border border-gray-400 shadow-md p-6 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        {Icon && <Icon className="w-5 h-5 text-gray-700" />}
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
          {items.length} {items.length === 1 ? "item" : "items"}
        </span>
      </div>

      {/* Bottom Controller */}
      {items.length > 1 && (
        <div className="flex justify-center">
          <div className="flex items-center gap-1 bg-gray-50 rounded-lg p-2 border">
            {/* First and Previous */}
            <button
              onClick={() => goToSlide(0)}
              disabled={currentIndex === 0}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700"
              title="First"
            >
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button
              onClick={goToPrevious}
              disabled={currentIndex === 0}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700"
              title="Previous"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {/* Page Numbers with Sliding Window */}
            <div className="flex gap-1 mx-2">
              {(() => {
                const maxVisible = 10;
                const totalPages = items.length;

                if (totalPages <= maxVisible) {
                  // Show all pages if 10 or fewer
                  return items.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => goToSlide(idx)}
                      className={`min-w-8 h-8 rounded font-semibold text-sm transition-colors ${
                        idx === currentIndex
                          ? "bg-blue-500 text-white"
                          : "text-gray-600 hover:bg-gray-200"
                      }`}
                      title={
                        getItemTitle
                          ? getItemTitle(items[idx], idx)
                          : `Item ${idx + 1}`
                      }
                    >
                      {idx + 1}
                    </button>
                  ));
                }

                // Sliding window logic for more than 10 pages
                let startIdx = Math.max(
                  0,
                  currentIndex - Math.floor(maxVisible / 2),
                );
                let endIdx = Math.min(
                  totalPages - 1,
                  startIdx + maxVisible - 1,
                );

                // Adjust window if we're near the end
                if (endIdx - startIdx < maxVisible - 1) {
                  startIdx = Math.max(0, endIdx - maxVisible + 1);
                }

                const visiblePages = [];
                for (let i = startIdx; i <= endIdx; i++) {
                  visiblePages.push(i);
                }

                return visiblePages.map((idx) => (
                  <button
                    key={idx}
                    onClick={() => goToSlide(idx)}
                    className={`min-w-8 h-8 rounded font-semibold text-sm transition-colors ${
                      idx === currentIndex
                        ? "bg-blue-500 text-white"
                        : "text-gray-600 hover:bg-gray-200"
                    }`}
                    title={
                      getItemTitle
                        ? getItemTitle(items[idx], idx)
                        : `Item ${idx + 1}`
                    }
                  >
                    {idx + 1}
                  </button>
                ));
              })()}
            </div>

            {/* Next and Last */}
            <button
              onClick={goToNext}
              disabled={currentIndex === items.length - 1}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700"
              title="Next"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => goToSlide(items.length - 1)}
              disabled={currentIndex === items.length - 1}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700"
              title="Last"
            >
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Current Item Display */}
      <div className="mb-6">
        {renderItem(items[currentIndex], currentIndex)}
      </div>
    </div>
  );
}
