import { useEffect, useRef, useState } from 'react';
import DragonMedallion from './components/DragonMedallion';
import RuneDivider from './components/RuneDivider';
import ModSelector from './components/ModSelector';
import SettingsPanel from './components/SettingsPanel';
import TranslationProgress from './components/TranslationProgress';
import RitualLog from './components/RitualLog';
import nordicCornerSvg from './assets/skyrim-ui/nordic-corner.svg';

const API_ORIGIN = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_ORIGIN = (import.meta.env.VITE_API_URL || 'ws://localhost:8000').replace(
  /^http/,
  'ws',
);

function App() {
  const [activeTab, setActiveTab] = useState('mo2'); // 'mo2' | 'manual'

  const [mo2Path, setMo2Path] = useState(
    localStorage.getItem('skyrim_mo2_path') || '',
  );
  const [modsList, setModsList] = useState([]);
  const [selectedMod, setSelectedMod] = useState('');
  const [scanningMods, setScanningMods] = useState(false);
  const [autoDetected, setAutoDetected] = useState(false);

  // Manual file
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);

  // Settings
  const [targetLang, setTargetLang] = useState('Spanish');
  const [generateVoice, setGenerateVoice] = useState(true);
  const [autoInject, setAutoInject] = useState(true);
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('es-ES-AlvaroNeural');
  const [aiProvider, setAiProvider] = useState('fast');
  const [apiKey, setApiKey] = useState(
    localStorage.getItem('skyrim_ai_key') || '',
  );
  const [showSettings, setShowSettings] = useState(true);

  // Processing / WebSocket
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle'); // idle | processing | completed | error
  const [jobId, setJobId] = useState(null);
  // Mod name locked to the current job so later injects target the right mod
  // even if the user changes the select while the job runs.
  const [jobModName, setJobModName] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [injectStatus, setInjectStatus] = useState(null);

  const logEndRef = useRef(null);
  const wsRef = useRef(null);
  const isBusy = status === 'processing';

  useEffect(() => {
    fetch(`${API_ORIGIN}/api/voices`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data.voices) && data.voices.length > 0) {
          setVoices(data.voices);
          setSelectedVoice(data.voices[0].id);
        }
      })
      .catch(() => {
        setVoices([
          {
            id: 'es-ES-AlvaroNeural',
            name: 'Álvaro (Español España)',
          },
        ]);
      });

    fetch(`${API_ORIGIN}/api/mo2/auto-detect`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data.found && Array.isArray(data.mods) && data.mods.length > 0) {
          setMo2Path(data.path || '');
          setModsList(data.mods);
          setSelectedMod(data.mods[0]);
          setAutoDetected(true);
        }
      })
      .catch(() => {});

    return () => {
      wsRef.current?.close();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [logs]);

  const appendLog = (text, level = 'info') => {
    setLogs((prev) => [
      ...prev,
      {
        text,
        level,
        time: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const handleMo2PathChange = (value) => {
    setMo2Path(value);
    localStorage.setItem('skyrim_mo2_path', value);
    setAutoDetected(false);
  };

  const handleApiKeyChange = (value) => {
    setApiKey(value);
    localStorage.setItem('skyrim_ai_key', value);
  };

  const scanMo2Mods = async (pathOverride) => {
    const target = pathOverride || mo2Path;
    if (!target.trim() || scanningMods || isBusy) return;

    setScanningMods(true);

    try {
      const res = await fetch(
        `${API_ORIGIN}/api/mo2/mods?path=${encodeURIComponent(target.trim())}`,
      );

      if (!res.ok) {
        throw new Error(`No se pudo escanear MO2 (HTTP ${res.status})`);
      }

      const data = await res.json();

      if (Array.isArray(data.mods) && data.mods.length > 0) {
        setModsList(data.mods);
        setSelectedMod(data.mods[0]);
      } else {
        setModsList([]);
        setSelectedMod('');
      }
    } catch (err) {
      console.error(err);
      appendLog(err instanceof Error ? err.message : 'Error al escanear MO2', 'error');
    } finally {
      setScanningMods(false);
    }
  };

  const onDragOver = (event) => {
    event.preventDefault();
    if (!isBusy) setIsDragging(true);
  };

  const onDragLeave = () => setIsDragging(false);

  const onDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    if (isBusy) return;

    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) setFile(droppedFile);
  };

  const onFileSelect = (event) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) setFile(selectedFile);
  };

  const buildAiConfig = () => ({
    api_key: aiProvider !== 'fast' ? apiKey : null,
    api_base:
      aiProvider === 'deepseek'
        ? 'https://api.deepseek.com/v1'
        : 'https://api.openai.com/v1',
    model: aiProvider === 'deepseek' ? 'deepseek-chat' : 'gpt-4o-mini',
  });

  const connectWebSocket = (id) => {
    wsRef.current?.close();

    const ws = new WebSocket(`${WS_ORIGIN}/ws/progress/${id}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.log) {
          appendLog(data.log, data.level || 'info');
        }

        if (typeof data.progress === 'number') {
          setProgress(Math.max(0, Math.min(100, data.progress)));
        }

        if (data.status === 'completed') {
          setStatus('completed');
          setProgress(100);
          setDownloadUrl(
            data.download_url ? `${API_ORIGIN}${data.download_url}` : null,
          );
          ws.close();
        }

        if (data.status === 'error') {
          setStatus('error');
          appendLog(data.error || 'El trabajo finalizó con error.', 'error');
          ws.close();
        }
      } catch (err) {
        console.error('WebSocket payload inválido:', err);
        setStatus('error');
        appendLog('Respuesta inválida recibida desde el servidor.', 'error');
      }
    };

    ws.onerror = () => {
      setStatus('error');
      appendLog(
        'Error de conexión con el santuario de Skyrim (WebSocket).',
        'error',
      );
    };
  };

  const startManualTranslation = async () => {
    if (!file || isBusy) return;

    setStatus('processing');
    setProgress(5);
    setDownloadUrl(null);
    setInjectStatus(null);
    setLogs([
      {
        text: 'Subiendo pergamino JSON al motor...',
        level: 'info',
        time: new Date().toLocaleTimeString(),
      },
    ]);

    const config = {
      target_lang: targetLang,
      generate_voice: generateVoice,
      voice: selectedVoice,
      ...buildAiConfig(),
    };

    const formData = new FormData();
    formData.append('file', file);
    formData.append('config', JSON.stringify(config));

    try {
      const res = await fetch(`${API_ORIGIN}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Error al subir archivo (HTTP ${res.status})`);
      }

      const data = await res.json();

      if (!data.job_id) {
        throw new Error('El backend no devolvió job_id.');
      }

      setJobId(data.job_id);
      connectWebSocket(data.job_id);
    } catch (err) {
      setStatus('error');
      appendLog(err instanceof Error ? err.message : 'Error desconocido', 'error');
    }
  };

  const startMo2Translation = async () => {
    if (!selectedMod || !mo2Path.trim() || isBusy) return;

    setStatus('processing');
    setProgress(5);
    setDownloadUrl(null);
    setInjectStatus(null);
    setLogs([
      {
        text: `Iniciando ritual de traducción para '${selectedMod}'...`,
        level: 'info',
        time: new Date().toLocaleTimeString(),
      },
    ]);

    const payload = {
      mo2_path: mo2Path.trim(),
      mod_name: selectedMod,
      target_lang: targetLang,
      generate_voice: generateVoice,
      voice: selectedVoice,
      auto_inject: autoInject,
      ...buildAiConfig(),
    };
    setJobModName(selectedMod);

    try {
      const res = await fetch(`${API_ORIGIN}/api/mo2/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`Error al iniciar trabajo de MO2 (HTTP ${res.status})`);
      }

      const data = await res.json();

      if (!data.job_id) {
        throw new Error('El backend no devolvió job_id.');
      }

      setJobId(data.job_id);
      connectWebSocket(data.job_id);
    } catch (err) {
      setStatus('error');
      appendLog(err instanceof Error ? err.message : 'Error desconocido', 'error');
    }
  };

  const injectToMo2 = async () => {
    const targetMod = jobModName || selectedMod;
    if (!jobId || !mo2Path || !targetMod || injectStatus === 'injecting') {
      return;
    }

    setInjectStatus('injecting');

    try {
      const res = await fetch(`${API_ORIGIN}/api/mo2/inject/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mo2_path: mo2Path,
          mod_name: targetMod,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setInjectStatus('success');
        appendLog('Inyección finalizada correctamente en MO2.', 'success');
      } else {
        setInjectStatus('error');
        appendLog(data.error || 'La inyección en MO2 falló.', 'error');
      }
    } catch (err) {
      setInjectStatus('error');
      appendLog(
        err instanceof Error ? err.message : 'Error al inyectar en MO2.',
        'error',
      );
    }
  };

  const resetAll = () => {
    wsRef.current?.close();
    setStatus('idle');
    setFile(null);
    setProgress(0);
    setLogs([]);
    setJobId(null);
    setJobModName(null);
    setDownloadUrl(null);
    setInjectStatus(null);
  };

  const activeModName =
    activeTab === 'mo2'
      ? selectedMod || 'Ningún mod seleccionado'
      : file?.name || 'Ningún JSON seleccionado';

  return (
    <main className="page-shell">
      {/* Ambient Side Smoke / Magic Mist */}
      <div className="ambient ambient-left" aria-hidden="true" />
      <div className="ambient ambient-right" aria-hidden="true" />

      {/* Main Skyrim Artifact Frame */}
      <section className="skyrim-frame">
        <div className="frame-line frame-line-top" aria-hidden="true" />
        <div className="frame-line frame-line-bottom" aria-hidden="true" />

        {/* 4 Nordic Corner Ornaments */}
        <div className="corner-ornament corner-tl" aria-hidden="true">
          <img src={nordicCornerSvg} alt="" />
        </div>
        <div className="corner-ornament corner-tr" aria-hidden="true">
          <img src={nordicCornerSvg} alt="" />
        </div>
        <div className="corner-ornament corner-bl" aria-hidden="true">
          <img src={nordicCornerSvg} alt="" />
        </div>
        <div className="corner-ornament corner-br" aria-hidden="true">
          <img src={nordicCornerSvg} alt="" />
        </div>

        <div className="app-container">
          {/* Header Hero */}
          <header className="hero">
            <div className="emblem-column">
              <DragonMedallion />
            </div>

            <div className="title-column">
              <div className="eyebrow">NORDIC LOCALIZATION ENGINE</div>
              <h1>SKYRIM TRANSLATOR</h1>
              <p className="subtitle">
                Automatizador de localización y doblaje neural
              </p>
              <RuneDivider />
            </div>

            <div className="hero-rune" aria-hidden="true">
              <span>ᛏ</span>
              <span>ᚱ</span>
              <span>ᚨ</span>
            </div>
          </header>

          {/* Mode Navigation Tabs */}
          <nav className="tabs-container" aria-label="Modo de entrada de traducción">
            <button
              type="button"
              className={`tab-btn ${activeTab === 'mo2' ? 'active' : ''}`}
              onClick={() => setActiveTab('mo2')}
              disabled={isBusy}
            >
              <span className="tab-icon" aria-hidden="true">◈</span>
              <span>
                <small>Integración directa</small>
                MOD ORGANIZER 2
              </span>
            </button>

            <button
              type="button"
              className={`tab-btn ${activeTab === 'manual' ? 'active' : ''}`}
              onClick={() => setActiveTab('manual')}
              disabled={isBusy}
            >
              <span className="tab-icon" aria-hidden="true">⇧</span>
              <span>
                <small>Archivo externo</small>
                SUBIR JSON MANUAL
              </span>
            </button>
          </nav>

          {/* Main Workspace Panel */}
          <section className="main-panel nordic-panel">
            {activeTab === 'mo2' ? (
              <div className="mo2-layout">
                <div className="mo2-fields">
                  <div className="panel-kicker">
                    <span className={`shield-check ${autoDetected ? 'detected' : ''}`}>
                      {autoDetected ? '✓' : '◇'}
                    </span>
                    <div>
                      <strong>
                        {autoDetected
                          ? 'MO2 Detectado Automáticamente'
                          : 'Mod Organizer 2'}
                      </strong>
                      <small>
                        {autoDetected
                          ? `${modsList.length} mods disponibles`
                          : 'Selecciona tu carpeta de mods'}
                      </small>
                    </div>
                  </div>

                  <div className="input-group">
                    <label htmlFor="mo2-path">Directorio de Mods (MO2)</label>
                    <div className="input-row">
                      <div className="field-shell">
                        <span className="field-icon" aria-hidden="true">⌂</span>
                        <input
                          id="mo2-path"
                          type="text"
                          className="text-input"
                          value={mo2Path}
                          onChange={(event) =>
                            handleMo2PathChange(event.target.value)
                          }
                          placeholder="C:\ModOrganizer\mods"
                          disabled={isBusy}
                        />
                      </div>

                      <button
                        type="button"
                        className="btn-secondary scan-button"
                        onClick={() => scanMo2Mods()}
                        disabled={scanningMods || isBusy || !mo2Path.trim()}
                      >
                        <span aria-hidden="true">⌕</span>
                        {scanningMods ? 'BUSCANDO...' : 'ESCANEAR'}
                      </button>
                    </div>
                  </div>

                  <div className="input-group">
                    <label id="mod-select-label" htmlFor="mod-select-button">
                      Seleccionar Mod para Traducir
                    </label>

                    <ModSelector
                      modsList={modsList}
                      selectedMod={selectedMod}
                      onSelectMod={setSelectedMod}
                      disabled={isBusy}
                    />
                  </div>

                  <label className="toggle-card">
                    <input
                      type="checkbox"
                      className="visually-hidden"
                      checked={autoInject}
                      onChange={(event) => setAutoInject(event.target.checked)}
                      disabled={isBusy}
                    />
                    <span className="custom-check" aria-hidden="true" />
                    <span className="toggle-copy">
                      <strong>Inyección Automática</strong>
                      <small>
                        Instala voces y textos en el mod al finalizar.
                      </small>
                    </span>
                  </label>
                </div>

                <aside className="action-altar">
                  <div className="action-glyph" aria-hidden="true">ᛞ</div>

                  <div>
                    <span className="action-caption">MOD SELECCIONADO</span>
                    <strong className="action-mod-name">{activeModName}</strong>
                  </div>

                  <button
                    type="button"
                    className="primary-action"
                    onClick={startMo2Translation}
                    disabled={!selectedMod || !mo2Path.trim() || isBusy}
                  >
                    <span className="primary-action-text">
                      {isBusy ? 'TRADUCIENDO...' : 'TRADUCIR Y GENERAR VOCES'}
                    </span>
                    <span className="button-rune" aria-hidden="true">ᛟ</span>
                  </button>

                  <small className="action-note">
                    Traducción, voz y empaquetado desde un único flujo.
                  </small>
                </aside>
              </div>
            ) : (
              <div className="manual-layout">
                <div
                  className={`dropzone ${isDragging ? 'active' : ''} ${
                    file ? 'has-file' : ''
                  }`}
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onDrop={onDrop}
                  onClick={() => {
                    if (!isBusy) {
                      document.getElementById('file-upload')?.click();
                    }
                  }}
                  role="button"
                  tabIndex={isBusy ? -1 : 0}
                  onKeyDown={(event) => {
                    if (!isBusy && (event.key === 'Enter' || event.key === ' ')) {
                      document.getElementById('file-upload')?.click();
                    }
                  }}
                  aria-disabled={isBusy}
                  aria-label="Zona de carga de archivo JSON"
                >
                  <input
                    type="file"
                    id="file-upload"
                    className="visually-hidden"
                    accept=".json,application/json"
                    onChange={onFileSelect}
                    disabled={isBusy}
                  />

                  <div className="scroll-seal" aria-hidden="true">⌘</div>
                  <strong>
                    {file ? file.name : 'Deposita aquí el pergamino JSON'}
                  </strong>
                  <span>
                    {file
                      ? 'Archivo preparado para iniciar la traducción.'
                      : 'Arrastra un JSON extraído de xEdit / SSE-AT o haz clic para seleccionarlo.'}
                  </span>
                </div>

                <button
                  type="button"
                  className="primary-action manual-action"
                  onClick={startManualTranslation}
                  disabled={!file || isBusy}
                >
                  <span className="primary-action-text">
                    {isBusy ? 'TRADUCIENDO...' : 'INICIAR TRADUCCIÓN'}
                  </span>
                  <span className="button-rune" aria-hidden="true">ᚱ</span>
                </button>
              </div>
            )}
          </section>

          {/* Settings Section */}
          <SettingsPanel
            showSettings={showSettings}
            onToggleSettings={() => setShowSettings((prev) => !prev)}
            targetLang={targetLang}
            onTargetLangChange={setTargetLang}
            generateVoice={generateVoice}
            onGenerateVoiceChange={setGenerateVoice}
            voices={voices}
            selectedVoice={selectedVoice}
            onSelectedVoiceChange={setSelectedVoice}
            aiProvider={aiProvider}
            onAiProviderChange={setAiProvider}
            apiKey={apiKey}
            onApiKeyChange={handleApiKeyChange}
            isBusy={isBusy}
          />

          {/* Ritual In-Progress / Output Grid */}
          {status !== 'idle' && (
            <section className="ritual-grid">
              <TranslationProgress
                status={status}
                progress={progress}
                jobId={jobId}
              />
              <RitualLog logs={logs} logEndRef={logEndRef} />
            </section>
          )}

          {/* Final Action Bar when Completed */}
          {status === 'completed' && (
            <section className="final-actions nordic-panel">
              {downloadUrl && (
                <a
                  href={downloadUrl}
                  download
                  className="download-link"
                >
                  <span aria-hidden="true">⬇</span>
                  DESCARGAR MOD EMPAQUETADO (.ZIP)
                </a>
              )}

              {activeTab === 'mo2' && selectedMod && !autoInject && (
                <button
                  type="button"
                  className="btn-secondary final-button"
                  onClick={injectToMo2}
                  disabled={
                    injectStatus === 'injecting' ||
                    injectStatus === 'success'
                  }
                >
                  {injectStatus === 'injecting'
                    ? 'INYECTANDO...'
                    : injectStatus === 'success'
                      ? 'INYECCIÓN EXITOSA EN MO2'
                      : injectStatus === 'error'
                        ? 'REINTENTAR INYECCIÓN EN MO2'
                        : 'INYECTAR DIRECTAMENTE EN MO2'}
                </button>
              )}

              <button
                type="button"
                className="btn-secondary final-button"
                onClick={resetAll}
              >
                TRADUCIR OTRO MOD
              </button>
            </section>
          )}

          {/* Error Retry Bar */}
          {status === 'error' && (
            <button
              type="button"
              className="btn-secondary retry-button"
              onClick={resetAll}
            >
              VOLVER A INTENTAR
            </button>
          )}

          {/* Footer Motto */}
          <footer className="footer-motto">
            <span aria-hidden="true">ᚨ</span>
            <p>LAS PALABRAS ANTIGUAS, AHORA EN TU IDIOMA</p>
            <span aria-hidden="true">ᚱ</span>
          </footer>
        </div>
      </section>
    </main>
  );
}

export default App;
