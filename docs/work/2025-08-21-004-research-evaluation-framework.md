# Strot Evaluation Framework

## Overview

The evaluation framework (`eval/`) is a comprehensive testing and metrics collection system that measures the accuracy and performance of the strot analysis engine. It automates the evaluation of analysis jobs against expected outcomes and stores detailed metrics in Airtable for analysis and reporting.

## Framework Architecture

### Command Line Interface (`__main__.py`)

**Entry Point**: `python -m eval` or direct execution

- **Input Methods**: JSON/JSONL files or stdin for batch processing
- **File Validation**: Automatic detection of JSON vs JSONL format
- **Progress Tracking**: Real-time feedback with success/failure indicators
- **Error Handling**: Continues processing remaining inputs on individual failures

**CLI Framework**: Built on `cyclopts` for clean argument parsing and help generation

### Configuration Management (`settings.py`)

#### Environment Settings (`EnvSettings`)

**Environment Variables** (prefixed with `STROT_`):

- **API Integration**: Base URL for strot API communication
- **AWS S3**: Credentials and bucket for log retrieval
- **Airtable**: Personal Access Token, Base ID, and table names

#### Airtable Schema Definitions

**Analysis Steps Table Schema**:

- `job_id`: Job identifier linking to metrics
- `index`: Sequential step execution order
- `step`: Action type (fallback, close-overlay-popup, skip-to-content, load-more-content, skip-similar-content)
- `screenshot_before_step_execution`: Visual context before action
- `step_execution_outcome`: Detailed execution result

**Evaluation Metrics Table Schema**:

- `run_id`: Unique evaluation run identifier
- `initiated_at/completed_at`: Timestamp tracking
- `target_site/label`: Test case identification
- `source_expected/actual`: URL comparison fields
- `source_matching`: Boolean match indicator
- `pagination_keys_expected/actual`: Parameter detection comparison
- `pagination_keys_matching`: Boolean pagination accuracy
- `entity_count_expected/actual`: Data extraction volume comparison
- `entity_count_difference`: Percentage accuracy metric
- `analysis_steps`: Linked records to detailed step analysis
- `comment`: Manual annotation field

### Input Types (`types.py`)

#### Base Input (`_CommonInput`)

- `expected_source`: Expected API endpoint URL
- `expected_pagination_keys`: List of pagination parameter names
- `expected_entity_count`: Expected data extraction volume

#### Input Variants

- **ExistingJobInput**: Evaluates completed analysis jobs by `job_id`
- **NewJobInput**: Creates and evaluates new jobs with `site_url` and `label`

### API Client Integration (`client.py`)

#### `StrotClient` Class

**HTTP Operations**:

- `create_job()`: Initiates new analysis jobs via API
- `get_job()`: Retrieves job status and source metadata
- `fetch_data()`: Executes data extraction with pagination parameters

**S3 Integration**:

- `fetch_logs()`: Retrieves structured analysis logs from S3
- **Error Handling**: Specific handling for missing log files
- **Timeout Support**: Handles long-running data extraction requests

**Logging Integration**: Comprehensive operation tracking with structured logging

### Log Analysis (`log_parser.py`)

#### Data Structures

**LogEvent**: Individual log entry with fields for:

- Event classification (event, action, status)
- Analysis metadata (url, query, step_count)
- LLM interactions (provider, model, tokens, cost)
- Browser actions (step, target, point, context)
- Results (method, queries, data, code, strategy)

**AnalysisStep**: Aggregated step data containing:

- Step identification and status
- Request details (method, URL, queries, data)
- Sub-events collection for detailed action tracking

**ReportData**: Complete analysis session containing:

- Target URL and query
- Analysis lifecycle events (begin/end)
- Ordered collection of analysis steps

#### Log Processing (`parse_jsonl_logs`)

1. **JSONL Parsing**: Handles nested JSON message structures
2. **Event Classification**: Categorizes log entries by type and action
3. **Step Aggregation**: Groups sub-events under parent analysis steps
4. **Timeline Reconstruction**: Maintains chronological order of operations
5. **Data Validation**: Robust error handling for malformed log entries

### Core Evaluation Engine (`evaluator.py`)

#### Evaluator Class Workflow

**1. Table Management (`_ensure_tables_exist`)**

- **Dynamic Schema**: Creates Airtable tables with proper field types
- **Relationship Setup**: Links analysis steps to evaluation metrics
- **Retry Logic**: Handles API failures with second attempt
- **Validation**: Checks existing tables before creation

**2. Screenshot Processing (`_upload_base64_image`)**

- **Image Decoding**: Converts base64 screenshot data to binary
- **Temporary Files**: Safe handling with automatic cleanup
- **Airtable Upload**: Direct attachment upload via API
- **URL Extraction**: Returns accessible image URLs for records

**3. Analysis Steps Processing (`_prepare_analysis_steps`)**

- **Log Parsing**: Extracts step-by-step browser actions
- **Screenshot Mapping**: Associates images with specific actions
- **Outcome Classification**: Categorizes step results (success/failure/reason)
- **Batch Preparation**: Formats data for Airtable insertion

**4. Metrics Calculation (`_prepare_metric`)**

- **Source Comparison**: Exact URL matching between expected and actual
- **Pagination Accuracy**: Set comparison of detected parameter keys
- **Entity Count Analysis**: Volume accuracy with percentage difference
- **Data Extraction**: Live testing of source functionality
- **Comprehensive Scoring**: Boolean and numerical accuracy metrics

**5. Airtable Integration**

- **Batch Operations**: Efficient bulk record creation
- **Error Recovery**: Individual record fallback for batch failures
- **Relationship Linking**: Connects metrics to analysis step records
- **Structured Logging**: Detailed operation tracking

#### Evaluation Process (`evaluate`)

**Job Management**:

1. Creates new jobs or uses existing job IDs
2. Polls job status until completion (pending → ready/failed)
3. Handles job failures gracefully

**Data Collection**:

1. Retrieves analysis logs from S3
2. Parses structured log data into analysis steps
3. Extracts screenshots and execution context

**Accuracy Assessment**:

1. Compares discovered source URL with expected endpoint
2. Validates detected pagination parameters
3. Tests actual data extraction functionality
4. Calculates accuracy percentages

**Results Storage**:

1. Creates analysis step records with visual context
2. Stores comprehensive evaluation metrics
3. Links related records for drill-down analysis
4. Provides Airtable dashboard URL for review

## Key Features

### Automated Accuracy Testing

- **Source Discovery**: Validates API endpoint identification
- **Pagination Detection**: Measures parameter recognition accuracy
- **Data Extraction**: Tests live functionality with expected volumes
- **Visual Documentation**: Screenshots provide execution context

### Comprehensive Metrics Collection

- **Boolean Indicators**: Simple pass/fail for critical functions
- **Numerical Accuracy**: Percentage differences for volume metrics
- **Execution Timeline**: Step-by-step browser action analysis

### Scalable Batch Processing

- **Multiple Input Formats**: JSON arrays or JSONL for large datasets
- **Progress Monitoring**: Real-time feedback during evaluation
- **Error Isolation**: Individual failures don't abort batch processing
- **Flexible Input Sources**: Files or stdin for integration flexibility

### Integration Architecture

- **API Client**: Seamless integration with strot API server
- **S3 Log Retrieval**: Access to detailed analysis logging
- **Airtable Storage**: Structured metrics with visual dashboard
- **Environment Configuration**: Flexible deployment configuration

This evaluation framework enables systematic testing and continuous improvement of the strot analysis engine through automated accuracy measurement, detailed execution analysis, and comprehensive metrics collection.
