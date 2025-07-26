"use client";

import { useEffect } from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";

interface OverlayProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  maxWidth?: string;
}

export function Overlay({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  maxWidth,
}: OverlayProps) {
  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      // Prevent body scroll when overlay is open
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const getSizeClasses = () => {
    if (maxWidth) return `max-w-none ${maxWidth}`;

    switch (size) {
      case "sm":
        return "max-w-md"; // ~60% on mobile, smaller on desktop
      case "md":
        return "max-w-2xl"; // ~60% on most screens
      case "lg":
        return "max-w-6xl"; // ~75-80% on most screens
      case "xl":
        return "max-w-7xl"; // ~80-85% on most screens
      default:
        return "max-w-2xl";
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Overlay Content */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className={`relative w-full ${getSizeClasses()} mx-auto`}>
          <div className="bg-white rounded-lg shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
              <button
                onClick={onClose}
                className="p-2 hover:bg-gray-100 rounded-md transition-colors"
              >
                <XMarkIcon className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
