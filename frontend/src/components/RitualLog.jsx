export function RitualLog({ logs = [], logEndRef }) {
  const getLogMarker = (level) => {
    switch (level) {
      case 'error':
        return '!';
      case 'success':
        return '✓';
      case 'audio':
        return '♫';
      case 'translate':
        return 'ᚱ';
      default:
        return '›';
    }
  };

  return (
    <div className="log-panel nordic-panel">
      <div className="log-header">
        <span aria-hidden="true">ᛃ</span>
        <strong>REGISTRO DEL RITUAL</strong>
        <span aria-hidden="true">ᛃ</span>
      </div>

      <div className="skyrim-terminal" aria-live="polite" role="log">
        {logs.length === 0 ? (
          <div className="log-placeholder">
            Esperando mensajes del motor de traducción...
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={`${log.time}-${index}`}
              className={`log-entry ${log.level || 'info'}`}
            >
              <span className="log-time">[{log.time}]</span>
              <span className="log-marker" aria-hidden="true">
                {getLogMarker(log.level)}
              </span>
              <span className="log-text">{log.text}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}

export default RitualLog;
