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
# Diagram Suite (Mermaid)
# ──────────────────────────────────────────────

DIAGRAM_BASE_INSTRUCTIONS = """You are an expert software architect and designer. Based on the project overview and context provided, generate a technical diagram in Mermaid format.

**CRITICAL FORMATTING RULES:**
1. Output ONLY the Mermaid diagram code itself.
2. Do NOT use markdown code fences (```).
3. Do NOT include `%%{{init...}}%%` blocks.
4. **MANDATORY:** Every single relationship or node definition MUST be on a NEW LINE. 
5. **MANDATORY:** Do NOT combine multiple relationships on the same line (e.g., avoid `A -> B -> C`). Use separate lines: `A -> B` and `B -> C`.
6. Ensure syntax is strictly valid for the requested Mermaid diagram type.
"""

# UML Structural Diagrams
CLASS_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Class Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Identify major classes, interfaces, and data structures.
2. Show attributes and methods where significant.
3. Represent relationships: inheritance, composition, aggregation, and associations.
4. Use `classDiagram` syntax.
"""

OBJECT_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Object Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Represent specific instances (objects) of classes at a point in time.
2. Show attribute values to illustrate state.
3. Use `graph TD` or `classDiagram` (with instance notation) to show object relationships.
"""

COMPONENT_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Component Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Identify physical or logical components (modules, libraries, packages).
2. Show interfaces and dependencies between components.
3. Use `graph LR` with subgraphs and component icons if possible.
"""

COMPOSITE_STRUCTURE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Composite Structure Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show the internal structure of a complex class or component.
2. Focus on parts, ports, and connectors.
3. Use `graph TD` with nested subgraphs.
"""

PACKAGE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Package Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Organize system elements into packages (folders/namespaces).
2. Show dependencies between packages.
3. Use `graph TD` with subgraphs representing packages.
"""

DEPLOYMENT_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Deployment Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Map software components to hardware/infrastructure nodes (servers, databases, clients).
2. Show physical connections and protocols.
3. Use `graph TD` with subgraphs representing nodes.
"""

PROFILE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Profile Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show how UML elements are extended with stereotypes, tagged values, and constraints.
2. Use `classDiagram` to show stereotypes and their applications.
"""

# UML Behavioral Diagrams
USECASE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Use Case Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Identify actors (Users, Systems) and Use Cases (Actions).
2. Group use cases into a System boundary.
3. Show relationships (association, extend, include).
4. Use `graph LR` with actor icons.
"""

ACTIVITY_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Activity Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show the step-by-step flow of a complex operation.
2. Include start/end nodes, actions, decision diamonds, and forks/joins.
3. Use `stateDiagram-v2` or `graph TD` for flow.
"""

STATE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML State Machine Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show states (e.g., Pending, Active, Completed) and transitions.
2. Include event triggers and guard conditions.
3. Use `stateDiagram-v2` syntax.
"""

SEQUENCE_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Sequence Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show object interactions arranged in time sequence.
2. Include lifelines, messages (sync/async), and activation boxes.
3. Use `sequenceDiagram` syntax.
"""

COMMUNICATION_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Communication Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Focus on the relationships between objects.
2. Number the messages to show sequence.
3. Use `graph LR` with labeled edges.
"""

INTERACTION_OVERVIEW_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Interaction Overview Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Provide a high-level view of multiple interactions.
2. Combine elements of activity and sequence diagrams.
3. Use `graph TD` to show the flow between interaction blocks.
"""

TIMING_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** UML Timing Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show state changes of objects over a specific timeline.
2. Use `gantt` or `timeline` syntax to represent object statuses over time.
"""

# Non-UML Diagrams
ER_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** Entity-Relationship Diagram (ERD)
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Identify entities (data tables/models) and their attributes.
2. Show relationships (1:1, 1:N, M:N) with cardinality.
3. Use `erDiagram` syntax.
"""
 
PROJECT_STRUCTURE_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** Project Structure (File Tree)
**Project Name:** {project_name}
**Context:** {context}
 
**Instructions:**
1. Create a hierarchical file tree visualization of the project structure.
2. Use Mermaid `graph TD` or `mindmap` syntax.
3. Represent directories as nodes and files as children.
4. Highlight key directories like `src/`, `tests/`, `docs/`, etc.
5. Do NOT include every single file if there are many; focus on the high-level architecture and important files.
"""

C4_CONTEXT_DIAGRAM_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** C4 System Context Diagram
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Show the system as a "box" in the middle, surrounded by users and other systems it interacts with.
2. Focus on high-level scope and boundaries.
3. Use `graph TD` with specialized styling for C4 nodes.
"""

WORKFLOW_FLOWCHART_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** Workflow Flowchart
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Map a specific business or technical process.
2. Use standard symbols: rectangles (process), diamonds (decision), ovals (start/end).
3. Use `graph TD` syntax.
"""

MINDMAP_PROMPT = DIAGRAM_BASE_INSTRUCTIONS + """
**Diagram Type:** Mind Map
**Project Name:** {project_name}
**Context:** {context}

**Instructions:**
1. Start with the Project Name as the central node.
2. Branch out into major modules, features, and technical concepts.
3. Use `mindmap` syntax.
"""

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
