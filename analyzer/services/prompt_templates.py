"""
Prompt templates for the AI-powered analysis pipeline.

All prompts are designed to be language-agnostic, working with any
programming language including Fortran, Lua, COBOL, and other
legacy or niche languages.
"""

# ──────────────────────────────────────────────
# File-Level Summary
# ──────────────────────────────────────────────
FILE_SUMMARY_PROMPT = """You are an expert code analyst. Analyze the following source file and provide a concise summary.

**File:** `{file_path}`
**Language:** {language}

**Instructions:**
1. Describe the purpose and responsibility of this file.
2. List the key components (classes, functions, endpoints, configurations).
3. Note any important design patterns, algorithms, or external dependencies.
4. Note any imports or integrations with other parts of the codebase.
5. Keep the summary between 3–8 sentences. Be precise and technical.

**Source Code:**
```{language_code}
{content}
```

**Summary:**"""

# ──────────────────────────────────────────────
# Chunked File Summary (for large files)
# ──────────────────────────────────────────────
FILE_CHUNK_SUMMARY_PROMPT = """You are an expert code analyst. This is part {chunk_number} of {total_chunks} of a large source file.

**File:** `{file_path}`
**Language:** {language}

**Instructions:**
1. Summarize what this portion of the file contains.
2. List key classes, functions, or configurations defined here.
3. Keep it concise (2–5 sentences).

**Source Code (Part {chunk_number}/{total_chunks}):**
```{language_code}
{content}
```

**Summary of this section:**"""

FILE_CHUNKS_MERGE_PROMPT = """You are an expert code analyst. Below are summaries of different parts of the same file.

**File:** `{file_path}`
**Language:** {language}

**Part Summaries:**
{chunk_summaries}

**Instructions:**
Combine these into a single coherent summary of the entire file.
Describe its overall purpose, key components, and design patterns.
Keep it between 3–8 sentences.

**Combined Summary:**"""

# ──────────────────────────────────────────────
# Module/Directory-Level Summary
# ──────────────────────────────────────────────
MODULE_SUMMARY_PROMPT = """You are an expert software architect. Analyze the following module (directory) based on its file summaries.

**Module Path:** `{module_path}`
**Number of Files:** {file_count}

**File Summaries:**
{file_summaries}

**Instructions:**
1. Describe the overall purpose and responsibility of this module/directory.
2. Explain how the files work together as a cohesive unit.
3. Identify the module's role in the larger application (e.g., data layer, API, utilities).
4. Note any patterns or architectural significance.
5. Keep the summary between 3–8 sentences.

**Module Summary:**"""

# ──────────────────────────────────────────────
# Project Overview
# ──────────────────────────────────────────────
PROJECT_OVERVIEW_PROMPT = """You are an expert software architect. Based on the module summaries below, generate a comprehensive project overview.

**Project Name:** {project_name}

**Module Summaries:**
{module_summaries}

**Instructions:**
Generate a professional project overview that includes:
1. **Project Description** — What the project does, its main purpose and value proposition.
2. **Technology Stack** — Languages, frameworks, libraries, and tools used.
3. **Key Features** — Main functionalities and capabilities.
4. **Project Structure** — High-level organization and module responsibilities.
5. **Dependencies & Integrations** — External services, APIs, or systems it connects to.

Format the output as clean Markdown. Be thorough but concise.

**Project Overview:**"""

# ──────────────────────────────────────────────
# Architecture Explanation
# ──────────────────────────────────────────────
ARCHITECTURE_PROMPT = """You are an expert software architect. Based on the module summaries below, explain the project's architecture.

**Project Name:** {project_name}

**Module Summaries:**
{module_summaries}

**Instructions:**
Generate a detailed architecture explanation that includes:
1. **Architecture Pattern** — Identify the overall pattern (MVC, microservices, monolith, layered, event-driven, etc.).
2. **Component Overview** — Describe each major component/module and its role.
3. **Data Flow** — How data flows through the system (inputs → processing → outputs).
4. **Communication** — How components communicate (REST APIs, message queues, shared state, etc.).
5. **Security & Configuration** — Authentication, authorization, environment configuration, secrets management.
6. **Scalability Considerations** — How the system can scale, potential bottlenecks.

Format the output as clean Markdown with sections and bullet points. Be technical and precise.

**Architecture Explanation:**"""

# ──────────────────────────────────────────────
# Workflow Explanation
# ──────────────────────────────────────────────
WORKFLOW_PROMPT = """You are an expert software architect. Based on the module summaries below, explain the system's workflows.

**Project Name:** {project_name}

**Module Summaries:**
{module_summaries}

**Instructions:**
Generate a detailed workflow explanation covering:
1. **Primary User Flows** — Step-by-step description of how users interact with the system.
2. **Backend Processing Flows** — Internal processes, background jobs, data transformations.
3. **Data Lifecycle** — How data is created, stored, processed, and consumed.
4. **Error Handling Flow** — How errors propagate and are handled.
5. **Integration Flows** — Interactions with external systems or APIs.

Present each workflow as a numbered step-by-step sequence. Be specific about which components handle each step.

Format the output as clean Markdown.

**Workflow Explanation:**"""

# ──────────────────────────────────────────────
# Use Case Diagram (Mermaid)
# ──────────────────────────────────────────────
USECASE_DIAGRAM_PROMPT = """You are an expert software architect and UML designer. Based on the project overview below, generate a use case diagram in Mermaid format.

**Project Name:** {project_name}

**Project Overview:**
{overview}

**Instructions:**
1. Identify all actors (users, admins, external systems).
2. Identify all major use cases (features/actions).
3. Generate valid Mermaid syntax for a use case diagram.
4. Group related use cases using packages/rectangles.
5. Show relationships between actors and use cases.

**Important:** Output ONLY the Mermaid diagram code, starting with the diagram type declaration. Do not wrap it in markdown code fences. Use valid Mermaid syntax that renders correctly.

Example format:
graph LR
    subgraph System
        UC1[Upload Project]
        UC2[View Results]
    end
    User -->|uses| UC1
    User -->|uses| UC2

**Mermaid Use Case Diagram:**"""

# ──────────────────────────────────────────────
# User Manual
# ──────────────────────────────────────────────
USER_MANUAL_PROMPT = """You are a technical writer. Based on the project information below, generate a user manual.

**Project Name:** {project_name}

**Project Overview:**
{overview}

**Architecture:**
{architecture}

**Workflow:**
{workflow}

**Instructions:**
Generate a comprehensive user manual that includes:
1. **Introduction** — Brief description of what the system does and who it's for.
2. **Getting Started** — Prerequisites, installation, first-time setup.
3. **Features Guide** — Detailed section for each feature:
   - What it does
   - How to use it (step-by-step)
   - Expected inputs and outputs
4. **Navigation Guide** — How to navigate through the application.
5. **Troubleshooting** — Common issues and how to resolve them.
6. **FAQ** — Frequently asked questions.

Format the output as clean Markdown with proper headings, numbered lists, and bullet points.
Make it user-friendly and accessible to non-technical users where possible.

**User Manual:**"""
