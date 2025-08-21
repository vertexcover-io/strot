# Strot UI Architecture

## Overview

The Strot UI (`ui/`) is a Next.js 15 React application that provides a modern dashboard interface for managing analysis jobs and labels. It features real-time job monitoring, comprehensive log visualization, and sample data preview capabilities with a responsive design built on Tailwind CSS.

## Technology Stack

### Core Framework

- **Next.js 15**: React framework with App Router and Server Components
- **React 19**: Latest React with concurrent features
- **TypeScript**: Full type safety throughout the application
- **Tailwind CSS 4**: Utility-first CSS framework for styling

### Key Dependencies

- **@tanstack/react-query**: Server state management and caching
- **Zustand**: Client-side state management
- **@radix-ui**: Accessible UI primitives (accordion, tabs, toast)
- **@heroicons/react**: Icon library
- **Lucide React**: Additional icon set
- **date-fns**: Date formatting and manipulation
- **@aws-sdk/client-s3**: S3 integration for log retrieval

## Application Architecture

### App Router Structure (`src/app/`)

```
app/
├── layout.tsx      # Root layout with fonts and metadata
├── page.tsx        # Main application page component
└── globals.css     # Global styles and Tailwind imports
```

### Component Organization (`src/components/`)

#### Layout Components (`layout/`)

- **MainLayout**: Primary layout wrapper with sidebar and content area
- **Sidebar**: Navigation sidebar with collapsible functionality
- **ContentHeader**: Contextual header with actions and title

#### View Components (`views/`)

- **JobsView**: Jobs listing with filtering, pagination, and creation form
- **LabelsView**: Labels management interface
- **FullPageJobView**: Detailed job inspection modal with logs and preview

#### Form Components (`forms/`)

- **CreateJobForm**: Job creation form with URL and label selection

#### Overlay Components (`overlays/`)

- **CreateJobOverlay**: Modal for creating new jobs
- **CreateLabelOverlay**: Modal for creating labels
- **EditLabelOverlay**: Modal for editing existing labels
- **Overlay**: Base overlay/modal component

#### Log Components (`logs/`)

- **LogViewer**: Main log visualization component with raw/rendered modes
- **AnalysisStep**: Individual analysis step visualization
- **SlideNavigation**: Navigate through analysis steps
- **PaginationDetection**: Pagination analysis visualization
- **CodeGeneration**: Code generation step display
- **LLMCall**: LLM interaction visualization

#### Common Components (`common/`)

- **CodeBlock**: Syntax-highlighted code display with copy functionality

### Library Layer (`src/lib/`)

#### API Client (`api-client.ts`)

**Centralized HTTP Client**:

- Type-safe API interactions with error handling
- Jobs management (CRUD operations with pagination)
- Labels management (CRUD operations with search)
- Request/response type safety with TypeScript interfaces

#### Configuration (`config.ts` & `env.ts`)

- Environment-specific settings management
- API base URL configuration
- Build-time and runtime configuration validation

#### AWS S3 Integration (`s3.ts`)

- Direct S3 access for log file retrieval
- Streaming log content with error handling
- Presigned URL generation for secure access

#### Report Generation (`report-generator.ts`)

- JSONL log parsing and analysis
- Analysis step reconstruction from log events
- LLM interaction tracking and cost calculation
- Visual timeline generation from log data

### Type System (`src/types/index.ts`)

#### API Type Definitions

**Job Types**:

- `JobListItem`: Job listing display data
- `GetJobResponse`: Detailed job information
- `CreateJobRequest/Response`: Job creation flow

**Label Types**:

- `LabelResponse`: Label data structure
- `LabelCreate/Update`: Label modification operations

**System Types**:

- `JobStatus`: Status enumeration (pending, ready, failed)
- `APIError`: Error response structure

## Key Features & Functionality

### Real-Time Job Monitoring

- **Auto-Refresh**: Pending jobs refresh every 15 seconds
- **Status Updates**: Visual indicators for job progress
- **Live Log Streaming**: Real-time log updates during analysis
- **Progress Indicators**: Visual feedback for long-running operations

### Advanced Log Visualization

- **Dual View Modes**: Raw JSONL and structured rendering
- **Analysis Timeline**: Step-by-step breakdown of analysis process
- **LLM Interaction Tracking**: Token usage, costs, and model responses
- **Screenshot Integration**: Visual context from analysis steps
- **Code Generation Display**: Syntax-highlighted generated extraction code

### Job Management Interface

- **Comprehensive Filtering**: By status, label, and URL search
- **Pagination**: Efficient handling of large job lists
- **Bulk Operations**: Multi-job management capabilities
- **Usage Analytics**: Track job usage frequency and patterns

### Label Management System

- **Schema Editor**: JSON schema definition for data extraction
- **Label Library**: Reusable extraction configurations
- **Validation**: Schema validation and error handling
- **Search and Filter**: Quick label discovery

### Data Preview System

- **Sample Data**: Live data extraction preview (5 items)
- **cURL Generation**: Command-line API access examples
- **Source Information**: Complete metadata display
- **JSON Formatting**: Syntax-highlighted response data

## Component Architecture Patterns

### State Management Strategy

- **React Query**: Server state, caching, and synchronization
- **useState**: Local component state
- **useRef**: DOM references and scroll position persistence
- **sessionStorage**: Cross-refresh state persistence

### Data Flow Architecture

1. **API Layer**: Centralized HTTP client with type safety
2. **Component Layer**: Presentation components with local state
3. **Hook Layer**: Custom hooks for complex state logic
4. **Service Layer**: Business logic and data transformation

### Error Handling Strategy

- **API Client**: Centralized error handling with user-friendly messages
- **Component Level**: Local error states with retry mechanisms
- **Global**: Toast notifications for system-wide messages
- **Fallback UI**: Graceful degradation for failed states

### Performance Optimizations

- **React Query Caching**: Intelligent server state caching
- **Debounced Search**: 300ms debounce for search inputs
- **Virtual Scrolling**: Efficient handling of large datasets
- **Lazy Loading**: Component-level code splitting
- **Memoization**: Prevent unnecessary re-renders

## Integration Points

### Backend API Integration

- **Jobs API**: Full CRUD operations with advanced filtering
- **Labels API**: Management and search capabilities
- **Real-time Data**: Live job status and log updates
- **Error Handling**: Comprehensive error response handling

### AWS S3 Integration

- **Direct Access**: Client-side log file retrieval
- **Streaming**: Efficient large log file handling
- **Security**: Secure credential management
- **Caching**: Intelligent log content caching

### Browser Features

- **Responsive Design**: Mobile-first responsive layouts
- **Keyboard Navigation**: Full keyboard accessibility
- **Local Storage**: Persistent user preferences
- **Progressive Enhancement**: Works with JavaScript disabled

This architecture provides a scalable, maintainable, and user-friendly interface for the Strot analysis platform, with comprehensive real-time monitoring, advanced data visualization, and intuitive management capabilities.
