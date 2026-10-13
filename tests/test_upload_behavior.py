import os, glob, tempfile
os.environ.setdefault("GEMINI_API_KEY", "dummy-key")

import pytest
from fastapi.testclient import TestClient
from fastapi_app import app, get_session_manager


@pytest.fixture
def client():
    app.state.limiter.enabled = False   # slowapi: avoid 5/min limit in tests
    return TestClient(app)


def sessions():
    return get_session_manager().sessions


def research_dirs():
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "research_*")))


def test_path_traversal_stays_inside_temp_dir(client):
    r = client.post("/upload", files=[("files", ("../../evil.txt", b"hello", "text/plain"))])
    assert r.status_code == 200, r.text
    s = list(sessions().values())[-1]
    assert os.listdir(s.temp_dir) == ["evil.txt"]


def test_too_many_files_rejected_without_session(client):
    before = len(sessions())
    files = [("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(11)]
    r = client.post("/upload", files=files)
    assert r.status_code == 400
    assert len(sessions()) == before


def test_oversize_file_rejected_and_cleaned_up(client):
    before_sessions, before_dirs = len(sessions()), research_dirs()
    big = b"a" * (51 * 1024 * 1024)
    r = client.post("/upload", files=[("files", ("big.txt", big, "text/plain"))])
    assert r.status_code == 400
    assert len(sessions()) == before_sessions      # no orphaned session
    assert research_dirs() == before_dirs          # no leaked temp dir


def test_duplicate_names_get_distinct_files(client):
    files = [("files", ("same.txt", b"a", "text/plain")),
             ("files", ("same.txt", b"b", "text/plain"))]
    r = client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    s = list(sessions().values())[-1]
    assert len(set(os.listdir(s.temp_dir))) == 2