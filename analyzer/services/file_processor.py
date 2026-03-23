"""
File processing utilities for the CodeMap Analyzer.

Handles ZIP extraction, Git repository cloning, directory traversal,
and file filtering to identify relevant source code files.
"""
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

logger = logging.getLogger('analyzer')

# ──────────────────────────────────────────────
# Directories to ignore during traversal
# ──────────────────────────────────────────────
IGNORE_DIRS = {
    # Version control
    '.git', '.svn', '.hg',
    # Package managers / dependencies
    'node_modules', 'bower_components', 'vendor', 'packages',
    # Python
    '__pycache__', '.venv', 'venv', 'env', '.env', '.tox', '.nox',
    '.mypy_cache', '.pytest_cache', '.ruff_cache', 'site-packages',
    '.eggs', '*.egg-info',
    # Build outputs
    'build', 'dist', 'out', 'target', 'bin', 'obj',
    # IDE / editor
    '.idea', '.vscode', '.vs', '.eclipse',
    # OS files
    '.DS_Store', 'Thumbs.db',
    # Misc
    'coverage', 'htmlcov', '.coverage', '__pypackages__',
    '.next', '.nuxt', '.cache', '.parcel-cache',
    'staticfiles', 'collected_static',
}

# ──────────────────────────────────────────────
# File extensions considered relevant
# ──────────────────────────────────────────────
RELEVANT_EXTENSIONS = {
    # Python
    '.py', '.pyw', '.pyi',
    # JavaScript / TypeScript
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    # Web
    '.html', '.htm', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    # Java / JVM
    '.java', '.kt', '.kts', '.scala', '.groovy', '.gradle',
    # C / C++
    '.c', '.h', '.cpp', '.cxx', '.cc', '.hpp', '.hxx',
    # C# / .NET
    '.cs', '.fs', '.vb',
    # Go
    '.go',
    # Rust
    '.rs',
    # Ruby
    '.rb', '.erb', '.rake',
    # PHP
    '.php',
    # Swift / Objective-C
    '.swift', '.m', '.mm',
    # Fortran (all common variants)
    '.f', '.f90', '.f95', '.f03', '.f08', '.for', '.fpp', '.ftn',
    # Lua / Luna
    '.lua',
    # Shell
    '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1',
    # Data / Config
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.xml', '.xsl', '.xsd',
    # Markup / Docs
    '.md', '.rst', '.txt', '.adoc',
    # SQL
    '.sql',
    # R
    '.r', '.R', '.rmd',
    # Perl
    '.pl', '.pm',
    # Elixir / Erlang
    '.ex', '.exs', '.erl', '.hrl',
    # Haskell
    '.hs', '.lhs',
    # Clojure
    '.clj', '.cljs', '.cljc', '.edn',
    # Dart
    '.dart',
    # Zig
    '.zig',
    # Nim
    '.nim',
    # Julia
    '.jl',
    # Dockerfile / Makefile (no extension but handled via name)
    # Terraform
    '.tf', '.tfvars',
    # Protobuf
    '.proto',
    # GraphQL
    '.graphql', '.gql',
}

# Special filenames to include (no extension-based detection)
RELEVANT_FILENAMES = {
    'Dockerfile', 'Makefile', 'CMakeLists.txt', 'Rakefile',
    'Gemfile', 'Vagrantfile', 'Procfile', 'Jenkinsfile',
    'docker-compose.yml', 'docker-compose.yaml',
    '.gitignore', '.dockerignore', '.editorconfig',
    'requirements.txt', 'setup.py', 'setup.cfg', 'pyproject.toml',
    'package.json', 'tsconfig.json', 'webpack.config.js',
    'Cargo.toml', 'go.mod', 'go.sum',
    'pom.xml', 'build.gradle', 'settings.gradle',
}


