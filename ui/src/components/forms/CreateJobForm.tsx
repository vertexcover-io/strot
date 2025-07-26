"use client";

import { useState, useEffect } from "react";
import { CreateJobRequest, LabelResponse } from "@/types";
import { apiClient } from "@/lib/api-client";

interface CreateJobFormProps {
  onJobCreated: () => void;
}

export function CreateJobForm({ onJobCreated }: CreateJobFormProps) {
  const [formData, setFormData] = useState<CreateJobRequest>({
    url: "",
    label: "",
  });
  const [labels, setLabels] = useState<LabelResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labelsLoading, setLabelsLoading] = useState(false);

  // Fetch labels on component mount
  useEffect(() => {
    fetchLabels();
  }, []);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200 p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Create New Job
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex flex-col lg:flex-row gap-4 lg:items-end">
          {/* URL Field */}
          <div className="flex-1">
            <label
              htmlFor="url"
              className="block text-sm font-medium text-gray-700 mb-1"
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
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder-gray-400 text-gray-900 bg-white"
              required
              disabled={loading}
            />
          </div>

          {/* Label Selection */}
          <div className="w-full lg:w-64">
            <label
              htmlFor="label"
              className="block text-sm font-medium text-gray-700 mb-1"
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
          </div>

          {/* Submit Button */}
          <div className="lg:flex-shrink-0">
            <button
              type="submit"
              disabled={loading || !formData.url || !formData.label}
              className="w-full lg:w-auto px-6 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
