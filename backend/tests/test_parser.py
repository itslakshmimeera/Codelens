import pytest
from app.services.parser import parse_file, parse_js_ts_code, parse_python_code


def test_parse_python_classes_and_methods():
    sample_code = '''"""Sample module docstring."""

class UserService(BaseService):
    """Handles user operations."""
    def __init__(self, db: Database):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Finds user by primary key."""
        return await self.db.find(user_id)

def helper_function(value: str) -> str:
    """Helper utility."""
    return value.strip()
'''
    result = parse_python_code(sample_code)

    # Symbols check
    symbols = result.symbols
    assert len(symbols) == 2  # UserService and helper_function

    cls_sym = next(s for s in symbols if s.name == "UserService")
    assert cls_sym.kind == "class"
    assert cls_sym.docstring == "Handles user operations."
    assert len(cls_sym.children) == 2

    init_method = next(m for m in cls_sym.children if m.name == "__init__")
    assert init_method.kind == "method"
    assert init_method.parent_name == "UserService"

    get_method = next(m for m in cls_sym.children if m.name == "get_user_by_id")
    assert get_method.kind == "method"
    assert get_method.docstring == "Finds user by primary key."

    fn_sym = next(s for s in symbols if s.name == "helper_function")
    assert fn_sym.kind == "function"
    assert fn_sym.docstring == "Helper utility."

    # Inheritance check
    assert ("UserService", "BaseService") in result.inheritances


def test_parse_python_imports_and_calls():
    sample_code = """from os import path
import sys
from app.models.repository import Repository, File
from .utils import calculate

def run():
    print("test")
    calculate()
"""
    result = parse_python_code(sample_code)

    assert len(result.imports) == 4
    imp_repo = next(i for i in result.imports if i.module == "app.models.repository")
    assert "Repository" in imp_repo.symbols
    assert "File" in imp_repo.symbols

    rel_imp = next(i for i in result.imports if i.module == "utils")
    assert rel_imp.is_relative is True

    # Call check
    calls = [c.target_name for c in result.calls]
    assert "calculate" in calls or "print" in calls


def test_parse_typescript_components_and_interfaces():
    sample_ts = """import React, { useState } from 'react';
import { Button } from './components/Button';

export interface UserProfileProps {
  userId: string;
  name: string;
}

export class ProfileManager extends BaseManager {
  render() {
    return null;
  }
}

export const UserCard = ({ userId, name }: UserProfileProps) => {
  return <div>{name}</div>;
};

function formatName(input: string): string {
  return input.toUpperCase();
}
"""
    result = parse_file(sample_ts, language="TypeScript (React)")

    names = {s.name for s in result.symbols}
    assert "UserProfileProps" in names
    assert "ProfileManager" in names
    assert "UserCard" in names
    assert "formatName" in names

    # Imports check
    modules = {i.module for i in result.imports}
    assert "react" in modules
    assert "./components/Button" in modules