def extract_zip(zip_path: str, dest_dir: str) -> str:
    """
    Extract a ZIP archive to the destination directory.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory to extract into.

    Returns:
        Path to the top-level directory of the extracted contents.

    Raises:
        zipfile.BadZipFile: If the file is not a valid ZIP archive.
        ValueError: If the ZIP contains unsafe path traversal entries.
    """
    logger.info(f"Extracting ZIP: {zip_path} → {dest_dir}")

    if not zipfile.is_zipfile(zip_path):
        raise zipfile.BadZipFile(f"Not a valid ZIP file: {zip_path}")

    os.makedirs(dest_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Security check: prevent path traversal attacks
        for member in zf.namelist():
            member_path = os.path.realpath(os.path.join(dest_dir, member))
            if not member_path.startswith(os.path.realpath(dest_dir)):
                raise ValueError(f"Unsafe path in ZIP archive: {member}")
        zf.extractall(dest_dir)

    # If the ZIP contains a single top-level directory, return that
    entries = os.listdir(dest_dir)
    if len(entries) == 1 and os.path.isdir(os.path.join(dest_dir, entries[0])):
        return os.path.join(dest_dir, entries[0])
    return dest_dir


def clone_repo(repo_url: str, dest_dir: str) -> str:
    """
    Clone a Git repository (shallow clone) to the destination directory.

    Args:
        repo_url: URL of the Git repository.
        dest_dir: Directory to clone into.

    Returns:
        Path to the cloned repository.

    Raises:
        RuntimeError: If the git clone command fails.
    """
    logger.info(f"Cloning repository: {repo_url} → {dest_dir}")

    os.makedirs(dest_dir, exist_ok=True)

    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, dest_dir],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError(
            "Git is not installed or not in PATH. "
            "Please install Git to use repository cloning."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Git clone timed out after 5 minutes.")

    return dest_dir


def get_relevant_files(root_dir: str, max_file_size_kb: int = 512) -> list[dict]:
    """
    Recursively traverse a directory and return relevant source files.

    Filters by extension whitelist, ignores blacklisted directories,
    and skips files exceeding the size limit.

    Args:
        root_dir: Root directory to traverse.
        max_file_size_kb: Maximum individual file size in KB.

    Returns:
        List of dicts with keys: 'path' (relative), 'abs_path', 'language', 'size'.
    """
    logger.info(f"Scanning directory: {root_dir}")
    relevant_files = []
    root_path = Path(root_dir)
    max_size_bytes = max_file_size_kb * 1024

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out ignored directories (modifies dirnames in-place)
        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIRS and not d.startswith('.')
        ]

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_dir)

            # Check file size
            try:
                file_size = os.path.getsize(filepath)
            except OSError:
                continue

            if file_size > max_size_bytes or file_size == 0:
                continue

            # Check if the file is relevant
            ext = Path(filename).suffix.lower()
            if ext in RELEVANT_EXTENSIONS or filename in RELEVANT_FILENAMES:
                language = _detect_language(ext, filename)
                relevant_files.append({
                    'path': rel_path.replace('\\', '/'),  # Normalize to forward slashes
                    'abs_path': filepath,
                    'language': language,
                    'size': file_size,
                })

    logger.info(f"Found {len(relevant_files)} relevant files in {root_dir}")
    return relevant_files


def read_file_content(filepath: str, max_size_kb: int = 512) -> str | None:
    """
    Read the text content of a file.

    Returns None if the file is binary or too large.

    Args:
        filepath: Absolute path to the file.
        max_size_kb: Maximum file size in KB.

    Returns:
        File content as string, or None if unreadable.
    """
    try:
        file_size = os.path.getsize(filepath)
        if file_size > max_size_kb * 1024:
            return None

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Could not read file {filepath}: {e}")
        return None


def cleanup_project_dir(project_dir: str) -> None:
    """
    Remove the extracted/cloned project directory.

    Args:
        project_dir: Path to the project directory to remove.
    """
    try:
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir, ignore_errors=True)
            logger.info(f"Cleaned up project directory: {project_dir}")
    except Exception as e:
        logger.warning(f"Failed to clean up {project_dir}: {e}")


