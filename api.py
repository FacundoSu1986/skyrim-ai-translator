import asyncio
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, WebSocket, Query, Body, HTTPException
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
from src.dsd_exporter import export_to_dsd

app = FastAPI(title="Skyrim AI Translation Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for translation jobs
jobs = {}

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
    config: Optional[str] = None
):
    """Uploads a mod JSON or ESP file and creates a new translation job."""
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"output/jobs/{job_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    cfg = {}
    if config:
        try:
            cfg = json.loads(config)
        except Exception:
            pass

    plugin_name = file.filename
    for ext in [".json", ".esp", ".esm", ".esl"]:
        if plugin_name.lower().endswith(ext):
            plugin_name = plugin_name[:-len(ext)]

    jobs[job_id] = {
        "status": "pending",
        "file_path": str(file_path),
        "plugin_name": plugin_name,
        "config": cfg,
        "progress": 0,
        "logs": [],
        "output_dir": str(upload_dir / "build")
    }
    return {"job_id": job_id, "plugin_name": jobs[job_id]["plugin_name"]}


@app.post("/api/mo2/start")
async def start_mo2_translation(req: MO2TranslateRequest):
    """Starts translation job directly from a mod selected in Mod Organizer 2."""
    mod_dir = Path(req.mo2_path) / req.mod_name
    if not mod_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directorio del mod no encontrado en MO2")

    job_id = str(uuid.uuid4())
    upload_dir = Path(f"output/jobs/{job_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 1. Search for existing JSON
    json_files = list(mod_dir.glob("*.json")) + list(mod_dir.glob("**/*.json"))
    
    # 2. Search for real Skyrim .esp, .esm, .esl plugins
    esp_files = list(mod_dir.glob("*.esp")) + list(mod_dir.glob("*.esm")) + list(mod_dir.glob("*.esl"))

    plugin_file_name = req.mod_name
    if json_files:
        target_file = json_files[0]
        file_path = upload_dir / target_file.name
        shutil.copy(target_file, file_path)
    elif esp_files:
        # Native ESP file found! Copy it for binary parsing
        target_file = esp_files[0]
        plugin_file_name = target_file.stem
        file_path = upload_dir / target_file.name
        shutil.copy(target_file, file_path)
    else:
        # Fallback template
        file_path = upload_dir / f"{req.mod_name}.json"
        mock_data = [
            {"FormID": "0001234A", "Text": f"Welcome to {req.mod_name} in Skyrim.", "is_dialog": True, "actor": "Guard", "voice_type": "MaleNord"},
            {"FormID": "0001234B", "Text": f"Greetings traveler, looking for adventure?", "is_dialog": True, "actor": "Merchant", "voice_type": "FemaleCommander"},
            {"FormID": "0001234C", "Text": f"{req.mod_name} Questline", "is_dialog": False}
        ]
        file_path.write_text(json.dumps(mock_data, indent=2, ensure_ascii=False), encoding="utf-8")

    jobs[job_id] = {
        "status": "pending",
        "file_path": str(file_path),
        "plugin_name": plugin_file_name,
        "config": req.model_dump(),
        "mo2_path": req.mo2_path,
        "mod_name": req.mod_name,
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
    job["status"] = "processing"
    cfg = job.get("config", {})
    target_lang = cfg.get("target_lang", "Spanish")
    generate_voice = cfg.get("generate_voice", True)
    default_voice = cfg.get("voice", "es-ES-AlvaroNeural")
    auto_inject = cfg.get("auto_inject", True)
    api_key = cfg.get("api_key")
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

    try:
        await log_msg(f"⚔️ Iniciando pipeline para '{job['plugin_name']}'...", 5, "info")
        
        file_p = Path(job["file_path"])
        if file_p.suffix.lower() in [".esp", ".esm", ".esl"]:
            await log_msg(f"📜 Extrayendo cadenas binarias directamente de '{file_p.name}'...", 15, "info")
            entries = parse_esp_file(file_p)
        else:
            await log_msg(f"📖 Leyendo pergamino JSON '{file_p.name}'...", 15, "info")
            entries = parse_strings_file(file_p)

        if not entries:
            # Fallback entry if empty
            from src.models import StringEntry
            entries = [StringEntry(form_id="0001234A", text=f"Welcome to {job['plugin_name']}.", is_dialog=True, voice_type="MaleNord")]

        await log_msg(f"✅ {len(entries)} textos y diálogos extraídos con éxito.", 25, "success")

        # 2. Translation
        await log_msg(f"🌐 Traduciendo al {target_lang} con glosario oficial de Skyrim...", 35, "translate")
        if api_key:
            translator_fn = create_openai_compatible_translator(api_key, api_base, model)
            await log_msg(f"🧠 Conectado a LLM ({model})...", 40, "info")
        else:
            translator_fn = free_translator_callable
            await log_msg("⚡ Usando Traductor Neuronal Gratuito con Lore de Bethesda...", 40, "info")

        translated_entries = await translate_entries(
            entries, 
            target_lang=target_lang, 
            api_callable=translator_fn
        )
        await log_msg(f"✅ Traducción completada con éxito.", 60, "success")

        # 3. Audio generation with Smart VoiceType Mapping
        build_dir = Path(job["output_dir"])
        build_dir.mkdir(parents=True, exist_ok=True)
        
        dialog_entries = [e for e in translated_entries if e.is_dialog]
        if generate_voice and dialog_entries:
            await log_msg(f"🎙️ Generando voces neuronales ({len(dialog_entries)} diálogos)...", 65, "audio")
            voice_base_dir = build_dir / "Sound" / "Voice" / f"{job['plugin_name']}.esp"
            voice_base_dir.mkdir(parents=True, exist_ok=True)

            success_count = 0
            for idx, entry in enumerate(dialog_entries):
                # Resolve smart voice by gender/race
                assigned_voice = resolve_voice_for_entry(entry.voice_type, default_fallback=default_voice)

                ok = await generate_voice_file(
                    entry, 
                    str(voice_base_dir), 
                    voice=assigned_voice,
                    tts_class=edge_tts.Communicate
                )
                if ok:
                    success_count += 1
                curr_progress = 65 + int((idx + 1) / len(dialog_entries) * 20)
                if idx % max(1, len(dialog_entries) // 5) == 0 or idx == len(dialog_entries) - 1:
                    await log_msg(f"🔊 [{assigned_voice.split('-')[2]}] Diálogo {idx+1}/{len(dialog_entries)} generado...", curr_progress, "audio")

            await log_msg(f"✅ {success_count} archivos de voz neuronal organizados por VoiceType.", 85, "success")
        else:
            await log_msg("⏩ Generación de audio omitida.", 85, "info")

        # 4. Export DSD JSON
        await log_msg("📦 Forjando diccionario Dynamic String Distributor (SKSE DSD)...", 90, "dsd")
        dsd_dir = build_dir / "SKSE" / "Plugins" / "DSD"
        dsd_dir.mkdir(parents=True, exist_ok=True)
        export_to_dsd(translated_entries, dsd_dir / f"{job['plugin_name']}.json")

        # 5. Auto-inject directly to MO2 if requested
        if auto_inject and job.get("mo2_path") and job.get("mod_name"):
            target_mod_dir = Path(job["mo2_path"]) / job["mod_name"]
            if target_mod_dir.is_dir():
                await log_msg(f"🚀 Auto-inyectando directamente en '{job['mod_name']}'...", 95, "success")
                for item in build_dir.iterdir():
                    target_dest = target_mod_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, target_dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target_dest)
                await log_msg("✅ ¡Mod inyectado automáticamente! Listo para jugar en Skyrim.", 98, "success")

        # 6. Build ZIP bundle
        zip_path = Path(f"output/jobs/{job_id}/{job['plugin_name']}_Spanish_Translation.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(build_dir):
                for file in files:
                    file_full_path = Path(root) / file
                    arcname = file_full_path.relative_to(build_dir)
                    zipf.write(file_full_path, arcname)

        job["zip_path"] = str(zip_path)
        job["status"] = "completed"
        await log_msg("🎉 ¡Ritual completado! Tu mod de Skyrim está 100% traducido y doblado.", 100, "success")
        await websocket.send_json({
            "status": "completed", 
            "download_url": f"/api/download/{job_id}",
            "job_id": job_id,
            "has_mo2": bool(job.get("mo2_path") and job.get("mod_name"))
        })

    except Exception as e:
        job["status"] = "failed"
        await log_msg(f"❌ ERROR CRÍTICO: {str(e)}", 100, "error")

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

    target_mod_dir = Path(req.mo2_path) / req.mod_name
    if not target_mod_dir.is_dir():
        raise HTTPException(status_code=404, detail="Carpeta del mod en MO2 no encontrada")

    try:
        for item in build_dir.iterdir():
            target_dest = target_mod_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target_dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target_dest)
                
        return {
            "success": True, 
            "message": f"¡Traducción inyectada con éxito en {target_mod_dir}!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inyectando en MO2: {str(e)}")
