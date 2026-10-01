from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_server import list_github_prs

result = list_github_prs("Lomesh2000", "hadoop")

print(result)