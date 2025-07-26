"use client";

import { useState, useEffect } from "react";
import { Overlay } from "./Overlay";
import { CreateJobRequest, LabelResponse } from "@/types";
import { apiClient } from "@/lib/api-client";

interface CreateJobOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onJobCreated: () => void;
}

export function CreateJobOverlay({
  isOpen,
  onClose,
  onJobCreated,
}: CreateJobOverlayProps) {
  const [formData, setFormData] = useState<CreateJobRequest>({
    url: "",
    label: "",
  });
  const [labels, setLabels] = useState<LabelResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labelsLoading, setLabelsLoading] = useState(false);

  // Fetch labels when overlay opens
  useEffect(() => {
    if (isOpen) {
      fetchLabels();
    }
  }, [isOpen]);

  const fetchLabels = async () => {
    try {
      setLabelsLoading(true);
      const response = await apiClient.listLabels({ limit: 100 });
      setLabels(response.labels);

      // Auto-select if there's only one label
      if (response.labels.length === 1 && !formData.label) {
        setFormData((prev) => ({ ...prev, label: response.labels[0].name }));
      }
    } catch (err) {
      console.error("Failed to fetch labels:", err);
    } finally {
      setLabelsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.url || !formData.label) {
      setError("Please fill in all required fields");
      return;
    }

    // Basic URL validation
    try {
      new URL(formData.url);
    } catch {
      setError("Please enter a valid URL");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await apiClient.createJob(formData);

      // Reset form
      setFormData({ url: "", label: "" });
      onJobCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setFormData({ url: "", label: "" });
      setError(null);
      onClose();
    }
  };

  return (
    <Overlay
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Job"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* URL Field */}
        <div>
          <label
            htmlFor="url"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Target URL <span className="text-red-500">*</span>
          </label>
          <input
            type="url"
            id="url"
            value={formData.url}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, url: e.target.value }))
            }
            placeholder="https://example.com/page-to-analyze"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400"
            required
            disabled={loading}
          />
          <p className="mt-1 text-sm text-gray-500">
            Enter the URL of the webpage you want to analyze
          </p>
        </div>

        {/* Label Selection */}
        <div>
          <label
            htmlFor="label"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Label <span className="text-red-500">*</span>
          </label>
          {labelsLoading ? (
            <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50">
              <span className="text-gray-500">Loading labels...</span>
            </div>
          ) : (
            <select
              id="label"
              value={formData.label}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, label: e.target.value }))
              }
              className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                !formData.label ? "text-gray-500" : "text-gray-900"
              }`}
              required
              disabled={loading}
            >
              <option value="" disabled className="text-gray-400">
                Select a label
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
          <p className="mt-1 text-sm text-gray-500">
            Choose the type of data to extract from the webpage
          </p>
        </div>

        {/* Selected Label Preview */}
        {formData.label && (
          <div className="p-4 bg-gray-50 rounded-md">
            <h4 className="text-sm font-medium text-gray-900 mb-2">
              Selected Label: {formData.label}
            </h4>
            {(() => {
              const selectedLabel = labels.find(
                (l) => l.name === formData.label,
              );
              return selectedLabel ? (
                <p className="text-sm text-gray-600">
                  {selectedLabel.requirement}
                </p>
              ) : null;
            })()}
          </div>
        )}

        {/* Form Actions */}
        <div className="flex justify-end space-x-3 pt-4 border-t">
          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading || !formData.url || !formData.label}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating..." : "Create Job"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
