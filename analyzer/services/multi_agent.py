"""
Multi-Agent Orchestrator for parallel AI processing.

Uses ThreadPoolExecutor to run multiple AI calls concurrently,
dramatically reducing analysis time for large projects.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from django.conf import settings

logger = logging.getLogger('analyzer')


class ProgressTracker:
    """Thread-safe progress tracker for multi-agent processing."""

    def __init__(self, job, base_percent: int, max_percent: int, total_items: int):
        self._lock = threading.Lock()
        self._job = job
        self._base = base_percent
        self._max = max_percent
        self._total = max(total_items, 1)
        self._completed = 0

    def increment(self, message: str = ''):
        """Mark one item as completed and update job progress."""
        with self._lock:
            self._completed += 1
            pct = self._base + int((self._completed / self._total) * (self._max - self._base))
            pct = min(pct, self._max)
            self._job.progress_percent = pct
            self._job.progress_message = message or f'Processing ({self._completed}/{self._total})...'
            self._job.save(update_fields=['progress_percent', 'progress_message'])

    @property
    def completed(self):
        with self._lock:
            return self._completed


class MultiAgentOrchestrator:
    """
    Orchestrates parallel AI processing using a thread pool.

    Phases:
    1. File summaries  — parallel batches
    2. Module summaries — parallel
    3. Project outputs  — overview/arch/workflow in parallel, then user manual + diagrams
    """

    def __init__(self, ai_service, max_workers: int = 3):
        self.ai = ai_service
        self.max_workers = max_workers
        logger.info(f"MultiAgentOrchestrator initialized with {max_workers} workers")

    def process_files_parallel(self, job, files_to_process: list, read_file_fn: Callable) -> list:
        """
        Process file summaries in parallel.

        Args:
            job: AnalysisJob instance
            files_to_process: List of file_info dicts (path, abs_path, language, size)
            read_file_fn: Function to read file content given abs_path

        Returns:
            List of file summary dicts
        """
        tracker = ProgressTracker(job, 20, 60, len(files_to_process))
        results = []
        errors = []

        def summarize_one(file_info):
            """Worker function for a single file."""
            content = read_file_fn(file_info['abs_path'])
            if not content or len(content.strip()) == 0:
                return None

            try:
                summary = self.ai.summarize_file(
                    file_path=file_info['path'],
                    content=content,
                    language=file_info['language'],
                )
                return {
                    'file_path': file_info['path'],
                    'summary': summary,
                    'language': file_info['language'],
                    'size': file_info['size'],
                }
            except Exception as e:
                logger.warning(f"Failed to summarize {file_info['path']}: {e}")
                return {
                    'file_path': file_info['path'],
                    'summary': f"[Analysis failed: {str(e)[:100]}]",
                    'language': file_info['language'],
                    'size': file_info['size'],
                }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(summarize_one, fi): fi
                for fi in files_to_process
            }

            for future in as_completed(future_to_file):
                file_info = future_to_file[future]

                # Check cancellation between completions
                job.refresh_from_db(fields=['status'])
                if job.status == 'cancelled':
                    executor.shutdown(wait=False, cancel_futures=True)
                    return results

                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        tracker.increment(
                            f'Analyzed {len(results)}/{len(files_to_process)}: {file_info["path"]}'
                        )
                except Exception as e:
                    logger.error(f"Worker error for {file_info['path']}: {e}")
                    errors.append(str(e))

        if errors:
            logger.warning(f"{len(errors)} file(s) had analysis errors")

        return results

    def process_modules_parallel(self, job, modules: dict) -> list:
        """
        Process module summaries in parallel.

        Args:
            job: AnalysisJob instance
            modules: Dict of {module_path: [file_summary_dicts]}

        Returns:
            List of module summary dicts
        """
        tracker = ProgressTracker(job, 65, 75, len(modules))
        results = []

        def summarize_module(module_path, module_files):
            try:
                summary = self.ai.summarize_module(module_path, module_files)
                return {
                    'module_path': module_path,
                    'summary': summary,
                    'file_count': len(module_files),
                }
            except Exception as e:
                logger.warning(f"Failed to summarize module {module_path}: {e}")
                return {
                    'module_path': module_path,
                    'summary': f"[Module analysis failed: {str(e)[:100]}]",
                    'file_count': len(module_files),
                }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_mod = {
                executor.submit(summarize_module, mp, mf): mp
                for mp, mf in modules.items()
            }

            for future in as_completed(future_to_mod):
                mod_path = future_to_mod[future]
                job.refresh_from_db(fields=['status'])
                if job.status == 'cancelled':
                    executor.shutdown(wait=False, cancel_futures=True)
                    return results

                try:
                    result = future.result()
                    results.append(result)
                    tracker.increment(f'Module {len(results)}/{len(modules)}: {mod_path}')
                except Exception as e:
                    logger.error(f"Worker error for module {mod_path}: {e}")

        return results

    def generate_outputs_parallel(
        self, job, project, combined_summaries: str,
        file_list: str, selected_components: list,
        existing_outputs: dict
    ) -> dict:
        """
        Generate project-level outputs in parallel where possible.

        Phase A: overview, architecture, workflow (independent — run in parallel)
        Phase B: user_manual (depends on Phase A)
        Phase C: diagrams (depend on overview + architecture — run in parallel)

        Args:
            job: AnalysisJob instance
            project: Project instance
            combined_summaries: All module summaries as text
            file_list: Newline-separated file paths
            selected_components: List of component keys to generate
            existing_outputs: Dict of already-generated outputs

        Returns:
            Dict of {output_type: content}
        """
        outputs = dict(existing_outputs)

        # ── Phase A: Independent docs (parallel) ──────────────
        phase_a_tasks = {}
        if 'overview' in selected_components and 'overview' not in outputs:
            phase_a_tasks['overview'] = lambda: self.ai.generate_project_overview(
                project.name, combined_summaries
            )
        if 'architecture' in selected_components and 'architecture' not in outputs:
            phase_a_tasks['architecture'] = lambda: self.ai.generate_architecture(
                project.name, combined_summaries
            )
        if 'workflow' in selected_components and 'workflow' not in outputs:
            phase_a_tasks['workflow'] = lambda: self.ai.generate_workflow(
                project.name, combined_summaries
            )

        if phase_a_tasks:
            job.progress_message = f'Generating docs in parallel ({len(phase_a_tasks)} agents)...'
            job.progress_percent = 78
            job.save(update_fields=['progress_message', 'progress_percent'])

            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(phase_a_tasks))) as executor:
                futures = {
                    executor.submit(fn): key
                    for key, fn in phase_a_tasks.items()
                }
                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        outputs[key] = future.result()
                        logger.info(f"Generated {key} output")
                    except Exception as e:
                        logger.error(f"Failed to generate {key}: {e}")
                        outputs[key] = f"[Generation failed: {str(e)[:200]}]"

        # ── Phase B: User manual (depends on A) ───────────────
        if 'user_manual' in selected_components and 'user_manual' not in outputs:
            job.progress_message = 'Generating user manual...'
            job.progress_percent = 88
            job.save(update_fields=['progress_message', 'progress_percent'])

            try:
                outputs['user_manual'] = self.ai.generate_user_manual(
                    project.name,
                    outputs.get('overview', ''),
                    outputs.get('architecture', ''),
                    outputs.get('workflow', ''),
                )
            except Exception as e:
                logger.error(f"Failed to generate user manual: {e}")

        # ── Phase C: Diagrams (parallel) ──────────────────────
        diagram_types = [
            'class_diagram', 'object_diagram', 'component_diagram',
            'composite_structure_diagram', 'package_diagram', 'deployment_diagram',
            'profile_diagram', 'usecase_diagram', 'activity_diagram',
            'state_diagram', 'sequence_diagram', 'communication_diagram',
            'interaction_overview_diagram', 'timing_diagram',
            'er_diagram', 'c4_context_diagram', 'workflow_flowchart',
            'mindmap', 'project_structure',
        ]

        diagrams_to_generate = [
            dt for dt in diagram_types
            if dt in selected_components and dt not in outputs
        ]

        if diagrams_to_generate:
            diagram_context = (
                f"Overview:\n{outputs.get('overview', '')}\n\n"
                f"Architecture:\n{outputs.get('architecture', '')}\n\n"
                f"Files:\n{file_list}"
            )

            tracker = ProgressTracker(job, 90, 98, len(diagrams_to_generate))

            def gen_diagram(dtype):
                return dtype, self.ai.generate_diagram(dtype, project.name, diagram_context)

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(gen_diagram, dt): dt
                    for dt in diagrams_to_generate
                }
                for future in as_completed(futures):
                    dt = futures[future]
                    try:
                        key, content = future.result()
                        outputs[key] = content
                        display_name = dt.replace('_', ' ').title()
                        tracker.increment(f'Generated {display_name}')
                    except Exception as e:
                        logger.error(f"Failed to generate diagram {dt}: {e}")

        return outputs
