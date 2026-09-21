from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.mcp_server import get_github_file


def test_get_github_file_handles_missing_repo():
    result = get_github_file("Lomesh-AI", "definitely-not-a-real-repo-xyz", "README.md")

    assert "error" in result.lower() or "not found" in result.lower()
