import os
import posixpath
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import uuid

from app.services.parser import ExtractedImport, ParseResult


@dataclass
class ResolvedDependency:
    """A resolved relationship between files and/or symbols."""

    source_file_path: str
    target_file_path: Optional[str]  # None if external third-party package
    source_symbol_name: Optional[str] = None
    target_symbol_name: Optional[str] = None
    dependency_type: str = "import"  # "import", "call", "inheritance"


@dataclass
class ImpactReport:
    """Analysis of what files and symbols are impacted by changes to a target."""

    target: str
    target_type: str  # "file" or "symbol"
    direct_dependents: List[str] = field(default_factory=list)
    indirect_dependents: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    impact_level: str = "low"  # "low", "medium", "high", "critical"
    summary: str = ""


class DependencyAnalyzer:
    """Resolves and analyzes cross-file and symbol dependencies in a codebase."""

    def __init__(self, file_paths: List[str]):
        # Normalized forward-slash relative file paths in repo
        self.file_paths = {f.replace("\\", "/"): f for f in file_paths}
        # Path lookup index by stem / module name
        self._build_indices()

    def _build_indices(self):
        self.exact_paths: Set[str] = set(self.file_paths.keys())
        # e.g., 'app/models/repository.py' -> 'app.models.repository'
        self.module_to_file: Dict[str, str] = {}
        for path in self.exact_paths:
            no_ext, _ = posixpath.splitext(path)
            mod_dotted = no_ext.replace("/", ".")
            self.module_to_file[mod_dotted] = path
            # Also without top-level prefix if applicable
            parts = mod_dotted.split(".")
            if len(parts) > 1:
                self.module_to_file[".".join(parts[1:])] = path

    def resolve_python_import(
        self, source_path: str, imp: ExtractedImport
    ) -> Optional[str]:
        """Resolves a Python import statement to a target file path within the repo."""
        clean_source = source_path.replace("\\", "/")

        if imp.is_relative:
            # e.g., source is 'app/api/repositories.py', from .models import ...
            source_dir = posixpath.dirname(clean_source)
            # handle relative levels
            for _ in range(max(0, imp.relative_level - 1)):
                source_dir = posixpath.dirname(source_dir)
            target_rel = posixpath.normpath(posixpath.join(source_dir, imp.module.replace(".", "/")))
            for ext in [".py", "/__init__.py"]:
                candidate = target_rel + ext if not target_rel.endswith(ext) else target_rel
                if candidate in self.exact_paths:
                    return candidate
            if target_rel in self.exact_paths:
                return target_rel
            return None

        # Absolute import e.g. "app.models.repository" or "app.models"
        mod = imp.module
        if mod in self.module_to_file:
            return self.module_to_file[mod]

        # Candidate by directory / __init__.py
        as_path = mod.replace(".", "/")
        for ext in [".py", "/__init__.py"]:
            candidate = as_path + ext
            if candidate in self.exact_paths:
                return candidate

        return None

    def resolve_js_ts_import(
        self, source_path: str, imp: ExtractedImport
    ) -> Optional[str]:
        """Resolves a JS/TS relative import to a file in the repo."""
        clean_source = source_path.replace("\\", "/")
        source_dir = posixpath.dirname(clean_source)

        if not imp.is_relative:
            # Third-party package (react, lodash, etc.)
            return None

        joined = posixpath.normpath(posixpath.join(source_dir, imp.module))
        # Try various extensions
        extensions = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]
        for ext in extensions:
            cand = joined + ext
            if cand in self.exact_paths:
                return cand

        return None

    def resolve_file_dependencies(
        self,
        source_path: str,
        parse_result: ParseResult,
        language: Optional[str] = None,
    ) -> List[ResolvedDependency]:
        """Resolves all imports, calls, and inheritances for a file into dependencies."""
        deps: List[ResolvedDependency] = []
        lang = (language or "").lower()

        # 1. Imports
        for imp in parse_result.imports:
            target_file: Optional[str] = None
            if "python" in lang:
                target_file = self.resolve_python_import(source_path, imp)
            elif any(k in lang for k in ["javascript", "typescript", "tsx", "jsx"]):
                target_file = self.resolve_js_ts_import(source_path, imp)

            if imp.symbols:
                for sym in imp.symbols:
                    deps.append(
                        ResolvedDependency(
                            source_file_path=source_path,
                            target_file_path=target_file,
                            target_symbol_name=sym,
                            dependency_type="import",
                        )
                    )
            else:
                deps.append(
                    ResolvedDependency(
                        source_file_path=source_path,
                        target_file_path=target_file,
                        target_symbol_name=imp.module.split(".")[-1],
                        dependency_type="import",
                    )
                )

        # 2. Inheritances
        for derived, base in parse_result.inheritances:
            deps.append(
                ResolvedDependency(
                    source_file_path=source_path,
                    target_file_path=None,
                    source_symbol_name=derived,
                    target_symbol_name=base,
                    dependency_type="inheritance",
                )
            )

        # 3. Calls
        for call in parse_result.calls:
            deps.append(
                ResolvedDependency(
                    source_file_path=source_path,
                    target_file_path=None,
                    source_symbol_name=call.caller_symbol,
                    target_symbol_name=call.target_name,
                    dependency_type="call",
                )
            )

        return deps


def analyze_impact(
    target: str,
    dependencies: List[Dict[str, str]],
) -> ImpactReport:
    """Computes direct and indirect dependents for a target file or symbol.

    dependencies list dict: {source_file, target_file, source_symbol, target_symbol, type}
    """
    target_clean = target.replace("\\", "/").strip()
    is_file = any(
        target_clean == dep.get("target_file") or target_clean == dep.get("source_file")
        for dep in dependencies
    )

    # Build adjacency graph: target -> dependents (who uses target)
    graph: Dict[str, Set[str]] = {}
    for dep in dependencies:
        src_file = dep.get("source_file") or ""
        tgt_file = dep.get("target_file") or ""
        src_sym = dep.get("source_symbol") or ""
        tgt_sym = dep.get("target_symbol") or ""

        # File-to-file link
        if tgt_file:
            graph.setdefault(tgt_file, set()).add(src_file)

        # Symbol link
        if tgt_sym:
            caller = src_sym or src_file
            if caller:
                graph.setdefault(tgt_sym, set()).add(caller)
                graph.setdefault(tgt_sym, set()).add(src_file)

    # Traverse graph from target
    direct = sorted(list(graph.get(target_clean, set())))

    visited = set(direct)
    queue = list(direct)
    indirect = []

    while queue:
        curr = queue.pop(0)
        for nxt in graph.get(curr, set()):
            if nxt != target_clean and nxt not in visited:
                visited.add(nxt)
                indirect.append(nxt)
                queue.append(nxt)

    affected_files = sorted(
        list(
            {item for item in visited if "/" in item or "." in item}
        )
    )

    total_impact = len(visited)
    if total_impact == 0:
        level = "low"
    elif total_impact <= 3:
        level = "medium"
    elif total_impact <= 8:
        level = "high"
    else:
        level = "critical"

    summary = (
        f"Modifying '{target_clean}' affects {len(direct)} direct component(s) "
        f"and {len(indirect)} indirect component(s) across {len(affected_files)} file(s)."
    )

    return ImpactReport(
        target=target_clean,
        target_type="file" if is_file else "symbol",
        direct_dependents=direct,
        indirect_dependents=sorted(indirect),
        affected_files=affected_files,
        impact_level=level,
        summary=summary,
    )
