import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function App() {
  // Navigation & Tab States
  const [activeTab, setActiveTab] = useState('generate'); // 'generate' | 'history'
  
  // Form Input States
  const [brief, setBrief] = useState('');
  const [selectedPlatforms, setSelectedPlatforms] = useState(['instagram']);
  const [selectedPersonas, setSelectedPersonas] = useState(['professional']);
  const [variantsCount, setVariantsCount] = useState(1);

  // Data States
  const [history, setHistory] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [activeJobStatus, setActiveJobStatus] = useState(null);
  const [activeJobLogs, setActiveJobLogs] = useState([]);
  const [copySuccess, setCopySuccess] = useState('');

  // Active copy variant view index
  const [activeVariantIndex, setActiveVariantIndex] = useState(0);

  // References for polling and auto-scroll
  const pollingRef = useRef(null);
  const logsEndRef = useRef(null);

  // Fetch campaign history from MongoDB Atlas
  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/history?limit=15`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
    return () => stopPolling();
  }, []);

  // Scroll logs to bottom automatically
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeJobLogs]);

  // Start polling status for a running task
  const startPolling = (jobId) => {
    stopPolling();
    setActiveJobId(jobId);
    setActiveJobStatus('PENDING');
    setActiveJobLogs([{ status: 'PENDING', message: 'Job submitted and queued in Celery.', timestamp: new Date().toISOString() }]);

    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${jobId}`);
        if (!res.ok) throw new Error('Status fetch failed');
        const data = await res.json();

        // Update active job status and logs
        setActiveJobStatus(data.status);
        setActiveJobLogs(data.progress_log || []);

        if (data.status === 'SUCCESS') {
          stopPolling();
          setSelectedJob(data);
          fetchHistory(); // Refresh the list
        } else if (data.status === 'FAILED') {
          stopPolling();
          setSelectedJob(data);
          fetchHistory();
        }
      } catch (err) {
        console.error('Error polling job status:', err);
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  // Submit ad generation request to FastAPI
  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!brief || brief.trim().length < 3) {
      alert('Brief must be at least 3 characters long.');
      return;
    }
    if (selectedPlatforms.length === 0) {
      alert('Select at least one social media platform.');
      return;
    }
    if (selectedPersonas.length === 0) {
      alert('Select at least one brand voice persona.');
      return;
    }

    try {
      const payload = {
        brief,
        platforms: selectedPlatforms,
        personas: selectedPersonas,
        variants_count: parseInt(variantsCount, 10),
      };

      const res = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = await res.json();
      setSelectedJob(null); // Clear selected pane
      setActiveVariantIndex(0);
      startPolling(data.job_id);
    } catch (err) {
      alert(`Submission failed: ${err.message}`);
    }
  };

  // Toggle platform selection helper
  const handlePlatformToggle = (platform) => {
    if (selectedPlatforms.includes(platform)) {
      setSelectedPlatforms(selectedPlatforms.filter((p) => p !== platform));
    } else {
      setSelectedPlatforms([...selectedPlatforms, platform]);
    }
  };

  // Toggle persona selection helper
  const handlePersonaToggle = (persona) => {
    if (selectedPersonas.includes(persona)) {
      setSelectedPersonas(selectedPersonas.filter((p) => p !== persona));
    } else {
      setSelectedPersonas([...selectedPersonas, persona]);
    }
  };

  // Copy variant text to clipboard
  const handleCopyClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopySuccess(id);
    setTimeout(() => setCopySuccess(''), 2000);
  };

  // Select a past job to preview
  const handleSelectHistory = async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/status/${jobId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedJob(data);
        setActiveJobId(null);
        setActiveJobStatus(null);
        setActiveJobLogs([]);
        setActiveVariantIndex(0);
      }
    } catch (err) {
      console.error('Failed to retrieve historical job:', err);
    }
  };

  return (
    <div id="root">
      {/* Primary Navigation Header */}
      <header>
        <div className="brand-ascii">
          {`__   _____ ___    _   _    ___ ___ _  _     _   ___ \n\\ \\ / /_ _| _ \\  /_\\ | |  / __| __| \\| |   /_\\ |_ _|\n \\ V / | ||   / / _ \\| |_| (_ | _|| .\` |  / _ \\ | | \n  \\_/ |___|_|_\\/_/ \\_\\____\\___|___|_|\\_| /_/ \\_\\___|`}
        </div>
      </header>

      {/* Main Split Pane Layout */}
      <div className="main-layout">
        
        {/* Left Side: Forms / Active progress / History */}
        <div className="input-panel">
          {/* Tab Switcher */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--color-hairline-strong)', marginBottom: '16px' }}>
            <button
              className="btn"
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                color: activeTab === 'generate' ? 'var(--color-ink)' : 'var(--color-mute)',
                borderBottom: activeTab === 'generate' ? '2px solid var(--color-ink)' : 'none',
                borderRadius: 0,
                fontWeight: activeTab === 'generate' ? '700' : '400',
              }}
              onClick={() => setActiveTab('generate')}
            >
              [+] GENERATOR
            </button>
            <button
              className="btn"
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                color: activeTab === 'history' ? 'var(--color-ink)' : 'var(--color-mute)',
                borderBottom: activeTab === 'history' ? '2px solid var(--color-ink)' : 'none',
                borderRadius: 0,
                fontWeight: activeTab === 'history' ? '700' : '400',
              }}
              onClick={() => setActiveTab('history')}
            >
              [-] HISTORY ({history.length})
            </button>
          </div>

          {activeTab === 'generate' ? (
            <>
              {/* Form Input Card */}
              <div className="tui-card">
                <div className="tui-card-header">
                  <span>INPUT_BRIEF_FORM</span>
                  <span style={{ color: 'var(--color-mute)' }}>V1.0</span>
                </div>
                <div className="tui-card-body">
                  <form onSubmit={handleGenerate}>
                    <div className="form-group">
                      <label className="form-label">AD BRIEF / CONCEPT</label>
                      <textarea
                        className="form-control"
                        placeholder="e.g. A sleek modern smart watch for fitness enthusiasts..."
                        value={brief}
                        onChange={(e) => setBrief(e.target.value)}
                        required
                        disabled={activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">TARGET PLATFORMS</label>
                      <div className="checkbox-group">
                        {['instagram', 'linkedin', 'facebook', 'twitter'].map((platform) => (
                          <label key={platform} className="checkbox-label">
                            <input
                              type="checkbox"
                              checked={selectedPlatforms.includes(platform)}
                              onChange={() => handlePlatformToggle(platform)}
                              disabled={activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                            />
                            <div className="checkbox-box"></div>
                            <span style={{ textTransform: 'capitalize' }}>{platform}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">BRAND PERSONAS</label>
                      <div className="checkbox-group">
                        {['professional', 'witty', 'urgent'].map((persona) => (
                          <label key={persona} className="checkbox-label">
                            <input
                              type="checkbox"
                              checked={selectedPersonas.includes(persona)}
                              onChange={() => handlePersonaToggle(persona)}
                              disabled={activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                            />
                            <div className="checkbox-box"></div>
                            <span style={{ textTransform: 'capitalize' }}>{persona}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">VARIANTS PER PERSONA</label>
                      <input
                        type="number"
                        className="form-control"
                        min="1"
                        max="5"
                        value={variantsCount}
                        onChange={(e) => setVariantsCount(e.target.value)}
                        required
                        disabled={activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                      />
                    </div>

                    <button
                      type="submit"
                      className="btn btn-primary"
                      style={{ width: '100%', marginTop: '8px' }}
                      disabled={activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                    >
                      {activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'
                        ? 'QUEUED IN CELERY...'
                        : 'GENERATE CAMPAIGN →'}
                    </button>
                  </form>
                </div>
              </div>

              {/* Active Logs Console Card */}
              {activeJobStatus && (
                <div className="tui-card">
                  <div className="tui-card-header">
                    <span>CELERY_QUEUE_LOGS</span>
                    <span className={`badge badge-${activeJobStatus.toLowerCase()}`}>
                      {activeJobStatus}
                    </span>
                  </div>
                  <div className="tui-card-body" style={{ padding: '12px' }}>
                    <div className="log-box">
                      {activeJobLogs.map((log, i) => (
                        <div key={i} className="log-entry">
                          <span className="log-time">
                            [{new Date(log.timestamp).toLocaleTimeString()}]
                          </span>
                          <span
                            className={`log-text ${
                              log.status === 'FAILED'
                                ? 'failed'
                                : log.status === 'SUCCESS'
                                ? 'success'
                                : ''
                            }`}
                          >
                            {log.message}
                          </span>
                        </div>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            /* History Gallery Panel */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {history.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-mute)' }}>
                  No historical campaigns found in database.
                </div>
              ) : (
                history.map((job) => (
                  <div
                    key={job.job_id}
                    className={`history-item ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`}
                    onClick={() => handleSelectHistory(job.job_id)}
                  >
                    <div className="history-header">
                      <span>{job.job_id.substring(0, 8)}...</span>
                      <span className={`badge badge-${job.status.toLowerCase()}`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="history-brief">{job.refined_prompt || job.error || 'No prompt refined'}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Right Side: Output visual previews and copy copies */}
        <div className="output-panel">
          {!selectedJob ? (
            /* Empty TUI Mockup landing card */
            <div className="tui-dark-mockup" style={{ margin: 'auto', maxWidth: '640px', width: '100%' }}>
              <div className="ascii-art">
                {`██╗   ██╗██╗██████╗  █████╗ ██╗      ██████╗ ███████╗███╗   ██╗
██║   ██║██║██╔══██╗██╔══██╗██║     ██╔════╝ ██╔════╝████╗  ██║
██║   ██║██║██████╔╝███████║██║     ██║  ███╗█████╗  ██╔██╗ ██║
╚██╗ ██╔╝██║██╔══██╗██╔══██║██║     ██║   ██║██╔══╝  ██║╚██╗██║
 ╚████╔╝ ██║██║  ██║██║  ██║███████╗╚██████╔╝███████╗██║ ╚████║
  ╚═══╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝`}
              </div>
              <div className="tui-prompt-row">
                <span style={{ color: 'var(--color-success)' }}>$</span> viralgenai --init-system
              </div>
              <div style={{ textAlign: 'left', marginTop: '16px', color: 'var(--color-mute)' }}>
                <div className="list-row"><span className="list-bullet">[+]</span> <span>API endpoint: http://localhost:8000</span></div>
                <div className="list-row"><span className="list-bullet">[+]</span> <span>MongoDB Atlas cluster online</span></div>
                <div className="list-row"><span className="list-bullet">[+]</span> <span>Celery worker active & listening</span></div>
                <div className="list-row"><span className="list-bullet">[+]</span> <span>Cloudinary storage active</span></div>
              </div>
              <div style={{ marginTop: '24px', fontSize: '11px', color: 'var(--color-ash)' }}>
                Enter a brief on the left panel and click Generate to start the campaign asset pipeline.
              </div>
            </div>
          ) : (
            /* Detailed Campaign output preview view */
            <>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <h1>CAMPAIGN ASSETS</h1>
                  <span className={`badge badge-${selectedJob.status.toLowerCase()}`}>
                    {selectedJob.status}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--color-mute)' }}>
                  Job ID: {selectedJob.job_id}
                </div>
              </div>

              {selectedJob.status === 'FAILED' ? (
                <div
                  style={{
                    border: '1px solid var(--color-danger)',
                    backgroundColor: 'rgba(255, 59, 48, 0.05)',
                    padding: '16px',
                    color: 'var(--color-danger)',
                    fontSize: '13px',
                  }}
                >
                  <strong>Pipeline Execution Failed:</strong>
                  <p style={{ marginTop: '8px', whiteSpace: 'pre-wrap' }}>{selectedJob.error}</p>
                </div>
              ) : (
                <>
                  {/* Prompt Card */}
                  {selectedJob.refined_prompt && (
                    <div className="tui-card">
                      <div className="tui-card-header">
                        <span>REFINED_VISUAL_PROMPT</span>
                      </div>
                      <div className="tui-card-body" style={{ fontSize: '13px', fontStyle: 'italic', lineHeight: '1.6' }}>
                        "{selectedJob.refined_prompt}"
                      </div>
                    </div>
                  )}

                  {/* Split Preview: Image and copy */}
                  <div className="preview-layout">
                    {/* Left: Image Box */}
                    <div>
                      <h2 style={{ fontSize: '14px', color: 'var(--color-mute)', textTransform: 'uppercase' }}>
                        Generated Visual
                      </h2>
                      <div className="image-container">
                        {selectedJob.image_url ? (
                          <a href={selectedJob.image_url} target="_blank" rel="noopener noreferrer">
                            <img src={selectedJob.image_url} alt="Generated Campaign Visual" />
                          </a>
                        ) : (
                          <div className="image-placeholder">
                            [-] Image url missing or generation skipped.
                          </div>
                        )}
                      </div>
                      {selectedJob.image_url && (
                        <div style={{ marginTop: '8px', textAlign: 'right' }}>
                          <a href={selectedJob.image_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '12px' }}>
                            [+] View Full Size Image
                          </a>
                        </div>
                      )}
                    </div>

                    {/* Right: Text Copy Variants */}
                    <div>
                      <h2 style={{ fontSize: '14px', color: 'var(--color-mute)', textTransform: 'uppercase' }}>
                        Ad Copy Variants ({selectedJob.variants?.length || 0})
                      </h2>
                      {(!selectedJob.variants || selectedJob.variants.length === 0) ? (
                        <div style={{ border: '1px solid var(--color-hairline)', padding: '24px', color: 'var(--color-mute)', fontSize: '13px' }}>
                          [-] No copy text variants returned.
                        </div>
                      ) : (
                        <div className="copy-variants">
                          {/* Tabs for each variant */}
                          <div style={{ display: 'flex', overflowX: 'auto', borderBottom: '1px solid var(--color-hairline)', gap: '4px' }}>
                            {selectedJob.variants.map((v, i) => (
                              <button
                                key={i}
                                className="btn"
                                style={{
                                  backgroundColor: activeVariantIndex === i ? 'var(--color-surface-card)' : 'transparent',
                                  border: 'none',
                                  borderRadius: 0,
                                  fontSize: '11px',
                                  padding: '4px 10px',
                                  height: '28px',
                                  color: activeVariantIndex === i ? 'var(--color-ink)' : 'var(--color-mute)',
                                  fontWeight: activeVariantIndex === i ? '700' : '400',
                                  whiteSpace: 'nowrap',
                                }}
                                onClick={() => setActiveVariantIndex(i)}
                              >
                                {v.platform.toUpperCase()} ({v.persona})
                              </button>
                            ))}
                          </div>

                          {/* Selected Variant Display Card */}
                          {selectedJob.variants[activeVariantIndex] && (
                            <div className="variant-card">
                              <div className="variant-header">
                                <span>
                                  {selectedJob.variants[activeVariantIndex].platform.toUpperCase()} ·{' '}
                                  {selectedJob.variants[activeVariantIndex].persona.toUpperCase()}
                                </span>
                                <span>
                                  {selectedJob.variants[activeVariantIndex].char_count} chars
                                </span>
                              </div>
                              <div className="variant-body">
                                {selectedJob.variants[activeVariantIndex].copy_text}
                              </div>
                              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
                                <button
                                  className="btn btn-secondary"
                                  style={{ height: '28px', fontSize: '12px', padding: '0 12px' }}
                                  onClick={() =>
                                    handleCopyClipboard(
                                      selectedJob.variants[activeVariantIndex].copy_text,
                                      `v-${activeVariantIndex}`
                                    )
                                  }
                                >
                                  {copySuccess === `v-${activeVariantIndex}` ? '[x] Copied!' : '[+] Copy Text'}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Telemetry data box */}
                  {selectedJob.telemetry && (
                    <div
                      style={{
                        marginTop: '16px',
                        padding: '12px',
                        border: '1px dashed var(--color-hairline)',
                        fontSize: '12px',
                        color: 'var(--color-mute)',
                      }}
                    >
                      <strong>Telemetry Data:</strong>{' '}
                      LLM: <code>{selectedJob.telemetry.model}</code> ({selectedJob.telemetry.llm_provider}) |{' '}
                      Duration: <code>{(selectedJob.telemetry.total_duration_ms / 1000).toFixed(2)}s</code> |{' '}
                      Created: <code>{new Date(selectedJob.telemetry.created_at).toLocaleString()}</code>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer copyright section */}
      <footer>
        <span>©2026 ViralGen AI Terminal</span>
        <span>Made with IBM Plex Mono & JetBrains Mono</span>
      </footer>
    </div>
  );
}
