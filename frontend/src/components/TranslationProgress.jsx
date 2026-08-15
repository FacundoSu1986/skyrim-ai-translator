function StatusGlyph({ status }) {
  if (status === 'completed') return <span className="status-glyph success" aria-label="Completado">✓</span>;
  if (status === 'error') return <span className="status-glyph error" aria-label="Error">!</span>;
  return <span className="status-glyph" aria-label="Procesando">ᚨ</span>;
}

export function TranslationProgress({ status, progress, jobId }) {
  const progressLabel =
    status === 'completed'
      ? 'TRADUCCIÓN COMPLETADA'
      : status === 'error'
        ? 'RITUAL INTERRUMPIDO'
        : 'FORJANDO TRADUCCIÓN...';

  const footerText =
    status === 'completed'
      ? 'Los archivos finales están listos para ser utilizados.'
      : status === 'error'
        ? 'Revisa el registro del ritual para identificar el fallo.'
        : 'Procesando archivos y forjando voces neurales. No cierres la aplicación.';

  return (
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
        aria-label="Progreso de traducción"
      >
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        >
          <span className="progress-shimmer" aria-hidden="true" />
        </div>
      </div>

      <div className="progress-footer">
        <div>
          <span className="mini-rune" aria-hidden="true">ᛟ</span>
          <span>{footerText}</span>
        </div>

        <span className="job-id">
          {jobId ? `JOB ${jobId}` : 'PREPARANDO RITUAL'}
        </span>
      </div>
    </div>
  );
}

export default TranslationProgress;
