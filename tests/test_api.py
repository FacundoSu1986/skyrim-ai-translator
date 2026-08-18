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


def test_mo2_start_with_skyrim_data_path(tmp_path):
    mo2_dir = tmp_path / "mods"
    mod_folder = mo2_dir / "SkyrimQuest"
    mod_folder.mkdir(parents=True)
    skyrim_data = tmp_path / "SkyrimData"
    skyrim_data.mkdir()

    # 1. Valid skyrim_data_path -> accepted
    res_valid = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "SkyrimQuest",
        "skyrim_data_path": str(skyrim_data),
        "target_lang": "Spanish",
        "generate_voice": False
    })
    assert res_valid.status_code == 200
    job_id = res_valid.json()["job_id"]
    assert jobs[job_id]["config"]["skyrim_data_path"] == str(skyrim_data)

    # 2. Missing / None skyrim_data_path -> allowed
    res_none = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "SkyrimQuest",
        "skyrim_data_path": None,
        "target_lang": "Spanish",
        "generate_voice": False
    })
    assert res_none.status_code == 200

    # 3. Invalid / non-existent skyrim_data_path -> rejected HTTP 400
    res_invalid = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "SkyrimQuest",
        "skyrim_data_path": "Z:\\non_existent_skyrim_data_999",
        "target_lang": "Spanish",
        "generate_voice": False
    })
    assert res_invalid.status_code == 400
    assert "Skyrim Data" in res_invalid.json()["detail"]


def test_upload_skyrim_data_path_validation(tmp_path):
    test_json = tmp_path / "ModA.json"
    test_json.write_text('[{"FormID": "0001", "Text": "Test text"}]', encoding="utf-8")
    skyrim_data = tmp_path / "SkyrimData"
    skyrim_data.mkdir()

    # 1. Valid skyrim_data_path in config -> accepted
    with open(test_json, "rb") as f:
        res_valid = client.post(
            "/api/upload",
            files={"file": ("ModA.json", f, "application/json")},
            data={"config": json.dumps({"skyrim_data_path": str(skyrim_data)})}
        )
    assert res_valid.status_code == 200

    # 2. Missing skyrim_data_path -> allowed
    with open(test_json, "rb") as f:
        res_none = client.post(
            "/api/upload",
            files={"file": ("ModA.json", f, "application/json")},
            data={"config": json.dumps({"target_lang": "Spanish"})}
        )
    assert res_none.status_code == 200

    # 3. Invalid skyrim_data_path -> rejected HTTP 400
    with open(test_json, "rb") as f:
        res_invalid = client.post(
            "/api/upload",
            files={"file": ("ModA.json", f, "application/json")},
            data={"config": json.dumps({"skyrim_data_path": "Z:\\invalid_skyrim_data_path_123"})}
        )
    assert res_invalid.status_code == 400
    assert "Skyrim Data" in res_invalid.json()["detail"]


