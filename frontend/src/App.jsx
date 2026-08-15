import { useEffect, useRef, useState } from 'react';

const API_ORIGIN = 'http://localhost:8000';
const WS_ORIGIN = 'ws://localhost:8000';

function DragonSigil() {
  return (
    <svg
      className="dragon-sigil"
      viewBox="0 0 180 180"
      role="img"
      aria-label="Emblema de dragón nórdico"
    >
      <defs>
        <linearGradient id="dragonMetal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#eef4f8" />
          <stop offset="35%" stopColor="#81909a" />
          <stop offset="70%" stopColor="#d8b86a" />
          <stop offset="100%" stopColor="#4d5962" />
        </linearGradient>
        <radialGradient id="dragonGlow">
          <stop offset="0%" stopColor="#74d7ff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#74d7ff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle className="sigil-ring-outer" cx="90" cy="90" r="78" />
      <circle className="sigil-ring-inner" cx="90" cy="90" r="66" />
      <circle cx="90" cy="136" r="29" fill="url(#dragonGlow)" opacity="0.34" />

      <g className="sigil-runes" aria-hidden="true">
        <path d="M90 17v12M54 27l7 10M126 27l-7 10M28 54l10 7M152 54l-10 7M17 90h12M151 90h12M28 126l10-7M152 126l-10-7M54 152l7-10M126 152l-7-10" />
      </g>

      <path
        fill="url(#dragonMetal)"
        d="M118 38c-9 3-17 8-23 15-9-7-21-10-34-7 7 4 13 9 17 16-10 1-19 6-25 14 10-2 18-1 25 4-14 7-22 19-25 35 9-9 18-14 29-14-12 11-16 24-12 40 4-10 11-18 20-24 1 11-2 22-8 32 14-6 24-16 30-31 5-13 5-26 1-38 8-8 13-18 15-30-7 6-14 10-22 11 7-7 11-15 12-23Zm-28 29c11-8 22-10 34-6-7 2-13 6-18 11 5 2 10 6 13 11-11-3-21-1-30 5 2-8 2-15 1-21Z"
      />
      <path
        className="sigil-eye"
        d="M103 67l7 2-5 5-6-2 4-5Z"
      />
      <path
        className="sigil-tail"
        d="M91 102c-17 5-27 16-31 33 12-8 23-10 34-7-6 4-10 10-13 18 16-6 27-17 33-32"
      />
      <path className="sigil-rune-mark" d="M82 145l8-13 8 13-8 13-8-13Z" />
    </svg>
  );
}

function RuneDivider() {
  return (
    <div className="rune-divider" aria-hidden="true">
      <span className="rune-line" />
      <span className="rune-diamond">◇</span>
      <span className="rune-knot">ᛟ</span>
      <span className="rune-diamond">◇</span>
      <span className="rune-line" />
    </div>
  );
}

