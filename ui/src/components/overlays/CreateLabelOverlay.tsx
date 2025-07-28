"use client";

import { useState } from "react";
import { Overlay } from "./Overlay";
import { LabelCreate } from "@/types";
import { apiClient } from "@/lib/api-client";

interface CreateLabelOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onLabelCreated: () => void;
}

export function CreateLabelOverlay({
  isOpen,
  onClose,
  onLabelCreated,
}: CreateLabelOverlayProps) {
  const [formData, setFormData] = useState<LabelCreate>({
    name: "",
    requirement: "",
    output_schema: {},
  });
  const [schemaText, setSchemaText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  const handleSchemaChange = (value: string) => {
    setSchemaText(value);
    setSchemaError(null);

    if (!value.trim()) {
      setFormData((prev) => ({ ...prev, output_schema: {} }));
      return;
    }

    try {
      const parsed = JSON.parse(value);
      setFormData((prev) => ({ ...prev, output_schema: parsed }));
    } catch (err) {
      setSchemaError("Invalid JSON format");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name || !formData.requirement) {
      setError("Please fill in all required fields");
      return;
    }

    if (schemaError) {
      setError("Please fix the JSON schema errors");
      return;
    }

    // Validate label name format (simple validation)
    if (!/^[a-z0-9_]+$/.test(formData.name)) {
      setError(
        "Label name must contain only lowercase letters, numbers, and underscores",
      );
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await apiClient.createLabel(formData);

      // Reset form
      setFormData({ name: "", requirement: "", output_schema: {} });
      setSchemaText("");
      onLabelCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create label");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setFormData({ name: "", requirement: "", output_schema: {} });
      setSchemaText("");
      setError(null);
      setSchemaError(null);
      onClose();
    }
  };

  const getExampleSchema = () => {
    return JSON.stringify(
      {
        type: "object",
        properties: {
          title: {
            type: "string",
            description: "The title of the item",
          },
          description: {
            type: "string",
            description: "A description of the item",
          },
          price: {
            type: "number",
            description: "The price as a number",
          },
        },
        required: ["title"],
      },
      null,
      2,
    );
  };

  const insertExampleSchema = () => {
    const example = getExampleSchema();
    setSchemaText(example);
    handleSchemaChange(example);
  };

  return (
    <Overlay
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Label"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Name Field */}
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Label Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="name"
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder="e.g., product_reviews, news_articles"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900"
            required
            disabled={loading}
          />
          <p className="mt-1 text-sm text-gray-500">
            Use lowercase letters, numbers, and underscores only
          </p>
        </div>

        {/* Requirement Field */}
        <div>
          <label
            htmlFor="requirement"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Requirement <span className="text-red-500">*</span>
          </label>
          <textarea
            id="requirement"
            value={formData.requirement}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, requirement: e.target.value }))
            }
            placeholder="Describe what data should be extracted from the webpage..."
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900"
            required
            disabled={loading}
          />
          <p className="mt-1 text-sm text-gray-500">
            Provide clear instructions for what data to extract
          </p>
        </div>

        {/* Output Schema Field */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label
              htmlFor="schema"
              className="block text-sm font-medium text-gray-700"
            >
              Output Schema (JSON)
            </label>
            <button
              type="button"
              onClick={insertExampleSchema}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={loading}
            >
              Insert Example
            </button>
          </div>
          <textarea
            id="schema"
            value={schemaText}
            onChange={(e) => handleSchemaChange(e.target.value)}
            placeholder="Enter JSON schema or click 'Insert Example' to get started..."
            rows={8}
            className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm text-gray-900 ${
              schemaError ? "border-red-300" : "border-gray-300"
            }`}
            disabled={loading}
          />
          {schemaError && (
            <p className="mt-1 text-sm text-red-600">{schemaError}</p>
          )}
          <p className="mt-1 text-sm text-gray-500">
            Define the structure of the data to be extracted (JSON Schema
            format)
          </p>
        </div>

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
            disabled={
              loading ||
              !formData.name ||
              !formData.requirement ||
              !!schemaError
            }
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Creating..." : "Create Label"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
