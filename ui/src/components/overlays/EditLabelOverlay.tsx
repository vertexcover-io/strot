"use client";

import { useState, useEffect } from "react";
import { Overlay } from "./Overlay";
import { LabelResponse, LabelUpdate } from "@/types";
import { apiClient } from "@/lib/api-client";

interface EditLabelOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onLabelUpdated: () => void;
  label: LabelResponse | null;
}

export function EditLabelOverlay({
  isOpen,
  onClose,
  onLabelUpdated,
  label,
}: EditLabelOverlayProps) {
  const [formData, setFormData] = useState<LabelUpdate>({
    requirement: "",
    output_schema: {},
  });
  const [schemaText, setSchemaText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);

  // Initialize form when label changes
  useEffect(() => {
    if (label && isOpen) {
      setFormData({
        requirement: label.requirement,
        output_schema: label.output_schema,
      });
      setSchemaText(JSON.stringify(label.output_schema, null, 2));
      setError(null);
      setSchemaError(null);
    }
  }, [label, isOpen]);

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

    if (!label) return;

    if (!formData.requirement) {
      setError("Requirement is required");
      return;
    }

    if (schemaError) {
      setError("Please fix the JSON schema errors");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await apiClient.updateLabel(label.id, formData);

      onLabelUpdated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update label");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
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

  if (!label) return null;

  return (
    <Overlay
      isOpen={isOpen}
      onClose={handleClose}
      title={`Edit Label: ${label.name}`}
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Name Field (Disabled) */}
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Label Name
          </label>
          <input
            type="text"
            id="name"
            value={label.name}
            disabled
            className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500 cursor-not-allowed"
          />
          <p className="mt-1 text-sm text-gray-500">
            Label name cannot be changed after creation
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
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
            className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm ${
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

        {/* Metadata */}
        <div className="p-4 bg-gray-50 rounded-md">
          <h4 className="text-sm font-medium text-gray-900 mb-2">
            Label Information
          </h4>
          <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
            <div>
              <span className="font-medium">Created:</span>{" "}
              {new Date(label.created_at).toLocaleString()}
            </div>
            <div>
              <span className="font-medium">Updated:</span>{" "}
              {new Date(label.updated_at).toLocaleString()}
            </div>
          </div>
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
            disabled={loading || !formData.requirement || schemaError}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Updating..." : "Update Label"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
