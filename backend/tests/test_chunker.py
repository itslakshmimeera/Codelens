import pytest
from app.services.chunker import chunk_file_content
from app.services.parser import ExtractedSymbol


def test_chunk_file_with_symbols():
    content = """def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
    symbols = [
        ExtractedSymbol(name="add", kind="function", line_start=1, line_end=2),
        ExtractedSymbol(name="multiply", kind="function", line_start=4, line_end=5),
    ]

    chunks = chunk_file_content(content, symbols)
    assert len(chunks) == 2
    assert chunks[0].symbol_name == "add"
    assert "add" in chunks[0].content
    assert chunks[1].symbol_name == "multiply"
    assert "multiply" in chunks[1].content


def test_chunk_file_fallback_sliding_window():
    # Long text without symbols
    content = "\n".join([f"line {i}" for i in range(1, 150)])
    chunks = chunk_file_content(content, symbols=None, max_chunk_lines=50, overlap_lines=10)

    assert len(chunks) >= 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 50
