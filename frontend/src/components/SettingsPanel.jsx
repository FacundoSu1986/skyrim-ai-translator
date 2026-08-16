export function SettingsPanel({
  showSettings,
  onToggleSettings,
  targetLang,
  onTargetLangChange,
  skyrimDataPath,
  onSkyrimDataPathChange,
  generateVoice,
  onGenerateVoiceChange,
  voices = [],
  selectedVoice,
  onSelectedVoiceChange,
  aiProvider,
  onAiProviderChange,
  apiKey,
  onApiKeyChange,
  isBusy = false,
}) {
  return (
    <section className={`settings-section ${showSettings ? 'open' : ''}`}>
      <button
        type="button"
        className="settings-toggle"
        onClick={onToggleSettings}
        aria-expanded={showSettings}
        aria-controls="settings-panel-content"
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
        <div id="settings-panel-content" className="settings-panel nordic-panel">
          <div className="settings-grid">
            <div className="input-group">
              <label htmlFor="language-select">Idioma Destino</label>
              <div className="field-shell">
                <span className="field-icon" aria-hidden="true">◎</span>
                <select
                  id="language-select"
                  className="select-input"
                  value={targetLang}
                  onChange={(event) => onTargetLangChange(event.target.value)}
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
              <label htmlFor="skyrim-data-path">Ruta Skyrim Data (Masters)</label>
              <div className="field-shell">
                <span className="field-icon" aria-hidden="true">⛁</span>
                <input
                  id="skyrim-data-path"
                  type="text"
                  className="text-input"
                  value={skyrimDataPath || ''}
                  onChange={(event) => onSkyrimDataPathChange(event.target.value)}
                  placeholder="Ej: E:\SteamLibrary\steamapps\common\Skyrim Special Edition\Data"
                  disabled={isBusy}
                />
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
                  onChange={(event) => onSelectedVoiceChange(event.target.value)}
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
                className="visually-hidden"
                checked={generateVoice}
                onChange={(event) => onGenerateVoiceChange(event.target.checked)}
                disabled={isBusy}
              />
              <span className="custom-check" aria-hidden="true" />
              <span>
                <strong>Generar archivos de voz</strong>
                <small>.mp3 para diálogos</small>
              </span>
            </label>

            <div className="provider-group">
              <span className="field-label" id="ai-provider-label">Proveedor de IA</span>

              <div className="provider-options" role="radiogroup" aria-labelledby="ai-provider-label">
                <label className="radio-option">
                  <input
                    type="radio"
                    className="visually-hidden"
                    name="aiProvider"
                    value="fast"
                    checked={aiProvider === 'fast'}
                    onChange={() => onAiProviderChange('fast')}
                    disabled={isBusy}
                  />
                  <span className="radio-ui" aria-hidden="true" />
                  <span>
                    <strong>Modo Rápido</strong>
                    <small>Local</small>
                  </span>
                </label>

                <label className="radio-option">
                  <input
                    type="radio"
                    className="visually-hidden"
                    name="aiProvider"
                    value="openai"
                    checked={aiProvider === 'openai'}
                    onChange={() => onAiProviderChange('openai')}
                    disabled={isBusy}
                  />
                  <span className="radio-ui" aria-hidden="true" />
                  <span>
                    <strong>OpenAI</strong>
                    <small>gpt-4o-mini</small>
                  </span>
                </label>

                <label className="radio-option">
                  <input
                    type="radio"
                    className="visually-hidden"
                    name="aiProvider"
                    value="deepseek"
                    checked={aiProvider === 'deepseek'}
                    onChange={() => onAiProviderChange('deepseek')}
                    disabled={isBusy}
                  />
                  <span className="radio-ui" aria-hidden="true" />
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
                  onChange={(event) => onApiKeyChange(event.target.value)}
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
  );
}

export default SettingsPanel;