def _detect_language(ext: str, filename: str) -> str:
    """
    Detect the programming language based on file extension or name.

    Args:
        ext: File extension (lowercase, with dot).
        filename: Full filename.

    Returns:
        Human-readable language name.
    """
    language_map = {
        '.py': 'Python', '.pyw': 'Python', '.pyi': 'Python',
        '.js': 'JavaScript', '.jsx': 'JavaScript (JSX)',
        '.ts': 'TypeScript', '.tsx': 'TypeScript (TSX)',
        '.mjs': 'JavaScript (ESM)', '.cjs': 'JavaScript (CJS)',
        '.html': 'HTML', '.htm': 'HTML',
        '.css': 'CSS', '.scss': 'SCSS', '.sass': 'Sass', '.less': 'Less',
        '.vue': 'Vue', '.svelte': 'Svelte',
        '.java': 'Java', '.kt': 'Kotlin', '.kts': 'Kotlin Script',
        '.scala': 'Scala', '.groovy': 'Groovy', '.gradle': 'Gradle',
        '.c': 'C', '.h': 'C/C++ Header',
        '.cpp': 'C++', '.cxx': 'C++', '.cc': 'C++',
        '.hpp': 'C++ Header', '.hxx': 'C++ Header',
        '.cs': 'C#', '.fs': 'F#', '.vb': 'Visual Basic',
        '.go': 'Go', '.rs': 'Rust',
        '.rb': 'Ruby', '.erb': 'ERB', '.rake': 'Rake',
        '.php': 'PHP',
        '.swift': 'Swift', '.m': 'Objective-C', '.mm': 'Objective-C++',
        '.f': 'Fortran', '.f90': 'Fortran 90', '.f95': 'Fortran 95',
        '.f03': 'Fortran 2003', '.f08': 'Fortran 2008',
        '.for': 'Fortran', '.fpp': 'Fortran', '.ftn': 'Fortran',
        '.lua': 'Lua',
        '.sh': 'Shell', '.bash': 'Bash', '.zsh': 'Zsh',
        '.fish': 'Fish', '.bat': 'Batch', '.cmd': 'Batch', '.ps1': 'PowerShell',
        '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML',
        '.toml': 'TOML', '.ini': 'INI', '.cfg': 'Config',
        '.xml': 'XML', '.xsl': 'XSLT', '.xsd': 'XSD',
        '.md': 'Markdown', '.rst': 'reStructuredText',
        '.txt': 'Text', '.adoc': 'AsciiDoc',
        '.sql': 'SQL',
        '.r': 'R', '.R': 'R', '.rmd': 'R Markdown',
        '.pl': 'Perl', '.pm': 'Perl Module',
        '.ex': 'Elixir', '.exs': 'Elixir Script',
        '.erl': 'Erlang', '.hrl': 'Erlang Header',
        '.hs': 'Haskell', '.lhs': 'Literate Haskell',
        '.clj': 'Clojure', '.cljs': 'ClojureScript',
        '.cljc': 'Clojure (Common)', '.edn': 'EDN',
        '.dart': 'Dart', '.zig': 'Zig', '.nim': 'Nim', '.jl': 'Julia',
        '.tf': 'Terraform', '.tfvars': 'Terraform Variables',
        '.proto': 'Protocol Buffers',
        '.graphql': 'GraphQL', '.gql': 'GraphQL',
        '.conf': 'Config',
    }

    # Check by filename first
    filename_map = {
        'Dockerfile': 'Docker', 'Makefile': 'Makefile',
        'CMakeLists.txt': 'CMake', 'Rakefile': 'Ruby',
        'Gemfile': 'Ruby', 'Vagrantfile': 'Ruby',
        'Procfile': 'Procfile', 'Jenkinsfile': 'Groovy',
    }

    if filename in filename_map:
        return filename_map[filename]

    return language_map.get(ext, 'Unknown')
