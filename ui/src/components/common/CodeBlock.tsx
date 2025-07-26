"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";

interface CodeBlockProps {
  children: React.ReactNode;
  language?: string;
  title?: string;
  maxHeight?: string;
  className?: string;
  showCopy?: boolean;
  theme?: "light" | "dark";
}

export function CodeBlock({
  children,
  language = "text",
  title,
  maxHeight = "max-h-32",
  className = "",
  showCopy = true,
  theme = "light",
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(String(children));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const themeClasses =
    theme === "dark"
      ? "bg-gray-900 text-green-400 border-gray-700"
      : "bg-white text-gray-900 border-gray-200";

  return (
    <div className={`rounded-lg overflow-hidden border ${className}`}>
      {/* Header with title and copy button */}
      {(title || showCopy) && (
        <div
          className={`px-4 py-2 border-b flex items-center justify-between ${
            theme === "dark"
              ? "bg-gray-800 border-gray-700"
              : "bg-gray-50 border-gray-200"
          }`}
        >
          {title && (
            <span
              className={`text-xs font-mono ${
                theme === "dark" ? "text-gray-300" : "text-gray-600"
              }`}
            >
              {title}
            </span>
          )}
          {showCopy && (
            <button
              onClick={handleCopy}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                theme === "dark"
                  ? "text-gray-400 hover:text-gray-200 hover:bg-gray-700"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
              title="Copy to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3" />
                  <span>Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Code content */}
      <pre
        className={`text-xs p-3 overflow-auto ${maxHeight} ${themeClasses} font-mono leading-relaxed`}
      >
        {children}
      </pre>
    </div>
  );
}
