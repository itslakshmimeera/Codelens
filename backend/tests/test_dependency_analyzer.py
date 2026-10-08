import pytest
from app.services.dependency_analyzer import DependencyAnalyzer, analyze_impact
from app.services.parser import ExtractedImport, ParseResult


def test_resolve_python_dependencies():
    files = [
        "app/api/repositories.py",
        "app/models/repository.py",
        "app/services/cloner.py",
    ]
    analyzer = DependencyAnalyzer(files)

    # Test resolving absolute import
    imp = ExtractedImport(module="app.models.repository", symbols=["Repository"], line=10)
    target = analyzer.resolve_python_import("app/api/repositories.py", imp)
    assert target == "app/models/repository.py"

    # Test resolving relative import
    imp_rel = ExtractedImport(module="cloner", symbols=["clone_repository"], line=12, is_relative=True, relative_level=1)
    target_rel = analyzer.resolve_python_import("app/services/scanner.py", imp_rel)
    assert target_rel == "app/services/cloner.py"


def test_analyze_impact_graph():
    deps = [
        {"source_file": "app/api/repositories.py", "target_file": "app/models/repository.py", "type": "import"},
        {"source_file": "app/services/ingestion.py", "target_file": "app/models/repository.py", "type": "import"},
        {"source_file": "app/main.py", "target_file": "app/api/repositories.py", "type": "import"},
    ]

    report = analyze_impact("app/models/repository.py", deps)
    assert report.target == "app/models/repository.py"
    # Direct dependents of repository.py are repositories.py and ingestion.py
    assert "app/api/repositories.py" in report.direct_dependents
    assert "app/services/ingestion.py" in report.direct_dependents
    # Indirect dependent is main.py
    assert "app/main.py" in report.indirect_dependents
    assert "app/main.py" in report.affected_files
