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
        response = client.post("/api/upload", files={"file": ("TestMod.json", f, "application/json")})
        
    assert response.status_code == 200
    assert "job_id" in response.json()
    assert response.json()["plugin_name"] == "TestMod"

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


def test_auto_detect_mo2_fallback():
    response = client.get("/api/mo2/auto-detect")
    assert response.status_code == 200
    data = response.json()
    assert "found" in data
    if not data["found"]:
        assert data["mods"] == []


def test_inject_invalid_job():
    res = client.post("/api/mo2/inject/non_existent_id", json={
        "mo2_path": "C:\\mods",
        "mod_name": "AnyMod"
    })
    assert res.status_code == 404