def test_websocket_empty_plugin_no_mock_fallback(tmp_path):
    """Verify that an empty or localized plugin fails fast without injecting mock 'Welcome to...' or MaleNord."""
    test_json = tmp_path / "EmptyMod.json"
    test_json.write_text("[]", encoding="utf-8")

    with open(test_json, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("EmptyMod.json", f, "application/json")},
            data={"config": json.dumps({"generate_voice": True})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    # Connect to WebSocket and consume events
    messages = []
    with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
        while True:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ["completed", "error"]:
                    break
            except Exception:
                break

    # Must fail fast with status="error" and error_code="NO_TRANSLATABLE_CONTENT"
    assert jobs[job_id]["status"] == "error"
    error_events = [m for m in messages if m.get("status") == "error"]
    assert len(error_events) > 0
    assert error_events[-1].get("error_code") == "NO_TRANSLATABLE_CONTENT"
    assert isinstance(error_events[-1].get("error"), str)

    # Must NOT contain fake mock text or voice
    log_texts = " ".join(m.get("log", "") for m in messages)
    assert "Welcome to" not in log_texts
    assert "MaleNord" not in log_texts

    # Build dir must NOT contain any DSD or ZIP
    build_dir = Path(jobs[job_id]["output_dir"])
    assert not (build_dir / "SKSE").exists()


def test_websocket_unresolved_voice_fail_fast(tmp_path):
    """Verify that dialogue with voice_type=None and generate_voice=True fails fast with 0 audio files and no auto-inject."""
    test_json = tmp_path / "NoVoiceMod.json"
    dialogue_data = [
        {"FormID": "0005555A", "Text": "Who goes there?", "is_dialog": True, "voice_type": None}
    ]
    test_json.write_text(json.dumps(dialogue_data), encoding="utf-8")

    with open(test_json, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("NoVoiceMod.json", f, "application/json")},
            data={"config": json.dumps({"generate_voice": True, "auto_inject": True})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = []
    with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
        while True:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ["completed", "error"]:
                    break
            except Exception:
                break

    # Must fail fast with status="error" and error_code="UNRESOLVED_VOICE_TYPES"
    assert jobs[job_id]["status"] == "error"
    error_events = [m for m in messages if m.get("status") == "error"]
    assert len(error_events) > 0
    assert error_events[-1].get("error_code") == "UNRESOLVED_VOICE_TYPES"
    assert isinstance(error_events[-1].get("error"), str)

    # Must NOT generate any audio files in Sound/Voice
    build_dir = Path(jobs[job_id]["output_dir"])
    voice_dir = build_dir / "Sound" / "Voice"
    if voice_dir.exists():
        audio_files = list(voice_dir.rglob("*.mp3"))
        assert len(audio_files) == 0, f"Expected 0 audio files, got {audio_files}"


def test_websocket_unresolved_voice_allowed_when_voice_disabled(tmp_path):
    """Verify that dialogue with voice_type=None completes translation normally when generate_voice=False."""
    test_json = tmp_path / "TextOnlyMod.json"
    dialogue_data = [
        {"FormID": "0007777A", "Text": "A letter from the Jarl.", "is_dialog": True, "voice_type": None}
    ]
    test_json.write_text(json.dumps(dialogue_data), encoding="utf-8")

    with open(test_json, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("TextOnlyMod.json", f, "application/json")},
            data={"config": json.dumps({"generate_voice": False})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = []
    with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
        while True:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ["completed", "error"]:
                    break
            except Exception:
                break

    assert jobs[job_id]["status"] == "completed"
    # Legacy JSON input carries no DSD metadata: the export must be skipped
    # explicitly (warning logged), not fabricated as a success artifact.
    build_dir = Path(jobs[job_id]["output_dir"])
    assert not (build_dir / "SKSE").exists()
    log_texts = " ".join(m.get("log", "") for m in messages)
    assert "Export DSD omitido" in log_texts


def test_upload_esp_skyrim_data_path_flow(tmp_path):
    """Verify that skyrim_data_path flows from /api/upload config to parse_esp_file master_search_paths."""
    import struct
    from tests.test_esp_and_voice import make_tes4_header, make_grup, make_record, make_subrecord
    from tests.test_dsd_metadata import make_trdt

    # 1. Master in Skyrim Data path
    skyrim_data = tmp_path / "SkyrimData"
    skyrim_data.mkdir()
    master_path = skyrim_data / "Skyrim.esm"
    vtyp_rec = make_record(b"VTYP", 0x00010001, make_subrecord(b"EDID", b"MaleNord\x00"))
    npc_rec = make_record(
        b"NPC_",
        0x0001A697,
        make_subrecord(b"FULL", b"Balgruuf\x00") +
        make_subrecord(b"VTCK", struct.pack("<I", 0x00010001))
    )
    master_path.write_bytes(make_tes4_header([]) + make_grup(b"NPC_", vtyp_rec + npc_rec))

    # 2. Mod ESP referencing Balgruuf
    mod_esp = tmp_path / "QuestMod.esp"
    info_rec = make_record(
        b"INFO",
        0x01000001,
        make_subrecord(b"ANAM", struct.pack("<I", 0x0001A697)) +
        make_subrecord(b"TRDT", make_trdt(0)) +
        make_subrecord(b"NAM1", b"Greetings dragonborn.\x00")
    )
    mod_esp.write_bytes(make_tes4_header(["Skyrim.esm"]) + make_grup(b"INFO", info_rec))

    # 3. Upload with config containing skyrim_data_path and generate_voice=False
    with open(mod_esp, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("QuestMod.esp", f, "application/octet-stream")},
            data={"config": json.dumps({
                "skyrim_data_path": str(skyrim_data),
                "generate_voice": False
            })}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = []
    with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
        while True:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ["completed", "error"]:
                    break
            except Exception:
                break

    assert jobs[job_id]["status"] == "completed"


def _run_websocket_job(job_id: str) -> list[dict]:
    messages = []
    with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
        while True:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ["completed", "error"]:
                    break
            except Exception:
                break
    return messages


def test_websocket_esp_dsd_official_output_path_and_content(tmp_path):
    """Golden path L: ESP jobs write the official DSD layout with 1->N content."""
    import struct
    from tests.test_esp_and_voice import make_tes4_header, make_grup, make_record, make_subrecord
    from tests.test_dsd_metadata import make_trdt

    # TargetMod.esp: target-new BOOK, Skyrim.esm override BOOK, and one INFO
    # carrying two indexed responses (NAM1 index 0 and 4).
    mod_esp = tmp_path / "TargetMod.esp"
    new_book = make_record(
        b"BOOK", 0x01000123,
        make_subrecord(b"EDID", b"MyBook\x00") + make_subrecord(b"FULL", b"Ancient Book\x00")
    )
    override_book = make_record(
        b"BOOK", 0x0001A697,
        make_subrecord(b"EDID", b"OvrBook\x00") + make_subrecord(b"FULL", b"Overridden Book\x00")
    )
    multi_info = make_record(
        b"INFO", 0x01000333,
        make_subrecord(b"TRDT", make_trdt(0)) + make_subrecord(b"NAM1", b"First response\x00") +
        make_subrecord(b"TRDT", make_trdt(4)) + make_subrecord(b"NAM1", b"Second response\x00")
    )
    mod_esp.write_bytes(
        make_tes4_header(["Skyrim.esm"])
        + make_grup(b"BOOK", new_book + override_book)
        + make_grup(b"INFO", multi_info)
    )

    with open(mod_esp, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("TargetMod.esp", f, "application/octet-stream")},
            data={"config": json.dumps({"generate_voice": False})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = _run_websocket_job(job_id)
    assert jobs[job_id]["status"] == "completed", jobs[job_id].get("error")

    build_dir = Path(jobs[job_id]["output_dir"])
    dsd_file = (
        build_dir / "SKSE" / "Plugins" / "DynamicStringDistributor"
        / "TargetMod.esp" / "SkyrimAITranslator.json"
    )
    assert dsd_file.exists(), f"Expected official DSD path {dsd_file}"
    assert not (build_dir / "SKSE" / "Plugins" / "DSD").exists()

    content = json.loads(dsd_file.read_text(encoding="utf-8"))
    assert isinstance(content, list)

    by_form_type = {(item["form_id"], item["type"]): item for item in content}
    assert by_form_type[("0x000123|TargetMod.esp", "BOOK FULL")]["string"]
    assert by_form_type[("0x01A697|Skyrim.esm", "BOOK FULL")]["string"]

    info_items = [
        item for item in content
        if item["form_id"] == "0x000333|TargetMod.esp" and item["type"] == "INFO NAM1"
    ]
    # Indexed 1->N: both responses of the same INFO survive the whole
    # pipeline with their own index.
    assert {item["index"] for item in info_items} == {0, 4}
    assert len(info_items) == 2


def test_websocket_preflight_unsupported_type_fails_before_translation(tmp_path, monkeypatch):
    """FACT FULL cannot be represented by DSD 1.4.3: the job must fail fast
    with DSD_UNSUPPORTED_TYPE before spending any LLM call."""
    import api as api_module
    from tests.test_esp_and_voice import make_tes4_header, make_grup, make_record, make_subrecord

    async def _translator_must_not_run(_text, _context):
        raise AssertionError("translator must not run when DSD preflight fails")

    monkeypatch.setattr(api_module, "free_translator_callable", _translator_must_not_run)

    mod_esp = tmp_path / "FactionMod.esp"
    fact_rec = make_record(
        b"FACT", 0x00000123,
        make_subrecord(b"EDID", b"MyFaction\x00") + make_subrecord(b"FULL", b"Thieves Guild\x00")
    )
    mod_esp.write_bytes(make_tes4_header([]) + make_grup(b"FACT", fact_rec))

    with open(mod_esp, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("FactionMod.esp", f, "application/octet-stream")},
            data={"config": json.dumps({"generate_voice": False})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = _run_websocket_job(job_id)

    assert jobs[job_id]["status"] == "error"
    assert jobs[job_id]["error_code"] == "DSD_UNSUPPORTED_TYPE"
    error_events = [m for m in messages if m.get("status") == "error"]
    assert error_events[-1]["error_code"] == "DSD_UNSUPPORTED_TYPE"
    assert "FACT FULL" in error_events[-1]["error"]


def test_websocket_preflight_missing_index_fails_fast(tmp_path):
    """INFO NAM1 without a resolvable TRDT index must fail fast with
    DSD_METADATA_MISSING before translation."""
    import struct
    from tests.test_esp_and_voice import make_tes4_header, make_grup, make_record, make_subrecord

    mod_esp = tmp_path / "BrokenInfo.esp"
    info_rec = make_record(
        b"INFO", 0x00000555,
        make_subrecord(b"ANAM", struct.pack("<I", 0)) +
        make_subrecord(b"NAM1", b"Response without TRDT\x00")
    )
    mod_esp.write_bytes(make_tes4_header([]) + make_grup(b"INFO", info_rec))

    with open(mod_esp, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("BrokenInfo.esp", f, "application/octet-stream")},
            data={"config": json.dumps({"generate_voice": False})}
        )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    messages = _run_websocket_job(job_id)

    assert jobs[job_id]["status"] == "error"
    assert jobs[job_id]["error_code"] == "DSD_METADATA_MISSING"
    error_events = [m for m in messages if m.get("status") == "error"]
    assert error_events[-1]["error_code"] == "DSD_METADATA_MISSING"


def test_upload_esp_preserves_target_plugin_filename(tmp_path):
    """ESP/ESM/ESL uploads capture the real plugin filename with its extension."""
    esp = tmp_path / "MyMaster.esm"
    esp.write_bytes(b"TES4 dummy")

    with open(esp, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("MyMaster.esm", f, "application/octet-stream")}
        )
    assert res.status_code == 200
    job = jobs[res.json()["job_id"]]
    assert job["target_plugin_filename"] == "MyMaster.esm"
    # plugin_name keeps its existing extension-less semantics
    assert job["plugin_name"] == "MyMaster"


def test_upload_json_has_no_target_plugin_filename(tmp_path):
    """Legacy JSON uploads never fabricate a target plugin filename."""
    test_json = tmp_path / "ModA.json"
    test_json.write_text('[{"FormID": "0001", "Text": "Hi"}]', encoding="utf-8")

    with open(test_json, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": ("ModA.json", f, "application/json")}
        )
    assert res.status_code == 200
    job = jobs[res.json()["job_id"]]
    assert job["target_plugin_filename"] is None
    assert job["plugin_name"] == "ModA"


def test_mo2_start_esp_capture_target_plugin_filename(tmp_path):
    """MO2 jobs with a native plugin capture the plugin's real filename."""
    mo2_dir = tmp_path / "mods"
    mod_folder = mo2_dir / "CoolCompanion"
    mod_folder.mkdir(parents=True)
    (mod_folder / "CoolCompanion.esp").write_bytes(b"TES4 dummy")

    res = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "CoolCompanion"
    })
    assert res.status_code == 200
    job = jobs[res.json()["job_id"]]
    assert job["target_plugin_filename"] == "CoolCompanion.esp"
    assert job["plugin_name"] == "CoolCompanion"


def test_mo2_start_json_has_no_target_plugin_filename(tmp_path):
    """MO2 jobs falling back to legacy JSON never fabricate a target plugin filename."""
    mo2_dir = tmp_path / "mods"
    mod_folder = mo2_dir / "TextMod"
    mod_folder.mkdir(parents=True)
    (mod_folder / "strings.json").write_text(
        '[{"FormID": "0001", "Text": "Hi"}]', encoding="utf-8"
    )

    res = client.post("/api/mo2/start", json={
        "mo2_path": str(mo2_dir),
        "mod_name": "TextMod"
    })
    assert res.status_code == 200
    job = jobs[res.json()["job_id"]]
    assert job["target_plugin_filename"] is None


def test_websocket_job_already_processing_rejects_concurrent_connection():
    """A second WebSocket connecting while status is 'processing' receives JOB_ALREADY_PROCESSING with current progress."""
    job_id = "test-job-processing-123"
    jobs[job_id] = {
        "status": "processing",
        "progress": 42,
        "logs": [],
    }
    try:
        with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["status"] == "error"
            assert msg["error_code"] == "JOB_ALREADY_PROCESSING"
            assert msg["error"] == "El trabajo ya se encuentra en procesamiento."
            assert msg["progress"] == 42
            assert msg["job_id"] == job_id
    finally:
        jobs.pop(job_id, None)


def test_websocket_reconnect_completed_job():
    """A WebSocket connecting to a 'completed' job receives download_url, has_mo2, and progress 100."""
    job_id = "test-job-completed-456"
    jobs[job_id] = {
        "status": "completed",
        "progress": 100,
        "mo2_path": "/fake/mo2/path",
        "mod_name": "CoolMod",
    }
    try:
        with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["status"] == "completed"
            assert msg["progress"] == 100
            assert msg["download_url"] == f"/api/download/{job_id}"
            assert msg["job_id"] == job_id
            assert msg["has_mo2"] is True
    finally:
        jobs.pop(job_id, None)


def test_websocket_reconnect_error_job():
    """A WebSocket connecting to an 'error' job receives the error, error_code, and progress 100."""
    job_id = "test-job-error-789"
    jobs[job_id] = {
        "status": "error",
        "error_code": "NO_TRANSLATABLE_CONTENT",
        "error": "No hay contenido traducible.",
        "progress": 100,
    }
    try:
        with client.websocket_connect(f"/ws/progress/{job_id}") as ws:
            msg = ws.receive_json()
            assert msg["status"] == "error"
            assert msg["error_code"] == "NO_TRANSLATABLE_CONTENT"
            assert msg["error"] == "No hay contenido traducible."
            assert msg["progress"] == 100
            assert msg["job_id"] == job_id
    finally:
        jobs.pop(job_id, None)


