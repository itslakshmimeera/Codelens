import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SearchResultItem:
    """An individual search match."""

    chunk_id: str
    file_id: str
    file_path: str
    symbol_name: Optional[str]
    content: str
    start_line: int
    end_line: int
    score: float
    language: Optional[str] = None


@dataclass
class AnswerCitation:
    """A citation referencing a specific file and line range in the codebase."""

    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str]
    snippet: str


@dataclass
class QueryAnswer:
    """Structured response to a natural-language codebase question."""

    question: str
    answer: str
    citations: List[AnswerCitation] = field(default_factory=list)
    related_symbols: List[str] = field(default_factory=list)
    confidence: float = 0.95


def _tokenize(text: str) -> List[str]:
    """Tokenizes text and splits camelCase, snake_case, and kebab-case."""
    # Split camelCase
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    # Extract alphanumeric words
    words = re.findall(r"[A-Za-z0-9_]+", s1.lower())
    tokens = []
    for w in words:
        subparts = [p for p in w.split("_") if p]
        tokens.extend(subparts)
    return tokens


class CodeSearchEngine:
    """Lexical and semantic retrieval engine for indexed code chunks and symbols."""

    def __init__(self, chunks_data: List[Dict[str, Any]]):
        """chunks_data is a list of dicts with:

        id, file_id, file_path, language, symbol_name, content, start_line, end_line
        """
        self.chunks = chunks_data
        self.doc_tokens: List[List[str]] = []
        self.doc_freq: Dict[str, int] = {}
        self.total_docs = len(chunks_data)
        self._build_index()

    def _build_index(self):
        for doc in self.chunks:
            # Combine symbol name, file path, and code content for search
            text = f"{doc.get('file_path', '')} {doc.get('symbol_name', '') or ''} {doc.get('content', '')}"
            tokens = _tokenize(text)
            self.doc_tokens.append(tokens)
            unique_terms = set(tokens)
            for t in unique_terms:
                self.doc_freq[t] = self.doc_freq.get(t, 0) + 1

    def search(self, query: str, top_k: int = 10) -> List[SearchResultItem]:
        """Searches indexed code chunks and ranks them by BM25-like relevance and symbol matches."""
        if not query or not query.strip() or not self.chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: List[Tuple[float, int]] = []
        avg_doc_len = (
            sum(len(toks) for toks in self.doc_tokens) / max(1, self.total_docs)
            if self.total_docs > 0
            else 1.0
        )
        k1 = 1.5
        b = 0.75

        for idx, (doc, doc_tokens) in enumerate(zip(self.chunks, self.doc_tokens)):
            doc_len = len(doc_tokens)
            score = 0.0
            doc_token_counts: Dict[str, int] = {}
            for t in doc_tokens:
                doc_token_counts[t] = doc_token_counts.get(t, 0) + 1

            for qt in query_tokens:
                tf = doc_token_counts.get(qt, 0)
                if tf > 0:
                    df = self.doc_freq.get(qt, 1)
                    idf = math.log(1 + (self.total_docs - df + 0.5) / (df + 0.5))
                    # BM25 term score
                    term_score = idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len))))
                    score += max(0.1, term_score)

            # High bonus for exact symbol match
            sym_name = (doc.get("symbol_name") or "").lower()
            file_name = doc.get("file_path", "").lower()
            for qt in query_tokens:
                if sym_name and qt in sym_name:
                    score += 5.0
                if qt in file_name:
                    score += 2.0

            if score > 0:
                scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        results: List[SearchResultItem] = []

        for score, idx in scores[:top_k]:
            doc = self.chunks[idx]
            results.append(
                SearchResultItem(
                    chunk_id=str(doc.get("id")),
                    file_id=str(doc.get("file_id")),
                    file_path=doc.get("file_path", ""),
                    symbol_name=doc.get("symbol_name"),
                    content=doc.get("content", ""),
                    start_line=doc.get("start_line", 1),
                    end_line=doc.get("end_line", 1),
                    score=round(score, 3),
                    language=doc.get("language"),
                )
            )

        return results


def synthesize_codebase_answer(
    question: str,
    search_results: List[SearchResultItem],
    all_symbols: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]],
) -> QueryAnswer:
    """Constructs an intelligent explanation based on retrieved code context and repository relationships."""
    if not search_results:
        return QueryAnswer(
            question=question,
            answer="No relevant code sections or symbols were found in the indexed repository for your query.",
            citations=[],
            related_symbols=[],
            confidence=0.0,
        )

    # Citations
    citations: List[AnswerCitation] = []
    found_symbols: Set[str] = set()
    files_referenced: Set[str] = set()

    for item in search_results[:5]:
        snippet_lines = item.content.splitlines()[:15]
        snippet_preview = "\n".join(snippet_lines)
        if len(item.content.splitlines()) > 15:
            snippet_preview += "\n// ... remaining lines truncated ..."

        citations.append(
            AnswerCitation(
                file_path=item.file_path,
                start_line=item.start_line,
                end_line=item.end_line,
                symbol_name=item.symbol_name,
                snippet=snippet_preview,
            )
        )
        files_referenced.add(item.file_path)
        if item.symbol_name:
            found_symbols.add(item.symbol_name)

    top_item = search_results[0]

    # Look up related dependencies for primary file/symbol
    related_deps = [
        d for d in dependencies
        if d.get("source_file") == top_item.file_path or d.get("target_file") == top_item.file_path
    ]

    # Synthesize Markdown answer
    answer_paragraphs = []
    answer_paragraphs.append(
        f"### Codebase Intelligence Analysis\n\n"
        f"Based on repository indexing, the implementation for **\"{question}\"** is primarily located in "
        f"`{top_item.file_path}`"
        + (f" within symbol `{top_item.symbol_name}`" if top_item.symbol_name else "")
        + f" (lines {top_item.start_line}–{top_item.end_line})."
    )

    if len(files_referenced) > 1:
        other_files = [f"`{f}`" for f in files_referenced if f != top_item.file_path]
        answer_paragraphs.append(
            f"**Related Modules Identified:** {', '.join(other_files[:4])}"
        )

    if found_symbols:
        sym_tags = [f"`{s}`" for s in list(found_symbols)[:6]]
        answer_paragraphs.append(f"**Key Entities & Symbols:** {', '.join(sym_tags)}")

    if related_deps:
        dep_items = []
        for d in related_deps[:4]:
            t_file = d.get("target_file") or "external package"
            t_sym = d.get("target_symbol") or ""
            dep_items.append(f"- `{d.get('source_file')}` {d.get('type', 'uses')} `{t_file}` ({t_sym})")
        answer_paragraphs.append("**Dependency Connections:**\n" + "\n".join(dep_items))

    answer_paragraphs.append(
        "Review the retrieved code citations below for exact definitions and implementation details."
    )

    full_answer = "\n\n".join(answer_paragraphs)

    return QueryAnswer(
        question=question,
        answer=full_answer,
        citations=citations,
        related_symbols=sorted(list(found_symbols)),
        confidence=min(0.98, max(0.5, round(top_item.score / 10.0, 2))),
    )
