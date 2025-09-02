import { parseISO, differenceInSeconds } from "date-fns";

export interface LogEvent {
  event?: string;
  action?: string;
  status?: string;
  timestamp?: string;
  url?: string;
  query?: string;
  step_count?: number;
  step?: string;
  target?: string;
  point?: { x: number; y: number } | string;
  context?: string; // Base64 encoded screenshot data
  provider?: string;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  result?: string;
  reason?: string;
  method?: string;
  queries?: Record<string, unknown>;
  data?: unknown;
  code?: string;
  strategy?: { info: Record<string, unknown> } | Record<string, unknown>;
  potential_pagination_parameters?: Record<string, unknown>;
  // New unified parameter detection fields (inputs/outputs)
  request?: Record<string, unknown>;
  pagination_keys?: Record<string, unknown>;
  dynamic_parameter_keys?: string[];
  apply_parameters_code?: string;
  // New structured extraction fields (inputs/outputs)
  response_length?: number;
  preprocessor?: Record<string, unknown>;
  default_entity_count?: number;
  [key: string]: unknown;
}

export interface AnalysisStep {
  step_count: number;
  status?: string;
  method?: string;
  url?: string;
  queries?: Record<string, unknown>;
  data?: string | Record<string, unknown> | null;
  reason?: string;
  sub_events: LogEvent[];
  // Additional fields from new request-detection events
  request_type?: string;
  response_preprocessor?: Record<string, unknown>;
}

export interface PaginationDetection {
  status?: string;
  potential_pagination_parameters?: Record<string, unknown>;
  strategy?: { info: Record<string, unknown> } | Record<string, unknown>;
  llm_calls: LogEvent[];
  reason?: string;
  // New unified parameter detection fields
  request?: Record<string, unknown>;
  pagination_keys?: Record<string, unknown>;
  dynamic_parameter_keys?: string[];
  apply_parameters_code?: string;
}

export interface CodeGeneration {
  status?: string;
  code?: string;
  reason?: string;
  llm_completion?: LogEvent;
  // Legacy fields
  default_limit?: number;
  response_length?: number;
  preprocessor?: Record<string, unknown>;
  // New structured extraction fields
  default_entity_count?: number;
}

export interface ReportData {
  url: string;
  query: string;
  analysis_begin?: LogEvent;
  analysis_end?: LogEvent;
  analysis_steps: AnalysisStep[];
  pagination_detections: PaginationDetection[];
  code_generations: CodeGeneration[];
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  analysis_duration: string;
  final_result?: {
    api_url: string;
  };
}

