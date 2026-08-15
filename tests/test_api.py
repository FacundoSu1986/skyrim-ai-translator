import json
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from api import app, jobs

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "active_jobs" in data
    assert "available_voices" in data
    assert data["service"] == "skyrim-ai-translator-api"


def test_health_active_jobs_counting():
    """Verify active_jobs strictly counts 'pending' and 'processing' states, excluding 'completed' and 'failed'."""
    original_jobs = dict(jobs)
    try:
        jobs.clear()
        # Arrange
        jobs["job_1"] = {"status": "pending"}
        jobs["job_2"] = {"status": "processing"}
        jobs["job_3"] = {"status": "completed"}
        jobs["job_4"] = {"status": "failed"}

        # Act
        response = client.get("/api/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["active_jobs"] == 2
    finally:
        jobs.clear()
        jobs.update(original_jobs)


def test_get_voices():
    response = client.get("/api/voices")
    assert response.status_code == 200
    assert "voices" in response.json()
    assert len(response.json()["voices"]) > 0

def test_get_mo2_mods(tmp_path):
    mod_dir = tmp_path / "mods"
    mod_dir.mkdir()
    (mod_dir / "SkyUI").mkdir()
    (mod_dir / "Unofficial Patch").mkdir()
    
    response = client.get(f"/api/mo2/mods?path={mod_dir}")
    assert response.status_code == 200
    assert response.json() == {"mods": ["SkyUI", "Unofficial Patch"]}

def test_get_mo2_mods_invalid_path():
    response = client.get("/api/mo2/mods?path=non_existent_folder_xyz")
    assert response.status_code == 200
    assert response.json() == {"mods": []}

def test_upload_json(tmp_path):
    test_json = tmp_path / "TestMod.json"
    test_json.write_text('[{"FormID": "0001", "Text": "Hi"}]', encoding="utf-8")
    
    with open(test_json, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("TestMod.json", f, "application/json")},
            data={"config": '{"api_key": "sk-secret-key", "target_lang": "French"}'}
        )
        
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert response.json()["plugin_name"] == "TestMod"
    # Verify api_key is NOT retained in job["config"]
    assert "api_key" not in jobs[job_id]["config"]
    assert jobs[job_id]["api_key"] == "sk-secret-key"

def test_mo2_start_invalid_mo2_path():
    res = client.post("/api/mo2/start", json={
        "mo2_path": "Z:\\non_existent_drive_folder_123",
        "mod_name": "AnyMod"
    })
    assert res.status_code == 400
    assert "MO2" in res.json()["detail"]

def test_mo2_start_and_inject(tmp_path):
    mo2_dir = tmp_path / "mods"
    mod_folder = mo2_dir / "CoolCompanion"
    mod_folder.mkdir(parents=True)
    
    # 1. Start MO2 job
    res = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "CoolCompanion",
        "target_lang": "Spanish",
        "generate_voice": False
    })
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    
    # Simulate job build output
    job = jobs[job_id]
    build_dir = Path(job["output_dir"])
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "test_file.txt").write_text("Hello Skyrim")
    
    # 2. Test Inject endpoint
    res_inject = client.post(f"/api/mo2/inject/{job_id}", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "CoolCompanion"
    })
    assert res_inject.status_code == 200
    assert res_inject.json()["success"] is True
    assert (mod_folder / "test_file.txt").exists()


def test_auto_detect_mo2_fallback(monkeypatch):
    """Verify MO2 auto-detection fallback returns found=False and empty mods deterministically when paths do not exist."""
    import api

    # Arrange
    monkeypatch.setattr(api.os.path, "isdir", lambda p: False)

    # Act
    response = client.get("/api/mo2/auto-detect")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["mods"] == []


def test_inject_invalid_job():
    res = client.post("/api/mo2/inject/non_existent_id", json={
        "mo2_path": "C:\\mods",
        "mod_name": "AnyMod"
    })
    assert res.status_code == 404

