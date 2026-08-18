import asyncio
import json
import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts

# Import backend modules
from src.parser import parse_strings_file
from src.esp_parser import parse_esp_file
from src.voice_mapper import resolve_voice_for_entry
from src.free_translator import free_translator_callable
from src.translator import translate_entries, create_openai_compatible_translator
from src.tts_generator import generate_voice_file
from src.dsd_exporter import export_to_dsd, validate_dsd_entries, DSDExportError

logger = logging.getLogger(__name__)

app = FastAPI(title="Skyrim AI Translation Agent API")

# CORS: allow development hosts by default or custom origins from CORS_ORIGINS
_default_cors = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_cors_raw = os.environ.get("CORS_ORIGINS")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else _default_cors

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for translation jobs and locks per mod
jobs = {}
_mod_locks: dict[str, asyncio.Lock] = {}


def _get_mod_lock(mod_name: str) -> asyncio.Lock:
    """Returns an asyncio.Lock dedicated to the specified mod name."""
    if mod_name not in _mod_locks:
        _mod_locks[mod_name] = asyncio.Lock()
    return _mod_locks[mod_name]


def _sanitize_name(name: str) -> str:
    """Strips any path components so user-supplied names can't escape their target directory."""
    clean = Path(name.replace("\\", "/")).name
    if not clean or clean in {".", ".."}:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    return clean


def _validate_mo2_path(mo2_path: str) -> Path:
    """Validates that mo2_path is provided and points to a real existing directory on the host."""
    if not mo2_path or not mo2_path.strip():
        raise HTTPException(status_code=400, detail="La ruta de MO2 no puede estar vacía")
    p = Path(mo2_path)
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Directorio MO2 inválido o inexistente: {mo2_path}")
    return p


def _validate_skyrim_data_path(skyrim_data_path: Optional[str]) -> Optional[Path]:
    """Validates that skyrim_data_path, if provided, points to a real existing directory."""
    if not skyrim_data_path or not str(skyrim_data_path).strip():
        return None
    p = Path(str(skyrim_data_path).strip())
    if not p.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"La ruta de Skyrim Data no existe o no es un directorio válido: '{skyrim_data_path}'"
        )
    return p


def _copy_build_to_dir(build_dir: Path, target_dir: Path) -> None:
    """Copies every generated artifact from build_dir into target_dir (synchronous)."""
    for item in build_dir.iterdir():
        target_dest = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target_dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target_dest)


