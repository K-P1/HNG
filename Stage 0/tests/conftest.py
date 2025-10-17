import os
import sys
from fastapi.testclient import TestClient

# Ensure project root is on sys.path when pytest runs from a different CWD.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.main import app  # noqa: E402
import pytest  # noqa: E402

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