function StatusGlyph({ status }) {
  if (status === 'completed') return <span className="status-glyph success">✓</span>;
  if (status === 'error') return <span className="status-glyph error">!</span>;
  return <span className="status-glyph">ᚨ</span>;
}

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
    if (!jobId || !mo2Path || !selectedMod || injectStatus === 'injecting') {
      return;
    }

    setInjectStatus('injecting');

    try {
      const res = await fetch(`${API_ORIGIN}/api/mo2/inject/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mo2_path: mo2Path,
          mod_name: selectedMod,
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
    setDownloadUrl(null);
    setInjectStatus(null);
  };

  const progressLabel =
    status === 'completed'
      ? 'TRADUCCIÓN COMPLETADA'
      : status === 'error'
        ? 'RITUAL INTERRUMPIDO'
        : 'FORJANDO TRADUCCIÓN...';

  const activeModName =
    activeTab === 'mo2'
      ? selectedMod || 'Ningún mod seleccionado'
      : file?.name || 'Ningún JSON seleccionado';

  return (
    <main className="page-shell">
      <div className="ambient ambient-left" aria-hidden="true" />
      <div className="ambient ambient-right" aria-hidden="true" />

      <section className="skyrim-frame">
        <div className="frame-line frame-line-top" aria-hidden="true" />
        <div className="frame-line frame-line-bottom" aria-hidden="true" />

        <span className="corner-ornament corner-tl" aria-hidden="true">ᛟ</span>
        <span className="corner-ornament corner-tr" aria-hidden="true">ᛟ</span>
        <span className="corner-ornament corner-bl" aria-hidden="true">ᛟ</span>
        <span className="corner-ornament corner-br" aria-hidden="true">ᛟ</span>

        <div className="app-container">
          <header className="hero">
            <div className="emblem-column">
              <DragonSigil />
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

          <nav className="tabs-container" aria-label="Modo de entrada">
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
                    <label htmlFor="mod-select">Seleccionar Mod para Traducir</label>

                    {modsList.length > 0 ? (
                      <div className="field-shell">
                        <span className="field-icon sword-icon" aria-hidden="true">
                          ⚔
                        </span>
                        <select
                          id="mod-select"
                          className="select-input select-skyrim"
                          value={selectedMod}
                          onChange={(event) => setSelectedMod(event.target.value)}
                          disabled={isBusy}
                        >
                          {modsList.map((mod) => (
                            <option key={mod} value={mod}>
                              {mod}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : (
                      <div className="hint-box">
                        No se encontraron mods. Introduce la ruta de MO2 y usa
                        <strong> ESCANEAR</strong>.
                      </div>
                    )}
                  </div>

                  <label className="toggle-card">
                    <input
                      type="checkbox"
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

          <section className={`settings-section ${showSettings ? 'open' : ''}`}>
            <button
              type="button"
              className="settings-toggle"
              onClick={() => setShowSettings((value) => !value)}
              aria-expanded={showSettings}
            >
              <span className="settings-title">
                <span className="gear-mark" aria-hidden="true">⚙</span>
                AJUSTES DE IDIOMA, VOCES E IA
              </span>
              <span className="settings-chevron" aria-hidden="true">
                {showSettings ? '⌃' : '⌄'}
              </span>
            </button>

            {showSettings && (
              <div className="settings-panel nordic-panel">
                <div className="settings-grid">
                  <div className="input-group">
                    <label htmlFor="language-select">Idioma Destino</label>
                    <div className="field-shell">
                      <span className="field-icon" aria-hidden="true">◎</span>
                      <select
                        id="language-select"
                        className="select-input"
                        value={targetLang}
                        onChange={(event) => setTargetLang(event.target.value)}
                        disabled={isBusy}
                      >
                        <option value="Spanish">Español (España Oficial)</option>
                        <option value="Spanish (Latin America)">
                          Español (Latinoamérica)
                        </option>
                        <option value="French">Francés</option>
                        <option value="German">Alemán</option>
                        <option value="Italian">Italiano</option>
                      </select>
                    </div>
                  </div>

                  <div className="input-group">
                    <label htmlFor="voice-select">Voz Neuronal (Edge-TTS)</label>
                    <div className="field-shell">
                      <span className="field-icon" aria-hidden="true">♬</span>
                      <select
                        id="voice-select"
                        className="select-input"
                        value={selectedVoice}
                        onChange={(event) =>
                          setSelectedVoice(event.target.value)
                        }
                        disabled={!generateVoice || isBusy}
                      >
                        {voices.map((voice) => (
                          <option key={voice.id} value={voice.id}>
                            {voice.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <label className="voice-toggle">
                    <input
                      type="checkbox"
                      checked={generateVoice}
                      onChange={(event) =>
                        setGenerateVoice(event.target.checked)
                      }
                      disabled={isBusy}
                    />
                    <span className="custom-check" aria-hidden="true" />
                    <span>
                      <strong>Generar archivos de voz</strong>
                      <small>.mp3 para diálogos</small>
                    </span>
                  </label>

                  <div className="provider-group">
                    <span className="field-label">Proveedor de IA</span>

                    <div className="provider-options">
                      <label className="radio-option">
                        <input
                          type="radio"
                          name="aiProvider"
                          value="fast"
                          checked={aiProvider === 'fast'}
                          onChange={() => setAiProvider('fast')}
                          disabled={isBusy}
                        />
                        <span className="radio-ui" />
                        <span>
                          <strong>Modo Rápido</strong>
                          <small>Local</small>
                        </span>
                      </label>

                      <label className="radio-option">
                        <input
                          type="radio"
                          name="aiProvider"
                          value="openai"
                          checked={aiProvider === 'openai'}
                          onChange={() => setAiProvider('openai')}
                          disabled={isBusy}
                        />
                        <span className="radio-ui" />
                        <span>
                          <strong>OpenAI</strong>
                          <small>gpt-4o-mini</small>
                        </span>
                      </label>

                      <label className="radio-option">
                        <input
                          type="radio"
                          name="aiProvider"
                          value="deepseek"
                          checked={aiProvider === 'deepseek'}
                          onChange={() => setAiProvider('deepseek')}
                          disabled={isBusy}
                        />
                        <span className="radio-ui" />
                        <span>
                          <strong>DeepSeek</strong>
                          <small>deepseek-chat</small>
                        </span>
                      </label>
                    </div>
                  </div>

                  <div className="input-group api-group">
                    <label htmlFor="api-key">Clave API</label>
                    <div className="field-shell">
                      <span className="field-icon" aria-hidden="true">⌁</span>
                      <input
                        id="api-key"
                        type="password"
                        className="text-input"
                        value={apiKey}
                        onChange={(event) =>
                          handleApiKeyChange(event.target.value)
                        }
                        placeholder={
                          aiProvider === 'fast'
                            ? 'No requerida en modo local'
                            : 'sk-...'
                        }
                        disabled={aiProvider === 'fast' || isBusy}
                        autoComplete="off"
                      />
                    </div>
                    <small className="security-note">
                      La persistencia actual usa localStorage para conservar el
                      comportamiento original.
                    </small>
                  </div>
                </div>
              </div>
            )}
          </section>

          {status !== 'idle' && (
            <section className="ritual-grid">
              <div className="progress-panel nordic-panel">
                <div className="progress-heading">
                  <div>
                    <span className="section-overline">ESTADO DEL PROCESO</span>
                    <h2>{progressLabel}</h2>
                  </div>

                  <div className="progress-number">
                    <StatusGlyph status={status} />
                    <span>{progress}%</span>
                  </div>
                </div>

                <div
                  className={`progress-track ${status}`}
                  role="progressbar"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="progress-fill"
                    style={{ width: `${progress}%` }}
                  >
                    <span className="progress-shimmer" />
                  </div>
                </div>

                <div className="progress-footer">
                  <div>
                    <span className="mini-rune" aria-hidden="true">ᛟ</span>
                    <span>
                      {status === 'completed'
                        ? 'Los archivos finales están listos.'
                        : status === 'error'
                          ? 'Revisa el registro del ritual para identificar el fallo.'
                          : 'Procesando archivos y generando recursos. No cierres el motor.'}
                    </span>
                  </div>

                  <span className="job-id">
                    {jobId ? `JOB ${jobId}` : 'PREPARANDO JOB'}
                  </span>
                </div>
              </div>

              <div className="log-panel nordic-panel">
                <div className="log-header">
                  <span aria-hidden="true">ᛃ</span>
                  <strong>REGISTRO DEL RITUAL</strong>
                  <span aria-hidden="true">ᛃ</span>
                </div>

                <div className="skyrim-terminal" aria-live="polite">
                  {logs.length === 0 ? (
                    <div className="log-placeholder">
                      Esperando mensajes del motor...
                    </div>
                  ) : (
                    logs.map((log, index) => (
                      <div
                        key={`${log.time}-${index}`}
                        className={`log-entry ${log.level}`}
                      >
                        <span className="log-time">[{log.time}]</span>
                        <span className="log-marker" aria-hidden="true">
                          {log.level === 'error'
                            ? '!'
                            : log.level === 'success'
                              ? '✓'
                              : log.level === 'audio'
                                ? '♫'
                                : log.level === 'translate'
                                  ? 'ᚱ'
                                  : '›'}
                        </span>
                        <span className="log-text">{log.text}</span>
                      </div>
                    ))
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>
            </section>
          )}

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

          {status === 'error' && (
            <button
              type="button"
              className="btn-secondary retry-button"
              onClick={resetAll}
            >
              VOLVER A INTENTAR
            </button>
          )}

          <footer className="footer-motto">
            <span>ᚨ</span>
            <p>LAS PALABRAS ANTIGUAS, AHORA EN TU IDIOMA</p>
            <span>ᚱ</span>
          </footer>
        </div>
      </section>
    </main>
  );
}

export default App;