export function parseJSONLLogs(jsonlContent: string): ReportData {
  const lines = jsonlContent
    .trim()
    .split("\n")
    .filter((line) => line.trim() && !line.includes("# ---<SEPARATOR>--- #"));
  const events: LogEvent[] = [];

  // Parse JSONL content
  for (const line of lines) {
    try {
      const outerEvent = JSON.parse(line);

      // Extract the actual log data from the "message" field if it exists
      if (outerEvent.message) {
        try {
          const innerEvent = JSON.parse(outerEvent.message);
          // Add outer timestamp if inner doesn't have it
          if (!innerEvent.timestamp && outerEvent.timestamp) {
            innerEvent.timestamp = outerEvent.timestamp;
          }
          events.push(innerEvent);
        } catch {
          // Skip invalid message content
          continue;
        }
      } else {
        events.push(outerEvent);
      }
    } catch {
      // Skip invalid JSON lines
      continue;
    }
  }

  // Initialize report data
  let url = "";
  let query = "";
  let analysis_begin: LogEvent | undefined;
  let analysis_end: LogEvent | undefined;
  const analysis_steps: AnalysisStep[] = [];
  const pagination_detections: PaginationDetection[] = [];
  const code_generations: CodeGeneration[] = [];

  let current_step: AnalysisStep | null = null;
  let current_pagination: PaginationDetection | null = null;
  let current_code_gen: CodeGeneration | null = null;

  // Process events in order
  for (const event of events) {
    const eventType = event.event || "unknown";
    const action = event.action || "";

    // Main analysis events (support old analysis, request-detection, parameter-detection, and structured-extraction)
    if (eventType === "analysis") {
      if (action === "begin") {
        analysis_begin = event;
        url = event.url || "";
        query = event.query || "";
      } else if (action === "end") {
        analysis_end = event;
      } else if (action === "run-step") {
        const step_count = event.step_count || 0;
        const status = event.status || "";

        if (status === "pending") {
          // Start a new step
          current_step = {
            step_count,
            status: "pending",
            sub_events: [],
          };
          analysis_steps.push(current_step);
        } else if (status === "success" || status === "failed") {
          // Update the current step with final status
          if (current_step && current_step.step_count === step_count) {
            current_step.status = status;
            current_step.method = event.method;
            current_step.url = event.url;
            current_step.queries = event.queries;
            current_step.data = event.data;
            current_step.reason = event.reason;
            // Capture additional fields from new request-detection events
            if (eventType === "request-detection" && event.request_type) {
              Object.assign(current_step, {
                request_type: event.request_type,
                response_preprocessor: event.response_preprocessor,
              });
            }
          }
          current_step = null; // Close the current step
        }
      } else if (
        action === "detect-pagination" ||
        action === "pagination-detection" ||
        action === "parameter-detection"
      ) {
        const status = event.status || "";
        if (status === "pending") {
          current_pagination = {
            status: "pending",
            potential_pagination_parameters:
              event.potential_pagination_parameters,
            strategy: undefined,
            llm_calls: [],
          };
        } else if (status === "success" || status === "failed") {
          if (current_pagination) {
            current_pagination.status = status;
            current_pagination.strategy = event.strategy;
            current_pagination.reason = event.reason;
            Object.assign(current_pagination, event);
            pagination_detections.push(current_pagination);
            current_pagination = null;
          }
        }
      } else if (
        action === "code-generation" ||
        action === "structured-extraction"
      ) {
        const status = event.status || "";
        if (status === "pending") {
          // Only create new code generation if we don't already have one pending
          if (!current_code_gen) {
            current_code_gen = {
              status: "pending",
            };
          }
        } else if (status === "success" || status === "failed") {
          // Only finalize if we have a current code generation and it has actual content
          if (current_code_gen && (event.code || current_code_gen.code)) {
            current_code_gen.status = status;
            if (event.code) {
              current_code_gen.code = event.code;
            }
            if (event.reason) {
              current_code_gen.reason = event.reason;
            }
            code_generations.push(current_code_gen);
            current_code_gen = null;
          }
        }
      }
    }

    // New request-detection events (individual steps from new Analyzer)
    else if (eventType === "request-detection" && action === "run-step") {
      const step_count = event.step_count || 0;
      const status = event.status || "";

      if (status === "pending") {
        // Start a new step
        current_step = {
          step_count,
          status: "pending",
          sub_events: [],
        };
        analysis_steps.push(current_step);
      } else if (status === "success" || status === "failed") {
        // Update the current step with final status
        if (current_step && current_step.step_count === step_count) {
          current_step.status = status;
          current_step.method = event.method;
          current_step.url = event.url;
          current_step.queries = event.queries;
          current_step.data = event.data;
          current_step.reason = event.reason;
          current_step.request_type = event.request_type;
          current_step.response_preprocessor = event.response_preprocessor;
        }
        current_step = null; // Close the current step
      }
    }

    // Sub-events go to current containers
    else if (eventType === "run-step" && current_step) {
      current_step.sub_events.push({
        ...event,
        timestamp: event.timestamp,
      });
    } else if (
      (eventType === "detect-pagination" ||
        eventType === "pagination-detection" ||
        eventType === "parameter-detection") &&
      action === "llm-completion" &&
      current_pagination
    ) {
      if (event.status !== "pending") {
        current_pagination.llm_calls.push(event);
      }
    } else if (
      (eventType === "pagination-detection" ||
        eventType === "parameter-detection") &&
      current_pagination &&
      event.status === "success"
    ) {
      // Handle direct pagination-detection success events from new Analyzer
      current_pagination.status = event.status;
      current_pagination.strategy = event.strategy;
      current_pagination.potential_pagination_parameters =
        event.parameters || event.potential_pagination_parameters;
      // Handle new unified parameter detection fields
      if (event.request) {
        current_pagination.request = event.request;
      }
      if (event.pagination_keys) {
        current_pagination.pagination_keys = event.pagination_keys;
      }
      if (event.dynamic_parameter_keys) {
        current_pagination.dynamic_parameter_keys =
          event.dynamic_parameter_keys;
      }
      if (event.apply_parameters_code) {
        current_pagination.apply_parameters_code = event.apply_parameters_code;
      }
      pagination_detections.push(current_pagination);
      current_pagination = null;
    } else if (
      (eventType === "code-generation" ||
        eventType === "structured-extraction") &&
      action === "llm-completion" &&
      event.status !== "pending"
    ) {
      if (!current_code_gen) {
        current_code_gen = { status: "pending" };
      }
      current_code_gen.llm_completion = event;
    } else if (
      eventType === "code-generation" ||
      eventType === "structured-extraction"
    ) {
      // Handle direct code-generation events from individual methods
      const status = event.status || "";

      if (status === "pending") {
        // Create or update current code generation with input parameters
        if (!current_code_gen) {
          current_code_gen = { status: "pending" };
        }
        // Capture input parameters
        if (event.response_length !== undefined) {
          current_code_gen.response_length = event.response_length;
        }
        if (event.preprocessor) {
          current_code_gen.preprocessor = event.preprocessor;
        }
      } else if (status === "success" || status === "failed") {
        // Ensure we have a code generation to update
        if (!current_code_gen) {
          current_code_gen = { status: "pending" };
        }
        current_code_gen.status = status;

        // Capture output data
        if (event.code) {
          current_code_gen.code = event.code;
        }
        if (event.default_limit !== undefined) {
          current_code_gen.default_limit = event.default_limit;
        }
        if (event.default_entity_count !== undefined) {
          current_code_gen.default_entity_count = event.default_entity_count;
        }
        if (event.reason) {
          current_code_gen.reason = event.reason;
        }

        // Only add to final list if we have meaningful content
        if (current_code_gen.code || current_code_gen.reason) {
          code_generations.push(current_code_gen);
        }
        current_code_gen = null;
      }
    }
  }

  // Handle any unfinished items
  if (current_pagination) {
    pagination_detections.push(current_pagination);
  }
  if (current_code_gen) {
    code_generations.push(current_code_gen);
  }

  // Sort analysis steps by step count
  analysis_steps.sort((a, b) => a.step_count - b.step_count);

  // Calculate summary statistics
  let total_cost = 0;
  let total_input_tokens = 0;
  let total_output_tokens = 0;

  // Count from all LLM calls
  for (const step of analysis_steps) {
    for (const sub_event of step.sub_events) {
      total_cost += sub_event.cost || 0;
      total_input_tokens += sub_event.input_tokens || 0;
      total_output_tokens += sub_event.output_tokens || 0;
    }
  }

  for (const pagination of pagination_detections) {
    for (const llm_call of pagination.llm_calls) {
      total_cost += llm_call.cost || 0;
      total_input_tokens += llm_call.input_tokens || 0;
      total_output_tokens += llm_call.output_tokens || 0;
    }
  }

  for (const code_gen of code_generations) {
    if (code_gen.llm_completion) {
      total_cost += code_gen.llm_completion.cost || 0;
      total_input_tokens += code_gen.llm_completion.input_tokens || 0;
      total_output_tokens += code_gen.llm_completion.output_tokens || 0;
    }
  }

  // Calculate duration
  let analysis_duration = "Unknown";
  if (
    analysis_begin &&
    analysis_end &&
    analysis_begin.timestamp &&
    analysis_end.timestamp
  ) {
    try {
      const startTime = parseISO(
        analysis_begin.timestamp.replace("Z", "+00:00"),
      );
      const endTime = parseISO(analysis_end.timestamp.replace("Z", "+00:00"));
      const duration = differenceInSeconds(endTime, startTime);
      analysis_duration = `${duration.toFixed(1)}s`;
    } catch {
      analysis_duration = "Unknown";
    }
  }

  // Find final result
  let final_result: { api_url: string } | undefined;
  if (
    analysis_end?.status === "success" &&
    typeof analysis_end.relevant_api_call === "string"
  ) {
    final_result = { api_url: analysis_end.relevant_api_call };
  }

  return {
    url,
    query,
    analysis_begin,
    analysis_end,
    analysis_steps,
    pagination_detections,
    code_generations,
    total_cost,
    total_input_tokens,
    total_output_tokens,
    analysis_duration,
    final_result,
  };
}
