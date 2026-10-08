import ast
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExtractedSymbol:
    """Represents a symbol extracted from a source file."""

    name: str
    kind: str  # "class", "function", "method", "interface", "type", "variable"
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None
    children: List["ExtractedSymbol"] = field(default_factory=list)


@dataclass
class ExtractedImport:
    """Represents an import statement extracted from a source file."""

    module: str
    symbols: List[str]
    line: int
    is_relative: bool = False
    relative_level: int = 0


@dataclass
class ExtractedCall:
    """Represents a function or method invocation."""

    caller_symbol: Optional[str]
    target_name: str
    line: int


@dataclass
class ParseResult:
    """Aggregated output from parsing a single source file."""

    symbols: List[ExtractedSymbol]
    imports: List[ExtractedImport]
    calls: List[ExtractedCall]
    inheritances: List[Tuple[str, str]]  # (derived_class, base_class)


# ---------------------------------------------------------------------------
# Python AST Visitor & Parser
# ---------------------------------------------------------------------------

class PythonCodeVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.symbols: List[ExtractedSymbol] = []
        self.imports: List[ExtractedImport] = []
        self.calls: List[ExtractedCall] = []
        self.inheritances: List[Tuple[str, str]] = []
        self._current_parent: Optional[ExtractedSymbol] = None

    def _get_signature_from_lines(self, start_line: int, end_line: int) -> str:
        """Extracts the declaration header lines up to the colon."""
        if not (1 <= start_line <= len(self.lines)):
            return ""
        collected = []
        for i in range(start_line - 1, min(end_line, len(self.lines))):
            line = self.lines[i].strip()
            collected.append(line)
            if line.endswith(":"):
                break
        return " ".join(collected)

    def visit_ClassDef(self, node: ast.ClassDef):
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", node.lineno)
        docstring = ast.get_docstring(node)
        signature = self._get_signature_from_lines(line_start, line_end)

        # Track inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.inheritances.append((node.name, base.id))
            elif isinstance(base, ast.Attribute):
                self.inheritances.append((node.name, base.attr))

        class_symbol = ExtractedSymbol(
            name=node.name,
            kind="class",
            line_start=line_start,
            line_end=line_end,
            signature=signature or f"class {node.name}:",
            docstring=docstring,
            parent_name=self._current_parent.name if self._current_parent else None,
        )

        prev_parent = self._current_parent
        self._current_parent = class_symbol

        # Visit child nodes (methods, inner classes)
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_doc = ast.get_docstring(item)
                m_start = item.lineno
                m_end = getattr(item, "end_lineno", item.lineno)
                m_sig = self._get_signature_from_lines(m_start, m_end)
                method_symbol = ExtractedSymbol(
                    name=item.name,
                    kind="method",
                    line_start=m_start,
                    line_end=m_end,
                    signature=m_sig or f"def {item.name}(...):",
                    docstring=method_doc,
                    parent_name=class_symbol.name,
                )
                class_symbol.children.append(method_symbol)
                # Visit statements inside method to find function calls
                self._visit_body_calls(item.body, caller_name=f"{class_symbol.name}.{item.name}")
            else:
                self.visit(item)

        self._current_parent = prev_parent
        self.symbols.append(class_symbol)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node, is_async=True)

    def _handle_function(self, node, is_async: bool = False):
        # Top-level function
        line_start = node.lineno
        line_end = getattr(node, "end_lineno", node.lineno)
        docstring = ast.get_docstring(node)
        signature = self._get_signature_from_lines(line_start, line_end)

        prefix = "async def " if is_async else "def "
        fn_symbol = ExtractedSymbol(
            name=node.name,
            kind="function",
            line_start=line_start,
            line_end=line_end,
            signature=signature or f"{prefix}{node.name}(...):",
            docstring=docstring,
            parent_name=self._current_parent.name if self._current_parent else None,
        )
        self.symbols.append(fn_symbol)
        self._visit_body_calls(node.body, caller_name=node.name)

    def _visit_body_calls(self, body: List[ast.AST], caller_name: str):
        for stmt in body:
            for subnode in ast.walk(stmt):
                if isinstance(subnode, ast.Call):
                    target = ""
                    if isinstance(subnode.func, ast.Name):
                        target = subnode.func.id
                    elif isinstance(subnode.func, ast.Attribute):
                        target = subnode.func.attr
                    if target:
                        self.calls.append(
                            ExtractedCall(
                                caller_symbol=caller_name,
                                target_name=target,
                                line=getattr(subnode, "lineno", 0),
                            )
                        )

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                ExtractedImport(
                    module=alias.name,
                    symbols=[],
                    line=node.lineno,
                    is_relative=False,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        symbols = [alias.name for alias in node.names]
        is_rel = (node.level or 0) > 0
        self.imports.append(
            ExtractedImport(
                module=module,
                symbols=symbols,
                line=node.lineno,
                is_relative=is_rel,
                relative_level=node.level or 0,
            )
        )


def parse_python_code(content: str) -> ParseResult:
    """Parses Python source code using the standard AST library."""
    try:
        tree = ast.parse(content)
        visitor = PythonCodeVisitor(content)
        visitor.visit(tree)
        return ParseResult(
            symbols=visitor.symbols,
            imports=visitor.imports,
            calls=visitor.calls,
            inheritances=visitor.inheritances,
        )
    except SyntaxError as e:
        logger.debug("Python syntax parse warning: %s", e)
        return parse_generic_code(content, language="Python")


# ---------------------------------------------------------------------------
# JavaScript / TypeScript Parser (Regex / Pattern based)
# ---------------------------------------------------------------------------

RE_JS_IMPORT = re.compile(
    r"""import\s+(?:(?:\*\s+as\s+(\w+)|([\w$]+)|\{([^}]+)\})\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
RE_JS_REQUIRE = re.compile(
    r"""(?:const|let|var)\s+(?:\{([^}]+)\}|([\w$]+))\s*=\s*require\(['"]([^'"]+)['"]\)""",
    re.MULTILINE,
)
RE_JS_CLASS = re.compile(
    r"""(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$.]+))?""",
    re.MULTILINE,
)
RE_JS_INTERFACE = re.compile(
    r"""(?:export\s+)?interface\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$,\s]+))?""",
    re.MULTILINE,
)
RE_JS_TYPE = re.compile(
    r"""(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=""",
    re.MULTILINE,
)
RE_JS_FUNCTION = re.compile(
    r"""(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z0-9_$]+)\s*\(([^)]*)\)""",
    re.MULTILINE,
)
RE_JS_ARROW_FN = re.compile(
    r"""(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>""",
    re.MULTILINE,
)


def _find_matching_brace_end(lines: List[str], start_idx: int) -> int:
    """Finds the ending line index for a code block by balancing curly braces."""
    brace_count = 0
    found_first = False
    for i in range(start_idx, len(lines)):
        line = lines[i]
        for char in line:
            if char == "{":
                brace_count += 1
                found_first = True
            elif char == "}":
                brace_count -= 1
                if found_first and brace_count <= 0:
                    return i + 1
    return min(start_idx + 30, len(lines))


def parse_js_ts_code(content: str, language: str) -> ParseResult:
    """Parses JavaScript, TypeScript, JSX, and TSX files."""
    symbols: List[ExtractedSymbol] = []
    imports: List[ExtractedImport] = []
    calls: List[ExtractedCall] = []
    inheritances: List[Tuple[str, str]] = []

    lines = content.splitlines()

    # 1. Imports
    for match in RE_JS_IMPORT.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        star_import, default_import, named_imports, module_path = match.groups()
        sym_list = []
        if default_import:
            sym_list.append(default_import.strip())
        if star_import:
            sym_list.append(star_import.strip())
        if named_imports:
            sym_list.extend(
                [s.strip().split(" as ")[0].strip() for s in named_imports.split(",") if s.strip()]
            )

        is_rel = module_path.startswith(".")
        imports.append(
            ExtractedImport(
                module=module_path,
                symbols=sym_list,
                line=line_num,
                is_relative=is_rel,
            )
        )

    for match in RE_JS_REQUIRE.finditer(content):
        line_num = content[: match.start()].count("\n") + 1
        named, single, module_path = match.groups()
        sym_list = []
        if single:
            sym_list.append(single.strip())
        if named:
            sym_list.extend([s.strip() for s in named.split(",") if s.strip()])
        imports.append(
            ExtractedImport(
                module=module_path,
                symbols=sym_list,
                line=line_num,
                is_relative=module_path.startswith("."),
            )
        )

    # 2. Classes
    for match in RE_JS_CLASS.finditer(content):
        class_name, base_class = match.groups()
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        sig = match.group(0).strip()

        if base_class:
            inheritances.append((class_name, base_class.strip()))

        cls_sym = ExtractedSymbol(
            name=class_name,
            kind="class",
            line_start=start_line,
            line_end=end_line,
            signature=sig,
        )
        symbols.append(cls_sym)

    # 3. Interfaces (TypeScript)
    for match in RE_JS_INTERFACE.finditer(content):
        iface_name, bases = match.groups()
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        symbols.append(
            ExtractedSymbol(
                name=iface_name,
                kind="interface",
                line_start=start_line,
                line_end=end_line,
                signature=match.group(0).strip(),
            )
        )

    # 4. Type aliases
    for match in RE_JS_TYPE.finditer(content):
        tname = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        symbols.append(
            ExtractedSymbol(
                name=tname,
                kind="type",
                line_start=start_line,
                line_end=start_line,
                signature=match.group(0).strip(),
            )
        )

    # 5. Functions
    for match in RE_JS_FUNCTION.finditer(content):
        fname, args = match.groups()
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        symbols.append(
            ExtractedSymbol(
                name=fname,
                kind="function",
                line_start=start_line,
                line_end=end_line,
                signature=match.group(0).strip(),
            )
        )

    # 6. Arrow functions
    for match in RE_JS_ARROW_FN.finditer(content):
        fname = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        symbols.append(
            ExtractedSymbol(
                name=fname,
                kind="function",
                line_start=start_line,
                line_end=end_line,
                signature=match.group(0).strip(),
            )
        )

    # Deduplicate symbols by (name, line_start)
    unique_symbols = []
    seen = set()
    for s in symbols:
        key = (s.name, s.line_start)
        if key not in seen:
            seen.add(key)
            unique_symbols.append(s)

    return ParseResult(
        symbols=unique_symbols,
        imports=imports,
        calls=calls,
        inheritances=inheritances,
    )


# ---------------------------------------------------------------------------
# Generic Language Parser (Go, Rust, Java, C++, Ruby, PHP, etc.)
# ---------------------------------------------------------------------------

RE_GENERIC_FN = re.compile(
    r"""^\s*(?:pub\s+|public\s+|private\s+|protected\s+|static\s+|fn\s+|func\s+|def\s+)+([A-Za-z0-9_]+)\s*\(""",
    re.MULTILINE,
)
RE_GENERIC_CLASS = re.compile(
    r"""^\s*(?:pub\s+|public\s+)?(?:class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)""",
    re.MULTILINE,
)
RE_GENERIC_IMPORT = re.compile(
    r"""^\s*(?:import|use|#include|package)\s+([^\s;]+)""",
    re.MULTILINE,
)


def parse_generic_code(content: str, language: str) -> ParseResult:
    """Fallback parser for other programming languages using structural patterns."""
    symbols: List[ExtractedSymbol] = []
    imports: List[ExtractedImport] = []
    lines = content.splitlines()

    for match in RE_GENERIC_IMPORT.finditer(content):
        line = content[: match.start()].count("\n") + 1
        module_path = match.group(1).strip('"\'<>;')
        imports.append(
            ExtractedImport(
                module=module_path,
                symbols=[],
                line=line,
            )
        )

    for match in RE_GENERIC_CLASS.finditer(content):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        symbols.append(
            ExtractedSymbol(
                name=name,
                kind="class",
                line_start=start_line,
                line_end=end_line,
                signature=match.group(0).strip(),
            )
        )

    for match in RE_GENERIC_FN.finditer(content):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_matching_brace_end(lines, start_line - 1)
        symbols.append(
            ExtractedSymbol(
                name=name,
                kind="function",
                line_start=start_line,
                line_end=end_line,
                signature=match.group(0).strip(),
            )
        )

    return ParseResult(
        symbols=symbols,
        imports=imports,
        calls=[],
        inheritances=[],
    )


# ---------------------------------------------------------------------------
# Master Dispatcher
# ---------------------------------------------------------------------------

def parse_file(content: str, language: Optional[str] = None) -> ParseResult:
    """Dispatches content parsing based on language.

    Returns structured ParseResult containing symbols, imports, calls, and inheritances.
    """
    if not content or not content.strip():
        return ParseResult(symbols=[], imports=[], calls=[], inheritances=[])

    lang = (language or "").lower()

    if "python" in lang:
        return parse_python_code(content)
    elif any(k in lang for k in ["javascript", "typescript", "tsx", "jsx"]):
        return parse_js_ts_code(content, language or "JavaScript")
    else:
        return parse_generic_code(content, language or "Generic")
