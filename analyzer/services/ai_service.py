"""
AI Service module for the CodeMap Analyzer.

Integrates with OpenAI's API to generate file summaries, module summaries,
project-level documentation, architecture explanations, workflow descriptions,
use case diagrams (Mermaid), and user manuals.

Features:
- Token-aware content chunking for large files
- Exponential backoff retry for API failures
- Configurable model and token limits
"""
import logging
import re

from django.conf import settings
from openai import OpenAI, AzureOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import prompt_templates as prompts

logger = logging.getLogger('analyzer')

# Approximate characters-per-token ratio for estimation
CHARS_PER_TOKEN = 4


class AIService:
    """
    High-level service for AI-powered code analysis.

    Uses OpenAI chat completions to summarize files, modules,
    and generate project-level documentation outputs.
    """

    def __init__(self):
        """Initialize the AI service with OpenAI client (Azure or standard)."""
        if settings.AZURE_ENDPOINT:
            self.client = AzureOpenAI(
                api_key=settings.OPENAI_API_KEY,
                azure_endpoint=settings.AZURE_ENDPOINT,
                azure_deployment=settings.AZURE_DEPLOYMENT,
                api_version=settings.AZURE_API_VERSION
            )
        else:
            self.client = OpenAI(
                api_key=settings.OPENAI_API_KEY
            )
            
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        # Reserve tokens for the prompt template + response
        self.max_content_tokens = self.max_tokens * 3  # Content window estimation

    # ──────────────────────────────────────────
    # Core API Call (with retry)
    # ──────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"AI API call failed, retrying (attempt {retry_state.attempt_number})..."
        ),
    )
    def _call_api(self, prompt: str, max_response_tokens: int | None = None) -> str:
        """
        Make a chat completion API call with retry logic.

        Args:
            prompt: The full prompt text.
            max_response_tokens: Max tokens for the response.

        Returns:
            The AI-generated response text.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert software architect and code analyst. "
                        "You analyze codebases across all programming languages, "
                        "including legacy languages like Fortran, COBOL, and Pascal, "
                        "as well as modern and niche languages. "
                        "Provide clear, concise, and technically accurate analysis."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_response_tokens or self.max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    # ──────────────────────────────────────────
    # Token / Chunking Utilities
    # ──────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string."""
        return len(text) // CHARS_PER_TOKEN

    def _chunk_content(self, content: str, max_chars: int | None = None) -> list[str]:
        """
        Split content into chunks that fit within token limits.

        Splits on line boundaries to avoid breaking code structures.

        Args:
            content: The full text content to chunk.
            max_chars: Maximum characters per chunk.

        Returns:
            List of content chunks.
        """
        if max_chars is None:
            max_chars = self.max_content_tokens * CHARS_PER_TOKEN

        if len(content) <= max_chars:
            return [content]

        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > max_chars and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    # ──────────────────────────────────────────
    # File Summarization
    # ──────────────────────────────────────────

    def summarize_file(self, file_path: str, content: str, language: str) -> str:
        """
        Generate an AI summary for a single source file.

        Handles large files by chunking and merging summaries.

        Args:
            file_path: Relative path of the file.
            content: Full file content.
            language: Detected programming language.

        Returns:
            AI-generated summary string.
        """
        language_code = language.lower().split()[0] if language else ''

        chunks = self._chunk_content(content)

        if len(chunks) == 1:
            # File fits in a single prompt
            prompt = prompts.FILE_SUMMARY_PROMPT.format(
                file_path=file_path,
                language=language,
                language_code=language_code,
                content=content,
            )
            return self._call_api(prompt)
        else:
            # Large file — summarize each chunk, then merge
            logger.info(f"File {file_path} split into {len(chunks)} chunks")
            chunk_summaries = []

            for i, chunk in enumerate(chunks, 1):
                prompt = prompts.FILE_CHUNK_SUMMARY_PROMPT.format(
                    file_path=file_path,
                    language=language,
                    language_code=language_code,
                    content=chunk,
                    chunk_number=i,
                    total_chunks=len(chunks),
                )
                summary = self._call_api(prompt)
                chunk_summaries.append(f"**Part {i}:** {summary}")

            # Merge chunk summaries
            merge_prompt = prompts.FILE_CHUNKS_MERGE_PROMPT.format(
                file_path=file_path,
                language=language,
                chunk_summaries='\n\n'.join(chunk_summaries),
            )
            return self._call_api(merge_prompt)

    # ──────────────────────────────────────────
    # Module Summarization
    # ──────────────────────────────────────────

    def summarize_module(self, module_path: str, file_summaries: list[dict]) -> str:
        """
        Generate a summary for a module (directory) based on its file summaries.

        Args:
            module_path: Relative path of the module.
            file_summaries: List of dicts with 'file_path' and 'summary' keys.

        Returns:
            AI-generated module summary string.
        """
        summaries_text = '\n\n'.join(
            f"**`{fs['file_path']}`:** {fs['summary']}"
            for fs in file_summaries
        )

        # If the combined summaries are too long, truncate them
        max_summaries_chars = self.max_content_tokens * CHARS_PER_TOKEN
        if len(summaries_text) > max_summaries_chars:
            summaries_text = summaries_text[:max_summaries_chars] + "\n\n... (truncated)"

        prompt = prompts.MODULE_SUMMARY_PROMPT.format(
            module_path=module_path,
            file_count=len(file_summaries),
            file_summaries=summaries_text,
        )
        return self._call_api(prompt)

    # ──────────────────────────────────────────
    # Project-Level Outputs
    # ──────────────────────────────────────────

    def generate_project_overview(self, project_name: str, module_summaries: str) -> str:
        """
        Generate a comprehensive project overview.

        Args:
            project_name: Name of the project.
            module_summaries: Combined text of all module summaries.

        Returns:
            Markdown-formatted project overview.
        """
        prompt = prompts.PROJECT_OVERVIEW_PROMPT.format(
            project_name=project_name,
            module_summaries=self._truncate(module_summaries),
        )
        return self._call_api(prompt)

    def generate_architecture(self, project_name: str, module_summaries: str) -> str:
        """
        Generate an architecture explanation.

        Args:
            project_name: Name of the project.
            module_summaries: Combined text of all module summaries.

        Returns:
            Markdown-formatted architecture explanation.
        """
        prompt = prompts.ARCHITECTURE_PROMPT.format(
            project_name=project_name,
            module_summaries=self._truncate(module_summaries),
        )
        return self._call_api(prompt)

    def generate_workflow(self, project_name: str, module_summaries: str) -> str:
        """
        Generate a workflow explanation.

        Args:
            project_name: Name of the project.
            module_summaries: Combined text of all module summaries.

        Returns:
            Markdown-formatted workflow description.
        """
        prompt = prompts.WORKFLOW_PROMPT.format(
            project_name=project_name,
            module_summaries=self._truncate(module_summaries),
        )
        return self._call_api(prompt)

    def generate_diagram(self, output_type: str, project_name: str, context: str, current_code: str = None, error_message: str = None) -> str:
        """
        Generate a Mermaid diagram of a specific type.
        Can also fix existing broken code if error_message is provided.

        Args:
            output_type: The type of diagram (e.g., 'class_diagram', 'er_diagram').
            project_name: Name of the project.
            context: Contextual information (overview, architecture, or summaries).
            current_code: Optional previous broken code to fix.
            error_message: Optional error message from a failed render attempt.

        Returns:
            Mermaid diagram code string.
        """
        # Map output_type to the corresponding prompt template
        prompt_name = f"{output_type.upper()}_PROMPT"
        # Handle aliases like project_structure -> project_structure_diagram
        if not hasattr(prompts, prompt_name) and hasattr(prompts, f"{prompt_name}_DIAGRAM"):
            prompt_name = f"{prompt_name}_DIAGRAM"
            
        prompt_template = getattr(prompts, prompt_name, None)
        
        if not prompt_template:
            # Fallback to a generic flowchart if type not found
            logger.warning(f"No prompt template found for {output_type}, falling back to workflow flowchart.")
            prompt_template = prompts.WORKFLOW_FLOWCHART_PROMPT

        main_prompt = prompt_template.format(
            project_name=project_name,
            context=self._truncate(context),
        )
        
        if current_code and error_message:
            fix_instructions = f"\n\n### CRITICAL: FIX PREVIOUS SYNTAX ERROR\n"
            fix_instructions += f"The previous attempt failed to render due to a Mermaid syntax error.\n"
            fix_instructions += f"**Error Message:** {error_message}\n"
            fix_instructions += f"**Broken Code:**\n```mermaid\n{current_code}\n```\n\n"
            fix_instructions += f"**Instructions to Fix:**\n"
            fix_instructions += f"1. Analyze the error message (e.g., unexpected token, missing newline).\n"
            fix_instructions += f"2. **CRITICAL:** Ensure EVERY relationship is on its own line. Do NOT clump nodes together (e.g., fix `NodeA nodeB` to `NodeA` and `NodeB` on separate lines).\n"
            fix_instructions += f"3. Avoid putting too many nodes or connections on a single line.\n"
            fix_instructions += f"4. Check for unclosed brackets [] or parentheses ().\n"
            fix_instructions += f"5. Provide ONLY the FULL corrected Mermaid code for a `{output_type.replace('_diagram', '')}` diagram.\n"
            fix_instructions += f"6. **NO CLUMPING:** Ensure there is either a newline or a clear space between all keywords and node names (e.g., `Google Fonts A2` instead of `Google FontsA2`)."
            main_prompt += fix_instructions

        result = self._call_api(main_prompt)

        # Clean up: remove markdown code fences, and any %%{init ...}%% blocks
        result = re.sub(r'^```(?:mermaid)?\s*\n?', '', result, flags=re.MULTILINE)
        result = re.sub(r'\n?```\s*$', '', result, flags=re.MULTILINE)
        result = re.sub(r'%%\{init[^\}]*\}%%\n?', '', result)
        
        return result.strip()

    def generate_user_manual(
        self, project_name: str, overview: str, architecture: str, workflow: str
    ) -> str:
        """
        Generate a comprehensive user manual.

        Args:
            project_name: Name of the project.
            overview: The project overview text.
            architecture: The architecture explanation text.
            workflow: The workflow explanation text.

        Returns:
            Markdown-formatted user manual.
        """
        prompt = prompts.USER_MANUAL_PROMPT.format(
            project_name=project_name,
            overview=self._truncate(overview),
            architecture=self._truncate(architecture),
            workflow=self._truncate(workflow),
        )
        return self._call_api(prompt)

    def _truncate(self, text: str) -> str:
        """Truncate text to fit within token limits."""
        max_chars = self.max_content_tokens * CHARS_PER_TOKEN
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n... (truncated for token limits)"
        return text