def _zip_dir(build_dir: Path, zip_path: Path) -> None:
    """Creates a zip archive containing all files under build_dir."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(build_dir):
            for file in files:
                file_full_path = Path(root) / file
                arcname = file_full_path.relative_to(build_dir)
                zipf.write(file_full_path, arcname)


def _save_upload_file(upload_file: UploadFile, dest_path: Path) -> None:
    """Saves uploaded file chunks to disk synchronously in a worker thread."""
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)


AVAILABLE_VOICES = [
    {"id": "es-ES-AlvaroNeural", "name": "Álvaro (Español España - Masculino)", "lang": "es-ES"},
    {"id": "es-ES-ElviraNeural", "name": "Elvira (Español España - Femenino)", "lang": "es-ES"},
    {"id": "es-ES-DarioNeural", "name": "Darío (Español España - Joven)", "lang": "es-ES"},
    {"id": "es-MX-DaliaNeural", "name": "Dalia (Español México - Femenino)", "lang": "es-MX"},
    {"id": "es-MX-JorgeNeural", "name": "Jorge (Español México - Masculino)", "lang": "es-MX"},
    {"id": "es-AR-TomasNeural", "name": "Tomás (Español Argentina - Masculino)", "lang": "es-AR"},
    {"id": "en-US-GuyNeural", "name": "Guy (English US - Male)", "lang": "en-US"},
]

class MO2TranslateRequest(BaseModel):
    mo2_path: str
    mod_name: str
    skyrim_data_path: Optional[str] = None
    target_lang: str = "Spanish"
    generate_voice: bool = True
    voice: str = "es-ES-AlvaroNeural"
    auto_inject: bool = True
    api_key: Optional[str] = None
    api_base: Optional[str] = "https://api.openai.com/v1"
    model: Optional[str] = "gpt-4o-mini"

class InjectRequest(BaseModel):
    mo2_path: str
    mod_name: str


@app.get("/api/health")
async def health_check():
    """Returns server health status, active jobs (pending or processing), and system capabilities."""
    active_count = sum(
        1 for j in jobs.values()
        if isinstance(j, dict) and j.get("status") in {"pending", "processing"}
    )
    return {
        "status": "healthy",
        "active_jobs": active_count,
        "available_voices": len(AVAILABLE_VOICES),
        "service": "skyrim-ai-translator-api",
        "version": "1.0.0"
    }


@app.get("/api/voices")
async def get_voices():
    """Returns list of available high-quality Edge-TTS voices."""
    return {"voices": AVAILABLE_VOICES}


@app.get("/api/mo2/auto-detect")
async def auto_detect_mo2():
    """Attempts to auto-detect the Mod Organizer 2 mods directory across common drive locations."""
    candidates = [
        r"C:\ModOrganizer\mods",
        r"D:\ModOrganizer\mods",
        r"E:\ModOrganizer\mods",
        r"C:\ModOrganizer2\mods",
        r"D:\ModOrganizer2\mods",
        r"E:\ModOrganizer2\mods",
        r"C:\MO2\mods",
        r"D:\MO2\mods",
        r"E:\MO2\mods",
        r"C:\Games\ModOrganizer\mods",
        r"D:\Games\ModOrganizer\mods",
        r"E:\Traducir Skyrim\mods",
        os.path.expandvars(r"%LOCALAPPDATA%\ModOrganizer\Skyrim Special Edition\mods"),
        os.path.expandvars(r"%LOCALAPPDATA%\ModOrganizer\Skyrim\mods"),
    ]

    for path_str in candidates:
        if path_str and os.path.isdir(path_str):
            try:
                mods = [
                    name for name in os.listdir(path_str)
                    if os.path.isdir(os.path.join(path_str, name)) and not name.startswith(".")
                ]
                if mods:
                    return {"found": True, "path": path_str, "mods": sorted(mods)}
            except Exception:
                pass

    return {"found": False, "path": "", "mods": []}


@app.get("/api/mo2/mods")
async def get_mo2_mods(path: str = Query(...)):
    """Scans and lists installed mods from a Mod Organizer 2 mods folder."""
    if not os.path.isdir(path):
        return {"mods": []}

    try:
        mods = [
            name for name in os.listdir(path)
            if os.path.isdir(os.path.join(path, name)) and not name.startswith(".")
        ]
        return {"mods": sorted(mods)}
    except Exception as e:
        return {"error": str(e), "mods": []}


@app.post("/api/upload")
async def upload_json(
    file: UploadFile = File(...),
    config: Optional[str] = Form(None)
):
    """Uploads a mod JSON or ESP file and creates a new translation job."""
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"output/jobs/{job_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_name(file.filename or "upload.dat")
    file_path = upload_dir / safe_name
    await asyncio.to_thread(_save_upload_file, file, file_path)

    cfg = {}
    transient_api_key = None
    if config:
        try:
            cfg = json.loads(config)
            transient_api_key = cfg.pop("api_key", None)
            if "skyrim_data_path" in cfg and cfg["skyrim_data_path"]:
                _validate_skyrim_data_path(cfg["skyrim_data_path"])
        except HTTPException:
            raise
        except Exception as err:
            logger.warning("JSON de configuración de subida no válido: %s", err)

    plugin_name = safe_name
    for ext in [".json", ".esp", ".esm", ".esl"]:
        if plugin_name.lower().endswith(ext):
            plugin_name = plugin_name[:-len(ext)]

    # Real plugin filename (with extension) for DSD output paths; never fabricated
    # for legacy JSON uploads.
    target_plugin_filename = None
    if Path(safe_name).suffix.lower() in [".esp", ".esm", ".esl"]:
        target_plugin_filename = safe_name

    jobs[job_id] = {
        "status": "pending",
        "file_path": str(file_path),
        "plugin_name": plugin_name,
        "target_plugin_filename": target_plugin_filename,
        "config": cfg,
        "api_key": transient_api_key,
        "progress": 0,
        "logs": [],
        "output_dir": str(upload_dir / "build")
    }
    return {"job_id": job_id, "plugin_name": plugin_name}


@app.post("/api/mo2/start")
async def start_mo2_translation(req: MO2TranslateRequest):
    """Starts translation job directly from a mod selected in Mod Organizer 2."""
    mo2_base = _validate_mo2_path(req.mo2_path)
    if req.skyrim_data_path:
        _validate_skyrim_data_path(req.skyrim_data_path)
    mod_name = _sanitize_name(req.mod_name)
    mod_dir = mo2_base / mod_name
    if not mod_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directorio del mod no encontrado en MO2")

    job_id = str(uuid.uuid4())
    upload_dir = Path(f"output/jobs/{job_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 1. Search for real Skyrim .esp, .esm, .esl plugins first
    esp_files = sorted(mod_dir.glob("*.esp")) + sorted(mod_dir.glob("*.esm")) + sorted(mod_dir.glob("*.esl"))

    # 2. Search for candidate JSON files, excluding generated DSD output to avoid re-translation loops
    candidate_jsons = [
        p for p in mod_dir.glob("**/*.json")
        if "SKSE" not in p.parts and "DSD" not in p.parts
    ]
    json_files = sorted(set(candidate_jsons))

    plugin_file_name = mod_name
    target_plugin_filename = None
    if esp_files:
        # Native ESP plugin found: prioritize binary parsing for authentic game data
        target_file = esp_files[0]
        plugin_file_name = target_file.stem
        target_plugin_filename = target_file.name
        file_path = upload_dir / target_file.name
        shutil.copy(target_file, file_path)
    elif json_files:
        target_file = json_files[0]
        file_path = upload_dir / target_file.name
        shutil.copy(target_file, file_path)
    else:
        # Fallback template
        file_path = upload_dir / f"{mod_name}.json"
        mock_data = [
            {"FormID": "0001234A", "Text": f"Welcome to {mod_name} in Skyrim.", "is_dialog": True, "actor": "Guard", "voice_type": "MaleNord"},
            {"FormID": "0001234B", "Text": f"Greetings traveler, looking for adventure?", "is_dialog": True, "actor": "Merchant", "voice_type": "FemaleCommander"},
            {"FormID": "0001234C", "Text": f"{mod_name} Questline", "is_dialog": False}
        ]
        file_path.write_text(json.dumps(mock_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Never persist the API key in the job config dict
    cfg = req.model_dump()
    cfg.pop("api_key", None)
    jobs[job_id] = {
        "status": "pending",
        "file_path": str(file_path),
        "plugin_name": plugin_file_name,
        "target_plugin_filename": target_plugin_filename,
        "config": cfg,
        # Transient: consumed and removed by the websocket handler
        "api_key": req.api_key,
        "mo2_path": str(mo2_base),
        "mod_name": mod_name,
        "progress": 0,
        "logs": [],
        "output_dir": str(upload_dir / "build")
    }
    return {"job_id": job_id, "plugin_name": plugin_file_name}


@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """Streams real-time progress and logs to the Skyrim Web UI."""
    await websocket.accept()
    if job_id not in jobs:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return

    job = jobs[job_id]
    current_status = job.get("status", "pending")

    if current_status == "processing":
        await websocket.send_json({
            "status": "error",
            "error_code": "JOB_ALREADY_PROCESSING",
            "error": "El trabajo ya se encuentra en procesamiento.",
            "progress": job.get("progress", 0),
            "job_id": job_id,
        })
        await websocket.close()
        return

    if current_status == "completed":
        await websocket.send_json({
            "status": "completed",
            "progress": 100,
            "download_url": f"/api/download/{job_id}",
            "job_id": job_id,
            "has_mo2": bool(job.get("mo2_path") and job.get("mod_name")),
        })
        await websocket.close()
        return

    if current_status == "error":
        await websocket.send_json({
            "status": "error",
            "error_code": job.get("error_code", "INTERNAL_ERROR"),
            "error": job.get("error", "Error desconocido"),
            "progress": 100,
            "job_id": job_id,
        })
        await websocket.close()
        return

    job["status"] = "processing"
    cfg = job.get("config", {})
    target_lang = cfg.get("target_lang", "Spanish")
    generate_voice = cfg.get("generate_voice", True)
    default_voice = cfg.get("voice", "es-ES-AlvaroNeural")
    auto_inject = cfg.get("auto_inject", True)
    # Transient key: read once, then removed from the job record
    api_key = job.pop("api_key", None) or cfg.pop("api_key", None)
    api_base = cfg.get("api_base", "https://api.openai.com/v1")
    model = cfg.get("model", "gpt-4o-mini")

    async def log_msg(msg: str, progress: int = None, level: str = "info"):
        job["logs"].append({"text": msg, "level": level})
        if progress is not None:
            job["progress"] = progress
        await websocket.send_json({
            "log": msg,
            "progress": job["progress"],
            "level": level,
            "status": job["status"]
        })

    async def fail_with_code(error_code: str, human_msg: str):
        job["status"] = "error"
        job["error"] = human_msg
        job["error_code"] = error_code
        job["logs"].append({"text": f"❌ [{error_code}] {human_msg}", "level": "error"})
        await websocket.send_json({
            "status": "error",
            "error_code": error_code,
            "error": human_msg,
            "log": f"❌ [{error_code}] {human_msg}",
            "level": "error",
            "progress": 100,
            "job_id": job_id
        })

    try:
        await log_msg(f"⚔️ Iniciando pipeline para '{job['plugin_name']}'...", 5, "info")

        file_p = Path(job["file_path"])
        is_plugin_source = file_p.suffix.lower() in [".esp", ".esm", ".esl"]
        if is_plugin_source:
            await log_msg(f"📜 Extrayendo cadenas binarias directamente de '{file_p.name}'...", 15, "info")
            master_search_paths = []
            if job.get("mo2_path") and job.get("mod_name"):
                source_mod_dir = Path(job["mo2_path"]) / job["mod_name"]
                if source_mod_dir.is_dir():
                    master_search_paths.append(source_mod_dir)

            skyrim_data_str = cfg.get("skyrim_data_path")
            if skyrim_data_str:
                data_dir = Path(skyrim_data_str)
                if data_dir.is_dir():
                    master_search_paths.append(data_dir)
                else:
                    logger.warning("Configured skyrim_data_path is not a valid directory: %s", skyrim_data_str)

            entries = await asyncio.to_thread(
                parse_esp_file,
                file_p,
                master_search_paths=master_search_paths or None
            )
        else:
            await log_msg(f"📖 Leyendo pergamino JSON '{file_p.name}'...", 15, "info")
            entries = parse_strings_file(file_p)

        if not entries:
            error_code = "NO_TRANSLATABLE_CONTENT"
            human_msg = f"No se encontraron textos o diálogos traducibles en '{file_p.name}'."
            job["status"] = "error"
            job["error"] = human_msg
            job["error_code"] = error_code
            job["logs"].append({"text": f"❌ [{error_code}] {human_msg}", "level": "error"})
            await websocket.send_json({
                "status": "error",
                "error_code": error_code,
                "error": human_msg,
                "log": f"❌ [{error_code}] {human_msg}",
                "level": "error",
                "progress": 100,
                "job_id": job_id
            })
            return

        await log_msg(f"✅ {len(entries)} textos y diálogos extraídos con éxito.", 25, "success")

        # 1.5 DSD preflight (plugin sources only): fail fast on incomplete
        # metadata or types DSD 1.4.3 cannot represent, BEFORE spending LLM/TTS.
        if is_plugin_source:
            try:
                validate_dsd_entries(entries)
            except DSDExportError as err:
                await fail_with_code(err.code, f"Validación DSD fallida: {err}")
                return

        # 2. Translation with Fail-Fast Contract
        await log_msg(f"🌐 Traduciendo al {target_lang}...", 35, "translate")
        if api_key:
            translator_fn = create_openai_compatible_translator(api_key, api_base, model, target_lang=target_lang)
            await log_msg(f"🧠 Conectado a LLM ({model})...", 40, "info")
        else:
            translator_fn = free_translator_callable
            await log_msg("⚡ Usando Traductor Neuronal Gratuito...", 40, "info")

        translated_entries = await translate_entries(
            entries,
            target_lang=target_lang,
            api_callable=translator_fn
        )
        await log_msg("✅ Traducción completada con éxito.", 60, "success")

        # 3. Audio generation with Smart VoiceType Mapping
        build_dir = Path(job["output_dir"])
        build_dir.mkdir(parents=True, exist_ok=True)

        dialog_entries = [e for e in translated_entries if e.is_dialog]
        success_voice_count = 0
        total_dialogs = len(dialog_entries)

        if generate_voice and dialog_entries:
            unresolved = [e for e in dialog_entries if not e.voice_type]
            if unresolved:
                unresolved_count = len(unresolved)
                sample_ids = ", ".join(f"0x{e.form_id}" for e in unresolved[:5])
                if unresolved_count > 5:
                    sample_ids += f", ... (+{unresolved_count - 5} más)"
                error_code = "UNRESOLVED_VOICE_TYPES"
                human_msg = (
                    f"{unresolved_count}/{total_dialogs} diálogos carecen de VoiceType resuelto "
                    f"(FormIDs: {sample_ids}). Proporcione 'skyrim_data_path' con los masters necesarios o desactive "
                    f"la generación de voces."
                )
                job["status"] = "error"
                job["error"] = human_msg
                job["error_code"] = error_code
                job["logs"].append({"text": f"❌ [{error_code}] {human_msg}", "level": "error"})
                await websocket.send_json({
                    "status": "error",
                    "error_code": error_code,
                    "error": human_msg,
                    "log": f"❌ [{error_code}] {human_msg}",
                    "level": "error",
                    "progress": 100,
                    "job_id": job_id
                })
                return

            await log_msg(f"🎙️ Generando voces neuronales ({total_dialogs} diálogos)...", 65, "audio")
            # Real plugin filename when known; legacy JSON jobs keep the old
            # plugin_name-based folder since no plugin can be demonstrated.
            voice_dir_name = job.get("target_plugin_filename") or f"{job['plugin_name']}.esp"
            voice_base_dir = build_dir / "Sound" / "Voice" / voice_dir_name
            voice_base_dir.mkdir(parents=True, exist_ok=True)

            completed_count = 0
            tts_semaphore = asyncio.Semaphore(5)
            progress_lock = asyncio.Lock()
            log_every = max(1, total_dialogs // 5)

            async def _gen_voice(entry):
                nonlocal success_voice_count, completed_count
                assigned_voice = resolve_voice_for_entry(entry.voice_type, default_fallback=default_voice)
                async with tts_semaphore:
                    ok = await generate_voice_file(
                        entry,
                        str(voice_base_dir),
                        voice=assigned_voice,
                        tts_class=edge_tts.Communicate
                    )
                async with progress_lock:
                    if ok:
                        success_voice_count += 1
                    completed_count += 1
                    curr_progress = 65 + int(completed_count / total_dialogs * 20)
                    if completed_count % log_every == 0 or completed_count == total_dialogs:
                        voice_label = assigned_voice.split("-")[2] if assigned_voice.count("-") >= 2 else assigned_voice
                        await log_msg(f"🔊 [{voice_label}] Diálogo {completed_count}/{total_dialogs} generado...", curr_progress, "audio")

            await asyncio.gather(*[_gen_voice(entry) for entry in dialog_entries])

            if success_voice_count == total_dialogs:
                await log_msg(f"✅ {success_voice_count}/{total_dialogs} archivos de voz neuronal organizados por VoiceType.", 85, "success")
            else:
                await log_msg(f"⚠️ {success_voice_count}/{total_dialogs} archivos de voz generados ({total_dialogs - success_voice_count} fallaron).", 85, "error")
        else:
            await log_msg("⏩ Generación de audio omitida.", 85, "info")

        # 4. Export DSD JSON (official Dynamic String Distributor 1.4.3 layout).
        # Legacy JSON input carries no DSD metadata: the export is skipped
        # explicitly, never fabricated, and never reported as success.
        if is_plugin_source and job.get("target_plugin_filename"):
            await log_msg("📦 Forjando diccionario Dynamic String Distributor (SKSE DSD)...", 90, "dsd")
            try:
                dsd_dir = (
                    build_dir / "SKSE" / "Plugins" / "DynamicStringDistributor"
                    / job["target_plugin_filename"]
                )
                export_to_dsd(translated_entries, dsd_dir / "SkyrimAITranslator.json")
            except DSDExportError as err:
                await fail_with_code(err.code, f"Fallo exportando DSD: {err}")
                return
            await log_msg("✅ DSD listo en SKSE/Plugins/DynamicStringDistributor.", 92, "success")
        else:
            await log_msg(
                "⚠️ Export DSD omitido: el input JSON legacy no provee metadata DSD "
                "(form_id|plugin, type, index). No se fabrica metadata.",
                90, "warning"
            )

        # 5. Auto-inject directly to MO2 if requested
        if auto_inject and job.get("mo2_path") and job.get("mod_name"):
            target_mod_dir = Path(job["mo2_path"]) / job["mod_name"]
            if target_mod_dir.is_dir():
                await log_msg(f"🚀 Auto-inyectando directamente en '{job['mod_name']}'...", 95, "success")
                async with _get_mod_lock(job["mod_name"]):
                    await asyncio.to_thread(_copy_build_to_dir, build_dir, target_mod_dir)
                await log_msg("✅ ¡Mod inyectado automáticamente! Listo para jugar en Skyrim.", 98, "success")

        # 6. Build ZIP bundle
        zip_path = Path(f"output/jobs/{job_id}/{job['plugin_name']}_Spanish_Translation.zip")
        await asyncio.to_thread(_zip_dir, build_dir, zip_path)

        job["zip_path"] = str(zip_path)
        job["status"] = "completed"
        if generate_voice and dialog_entries and success_voice_count < total_dialogs:
            final_msg = f"🎉 ¡Traducción completada con éxito! ({success_voice_count}/{total_dialogs} audios doblados)."
        else:
            final_msg = "🎉 ¡Ritual completado! Tu mod de Skyrim está 100% traducido y doblado."

        await log_msg(final_msg, 100, "success")
        await websocket.send_json({
            "status": "completed",
            "download_url": f"/api/download/{job_id}",
            "job_id": job_id,
            "has_mo2": bool(job.get("mo2_path") and job.get("mod_name"))
        })

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        logger.exception("Error crítico en pipeline de traducción para %s: %s", job_id, e)
        await websocket.send_json({
            "status": "error",
            "error": str(e),
            "log": f"❌ ERROR CRÍTICO: {str(e)}",
            "level": "error",
            "progress": 100,
            "job_id": job_id
        })

    await websocket.close()


@app.get("/api/download/{job_id}")
async def download_result(job_id: str):
    """Downloads the complete compiled Skyrim Mod ZIP bundle."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    zip_path = Path(job.get("zip_path", ""))
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="El archivo ZIP no está listo")

    return FileResponse(
        zip_path,
        filename=zip_path.name,
        media_type="application/zip"
    )


@app.post("/api/mo2/inject/{job_id}")
async def inject_to_mo2(job_id: str, req: InjectRequest):
    """Directly copies the generated translation files into the Mod Organizer 2 mod directory."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    build_dir = Path(job.get("output_dir", ""))
    if not build_dir.exists():
        raise HTTPException(status_code=400, detail="No hay archivos generados para inyectar")

    mo2_base = _validate_mo2_path(req.mo2_path)
    mod_name = _sanitize_name(req.mod_name)
    target_mod_dir = mo2_base / mod_name
    if not target_mod_dir.is_dir():
        raise HTTPException(status_code=404, detail="Carpeta del mod en MO2 no encontrada")

    try:
        async with _get_mod_lock(mod_name):
            await asyncio.to_thread(_copy_build_to_dir, build_dir, target_mod_dir)
        return {
            "success": True,
            "message": f"¡Traducción inyectada con éxito en {target_mod_dir}!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inyectando en MO2: {str(e)}") from e
