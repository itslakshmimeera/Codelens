from dataclasses import dataclass
from typing import List, Optional

from app.services.parser import ExtractedSymbol


@dataclass
class GeneratedChunk:
    """A semantic chunk of code ready to be indexed and searched."""

    content: str
    start_line: int
    end_line: int
    chunk_index: int
    symbol_name: Optional[str] = None


def chunk_file_content(
    content: str,
    symbols: Optional[List[ExtractedSymbol]] = None,
    max_chunk_lines: int = 60,
    overlap_lines: int = 10,
) -> List[GeneratedChunk]:
    """Divides source code into meaningful structural chunks.

    Prioritizes AST/extracted symbols (classes, functions, methods).
    Falls back to windowed line chunking with overlap for remaining code.
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total_lines = len(lines)
    chunks: List[GeneratedChunk] = []
    chunk_idx = 0
    covered_lines = set()

    # 1. Structural Chunks based on extracted symbols
    if symbols:
        for sym in symbols:
            s_start = max(1, sym.line_start)
            s_end = min(total_lines, sym.line_end)
            if s_start <= s_end:
                snippet = "".join(lines[s_start - 1 : s_end])
                if snippet.strip():
                    chunks.append(
                        GeneratedChunk(
                            content=snippet,
                            start_line=s_start,
                            end_line=s_end,
                            chunk_index=chunk_idx,
                            symbol_name=sym.name,
                        )
                    )
                    chunk_idx += 1
                    covered_lines.update(range(s_start, s_end + 1))

            # Include children (methods inside classes)
            for child in sym.children:
                c_start = max(1, child.line_start)
                c_end = min(total_lines, child.line_end)
                if c_start <= c_end:
                    c_snippet = "".join(lines[c_start - 1 : c_end])
                    if c_snippet.strip():
                        chunks.append(
                            GeneratedChunk(
                                content=c_snippet,
                                start_line=c_start,
                                end_line=c_end,
                                chunk_index=chunk_idx,
                                symbol_name=f"{sym.name}.{child.name}",
                            )
                        )
                        chunk_idx += 1
                        covered_lines.update(range(c_start, c_end + 1))

    # 2. Sequential fallback chunking for non-symbol or remaining lines
    # If file was small and completely covered, return
    if len(covered_lines) >= total_lines and chunks:
        return chunks

    # Otherwise chunk entire file in sliding windows if no symbols were found,
    # or chunk large uncovered gaps
    if not chunks:
        step = max(1, max_chunk_lines - overlap_lines)
        for start_idx in range(0, total_lines, step):
            end_idx = min(total_lines, start_idx + max_chunk_lines)
            chunk_text = "".join(lines[start_idx:end_idx])
            if chunk_text.strip():
                chunks.append(
                    GeneratedChunk(
                        content=chunk_text,
                        start_line=start_idx + 1,
                        end_line=end_idx,
                        chunk_index=chunk_idx,
                        symbol_name=None,
                    )
                )
                chunk_idx += 1

    return chunks
