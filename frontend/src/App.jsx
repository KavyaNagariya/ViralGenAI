import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';

function TurnVariants({ turn }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [copySuccess, setCopySuccess] = useState('');

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopySuccess('copied');
    setTimeout(() => setCopySuccess(''), 2000);
  };

  const selectedVariant = turn.variants?.[activeIdx];

  return (
    <div className="copy-variants">
      {/* Tabs for each variant */}
      <div style={{ display: 'flex', overflowX: 'auto', borderBottom: '1px solid var(--color-hairline)', gap: '4px' }}>
        {turn.variants?.map((v, i) => (
          <button
            key={i}
            className="btn"
            style={{
              backgroundColor: activeIdx === i ? 'var(--color-surface-card)' : 'transparent',
              border: 'none',
              borderRadius: 0,
              fontSize: '11px',
              padding: '4px 10px',
              height: '28px',
              color: activeIdx === i ? 'var(--color-ink)' : 'var(--color-mute)',
              fontWeight: activeIdx === i ? '700' : '400',
              whiteSpace: 'nowrap',
            }}
            onClick={() => setActiveIdx(i)}
          >
            {v.platform.toUpperCase()} ({v.persona})
          </button>
        ))}
      </div>

      {/* Selected Variant Display Card */}
      {selectedVariant && (
        <div className="variant-card">
          <div className="variant-header">
            <span>
              {selectedVariant.platform.toUpperCase()} ·{' '}
              {selectedVariant.persona.toUpperCase()}
            </span>
            <span>
              {selectedVariant.char_count} chars
            </span>
          </div>
          <div className="variant-body">
            {selectedVariant.copy_text}
          </div>
          <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn btn-secondary"
              style={{ height: '28px', fontSize: '12px', padding: '0 12px' }}
              onClick={() => handleCopy(selectedVariant.copy_text)}
            >
              {copySuccess === 'copied' ? '[x] Copied!' : '[+] Copy Text'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

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
  const [runningPrompt, setRunningPrompt] = useState('');
  const chatEndRef = useRef(null);

  // Active copy variant view index
  const [activeVariantIndex, setActiveVariantIndex] = useState(0);

  // Toggle state for the slide-out history drawer
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);

  // Delete a campaign from the database
  const handleDeleteCampaign = async (e, jobId) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this campaign? This action cannot be undone.')) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/status/${jobId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setHistory(prev => prev.filter(job => job.job_id !== jobId));
        if (selectedJob?.job_id === jobId) {
          setSelectedJob(null);
        }
        alert('Campaign deleted successfully.');
      } else {
        alert('Failed to delete campaign.');
      }
    } catch (err) {
      console.error('Error deleting campaign:', err);
      alert('Error connecting to backend.');
    }
  };

  // Flush Upstash Redis database cache
  const handleClearRedisCache = async () => {
    if (!confirm('Are you sure you want to clear the Redis cache? This will flush all Celery broker queues and cached assets.')) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/redis/clear`, {
        method: 'POST',
      });
      if (res.ok) {
        alert('Redis cache cleared successfully!');
      } else {
        const text = await res.text();
        alert(`Failed to clear cache: ${text}`);
      }
    } catch (err) {
      console.error('Error flushing Redis:', err);
      alert('Error connecting to backend.');
    }
  };

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

  // Scroll chat/logs to bottom automatically
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [selectedJob?.turns, activeJobLogs, activeJobStatus]);

  // Synchronize configuration parameters when a campaign is selected
  useEffect(() => {
    if (selectedJob) {
      const platforms = selectedJob.input?.platforms || [];
      const personas = selectedJob.input?.personas || [];
      const variants_count = selectedJob.input?.variants_count || 1;
      
      setSelectedPlatforms(platforms);
      setSelectedPersonas(personas);
      setVariantsCount(variants_count);
    }
  }, [selectedJob]);

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

  // Submit ad generation request to FastAPI (handles new campaign or refinement)
  const handleGenerate = async (e) => {
    if (e) e.preventDefault();
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

      if (selectedJob) {
        payload.job_id = selectedJob.job_id;
      }

      setRunningPrompt(brief);
      setBrief('');

      const res = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = await res.json();
      if (!selectedJob) {
        setSelectedJob(null); // Clear selected pane if brand new campaign
      }
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
        setRunningPrompt('');
      }
    } catch (err) {
      console.error('Failed to retrieve historical job:', err);
    }
  };
  return (
    <div id="root">
      {/* Drawer Backdrop */}
      {showHistoryDrawer && (
        <div className="drawer-backdrop" onClick={() => setShowHistoryDrawer(false)} />
      )}

      {/* History Slide-Out Drawer */}
      <div className={`history-drawer ${showHistoryDrawer ? 'open' : ''}`}>
        <div className="drawer-header">
          <span>CAMPAIGN HISTORY</span>
          <button className="btn" onClick={() => setShowHistoryDrawer(false)} style={{ border: 'none', background: 'transparent', fontSize: '16px', cursor: 'pointer', padding: 0 }}>
            [x]
          </button>
        </div>
        <div className="drawer-body">
          <button
            className="btn btn-primary"
            style={{ width: '100%', marginBottom: '16px', height: '32px', fontSize: '12px' }}
            onClick={() => {
              setSelectedJob(null);
              setActiveJobId(null);
              setActiveJobStatus(null);
              setActiveJobLogs([]);
              setBrief('');
              setShowHistoryDrawer(false);
            }}
          >
            [+] NEW CAMPAIGN
          </button>
          
          {history.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--color-mute)', fontSize: '12px' }}>
              No past campaigns found.
            </div>
          ) : (
            history.map((job) => (
              <div
                key={job.job_id}
                className={`drawer-history-item ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`}
                onClick={() => {
                  handleSelectHistory(job.job_id);
                  setShowHistoryDrawer(false);
                }}
              >
                <div className="drawer-item-info">
                  <div className="drawer-item-title">
                    {job.brief || job.input?.brief || 'No Brief Provided'}
                  </div>
                  <div className="drawer-item-meta">
                    <span>ID: {job.job_id.substring(0, 8)}</span>
                    <span className={`badge badge-${job.status ? job.status.toLowerCase() : 'pending'}`} style={{ fontSize: '8px', padding: '1px 4px' }}>
                      {job.status || 'PENDING'}
                    </span>
                  </div>
                </div>
                <button
                  className="btn-delete-history"
                  onClick={(e) => handleDeleteCampaign(e, job.job_id)}
                  title="Delete Campaign"
                >
                  ✖
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Primary Navigation Header */}
      <header>
        <div className="brand-ascii" onClick={() => {
          setSelectedJob(null);
          setActiveJobId(null);
          setActiveJobStatus(null);
          setActiveJobLogs([]);
          setBrief('');
        }} style={{ cursor: 'pointer' }}>
          {`__   _____ ___    _   _    ___ ___ _  _     _   ___ \n\\ \\ / /_ _| _ \\  /_\\ | |  / __| __| \\| |   /_\\ |_ _|\n \\ V / | ||   / / _ \\| |_| (_ | _|| .\` |  / _ \\ | | \n  \\_/ |___|_|_\\/_/ \\_\\____\\___|___|_|\\_| /_/ \\_\\___|`}
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            className="btn btn-secondary"
            onClick={() => {
              setSelectedJob(null);
              setActiveJobId(null);
              setActiveJobStatus(null);
              setActiveJobLogs([]);
              setBrief('');
            }}
            style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
          >
            [+] NEW CAMPAIGN
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => setShowHistoryDrawer(true)}
            style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
          >
            [=] HISTORY ({history.length})
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleClearRedisCache}
            style={{ height: '32px', fontSize: '12px', padding: '0 12px', borderColor: 'var(--color-danger)', color: 'var(--color-danger)' }}
          >
            [!] CLEAR CACHE
          </button>
          <button
            className="btn btn-secondary"
            onClick={toggleTheme}
            style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
          >
            {theme === 'light' ? '[-] DARK_MODE' : '[+] LIGHT_MODE'}
          </button>
        </div>
      </header>

      {/* Main Layout (Full-Width) */}
      <div className="main-layout">
        <div className="output-panel">
          {/* 1. Scrollable Chat Message Area */}
          <div className="chat-scroll-area">
            {!selectedJob && !activeJobId ? (
              /* ChatGPT / Gemini style landing interface */
              <div className="chat-landing-container">
                <h1 className="chat-landing-title">What campaign are we creating today?</h1>
                <p className="chat-landing-subtitle">
                  Enter your product brief or marketing concept, and we'll generate visual assets and social copy tailored for each platform.
                </p>

                {/* Suggestion Cards Grid */}
                <div className="suggestion-grid">
                  <div
                    className="suggestion-card"
                    onClick={() =>
                      setBrief('A sleek modern smartwatch for fitness runners, featuring real-time heart rate tracking and GPS route mapping.')
                    }
                  >
                    <span className="suggestion-icon">⌚</span>
                    <div className="suggestion-card-title">Fitness Smartwatch</div>
                    <div className="suggestion-card-desc">Sleek smart watch with heart rate tracking & GPS.</div>
                  </div>

                  <div
                    className="suggestion-card"
                    onClick={() =>
                      setBrief('Launch of organic, small-batch dark roast coffee beans sourced from sustainable family-owned farms, with rich chocolate undertones.')
                    }
                  >
                    <span className="suggestion-icon">☕</span>
                    <div className="suggestion-card-title">Organic Coffee Launch</div>
                    <div className="suggestion-card-desc">Rich dark roast beans from sustainable family farms.</div>
                  </div>

                  <div
                    className="suggestion-card"
                    onClick={() =>
                      setBrief('An AI-powered smart home security system with real-time facial recognition, night vision, and immediate mobile app alerts.')
                    }
                  >
                    <span className="suggestion-icon">🏠</span>
                    <div className="suggestion-card-title">Smart Home Security</div>
                    <div className="suggestion-card-desc">AI-powered cameras with real-time facial recognition.</div>
                  </div>

                  <div
                    className="suggestion-card"
                    onClick={() =>
                      setBrief('Premium handcrafted full-grain leather backpack designed for modern digital nomads, featuring a padded laptop compartment and water resistance.')
                    }
                  >
                    <span className="suggestion-icon">🎒</span>
                    <div className="suggestion-card-title">Leather Nomad Backpack</div>
                    <div className="suggestion-card-desc">Handcrafted leather bag with modern tech storage.</div>
                  </div>
                </div>
              </div>
            ) : (
              /* Chat Thread Container containing all turns, active logs, or errors */
              <div className="chat-thread-container">
                {/* Render all turns for the campaign */}
                {selectedJob?.turns?.map((turn, i) => (
                  <React.Fragment key={i}>
                    {/* User Message Bubble */}
                    <div className="chat-bubble-user">
                      <strong>Brief submitted:</strong>
                      <p style={{ marginTop: '8px', margin: 0, fontStyle: 'italic' }}>
                        "{turn.brief}"
                      </p>
                    </div>

                    {/* AI Response Bubble */}
                    <div className="chat-bubble-ai">
                      <div className="chat-bubble-ai-header">
                        <span>ViralGen AI Response - Version {i + 1}</span>
                      </div>

                      {/* Split Preview: Image and copy */}
                      <div className="preview-layout" style={{ width: '100%' }}>
                        {/* Left: Image Box */}
                        <div>
                          <h2 style={{ fontSize: '14px', color: 'var(--color-mute)', textTransform: 'uppercase' }}>
                            Generated Visual
                          </h2>
                          <div className="image-container">
                            {turn.image_url ? (
                              <a href={turn.image_url} target="_blank" rel="noopener noreferrer">
                                <img src={turn.image_url} alt="Generated Campaign Visual" />
                              </a>
                            ) : (
                              <div className="image-placeholder">
                                [-] Image url missing or generation skipped.
                              </div>
                            )}
                          </div>
                          {turn.image_url && (
                            <div style={{ marginTop: '8px', textAlign: 'right' }}>
                              <a href={turn.image_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '12px' }}>
                                [+] View Full Size Image
                              </a>
                            </div>
                          )}
                        </div>

                        {/* Right: Text Copy Variants */}
                        <div>
                          <h2 style={{ fontSize: '14px', color: 'var(--color-mute)', textTransform: 'uppercase' }}>
                            Ad Copy Variants ({turn.variants?.length || 0})
                          </h2>
                          {(!turn.variants || turn.variants.length === 0) ? (
                            <div style={{ border: '1px solid var(--color-hairline)', padding: '24px', color: 'var(--color-mute)', fontSize: '13px', borderRadius: '6px' }}>
                              [-] No copy text variants returned.
                            </div>
                          ) : (
                            <TurnVariants turn={turn} />
                          )}
                        </div>
                      </div>

                      {/* Telemetry data box */}
                      {turn.telemetry && (
                        <div
                          style={{
                            width: '100%',
                            padding: '12px',
                            border: '1px dashed var(--color-hairline)',
                            borderRadius: '6px',
                            fontSize: '12px',
                            color: 'var(--color-mute)',
                          }}
                        >
                          <strong>Telemetry Data:</strong>{' '}
                          LLM: <code>{turn.telemetry.model}</code> ({turn.telemetry.llm_provider}) |{' '}
                          Duration: <code>{(turn.telemetry.total_duration_ms / 1000).toFixed(2)}s</code> |{' '}
                          Created: <code>{new Date(turn.telemetry.created_at).toLocaleString()}</code>
                        </div>
                      )}
                    </div>
                  </React.Fragment>
                ))}

                {/* If the current job is generating/processing, show the running turn */}
                {activeJobId && (activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING') && (
                  <React.Fragment>
                    {/* User bubble for current running prompt */}
                    <div className="chat-bubble-user">
                      <strong>Brief submitted:</strong>
                      <p style={{ marginTop: '8px', margin: 0, fontStyle: 'italic' }}>
                        "{runningPrompt}"
                      </p>
                    </div>

                    {/* AI Bubble showing live queue logs */}
                    <div className="chat-bubble-ai">
                      <div className="chat-bubble-ai-header">
                        <span>ViralGen AI Status (Running...)</span>
                      </div>

                      <div className="tui-card" style={{ width: '100%', borderRadius: '6px', overflow: 'hidden' }}>
                        <div className="tui-card-header">
                          <span>CELERY_QUEUE_LOGS</span>
                          <span className={`badge badge-${activeJobStatus ? activeJobStatus.toLowerCase() : 'pending'}`}>
                            {activeJobStatus}
                          </span>
                        </div>
                        <div className="tui-card-body" style={{ padding: '12px' }}>
                          <div className="log-box" style={{ height: '200px' }}>
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
                          </div>
                        </div>
                      </div>
                    </div>
                  </React.Fragment>
                )}

                {/* If the campaign run failed, show execution failure box */}
                {selectedJob && selectedJob.status === 'FAILED' && (
                  <div className="chat-bubble-ai">
                    <div
                      style={{
                        border: '1px solid var(--color-danger)',
                        backgroundColor: 'rgba(255, 59, 48, 0.05)',
                        padding: '16px',
                        color: 'var(--color-danger)',
                        fontSize: '13px',
                        borderRadius: '6px',
                        width: '100%',
                      }}
                    >
                      <strong>Pipeline Execution Failed:</strong>
                      <p style={{ marginTop: '8px', whiteSpace: 'pre-wrap' }}>{selectedJob.error}</p>
                    </div>
                  </div>
                )}
                
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          {/* 2. Sticky Bottom Configuration & Input Box */}
          <div className="chat-input-sticky-container">
            {/* Campaign Inline Settings */}
            <div className="inline-config-bar">
              <div className="inline-config-row">
                <span className="inline-config-label">Platforms:</span>
                <div className="chips-container">
                  {['instagram', 'linkedin', 'facebook', 'twitter'].map((platform) => (
                    <span
                      key={platform}
                      className={`chip-pill ${selectedPlatforms.includes(platform) ? 'active' : ''}`}
                      onClick={() => handlePlatformToggle(platform)}
                    >
                      {platform.toUpperCase()}
                    </span>
                  ))}
                </div>
              </div>

              <div className="inline-config-row">
                <span className="inline-config-label">Personas:</span>
                <div className="chips-container">
                  {['professional', 'witty', 'urgent'].map((persona) => (
                    <span
                      key={persona}
                      className={`chip-pill ${selectedPersonas.includes(persona) ? 'active' : ''}`}
                      onClick={() => handlePersonaToggle(persona)}
                    >
                      {persona.toUpperCase()}
                    </span>
                  ))}
                </div>
              </div>

              <div className="inline-config-row">
                <span className="inline-config-label">Variants:</span>
                <div className="inline-counter">
                  <button
                    type="button"
                    className="counter-btn"
                    onClick={() => setVariantsCount(prev => Math.max(1, prev - 1))}
                  >
                    -
                  </button>
                  <span className="counter-value">{variantsCount}</span>
                  <button
                    type="button"
                    className="counter-btn"
                    onClick={() => setVariantsCount(prev => Math.min(5, prev + 1))}
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            {/* Chat Input Box */}
            <form onSubmit={handleGenerate} className="chat-input-form">
              <div className="chat-input-bar">
                <textarea
                  className="chat-input-textarea"
                  placeholder={selectedJob ? "Point out mistakes or request changes in this campaign..." : "Message ViralGen AI..."}
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  rows={1}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleGenerate(e);
                    }
                  }}
                />
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={!brief || brief.trim().length < 3 || activeJobStatus === 'PENDING' || activeJobStatus === 'PROCESSING'}
                  title="Generate Campaign"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                </button>
              </div>
              <div className="chat-input-disclaimer">
                AI can make mistakes. Specify your platforms and personas using the config selectors above.
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Footer copyright section */}
      <footer>
        <span>©2026 ViralGen AI Terminal</span>
      </footer>
    </div>
  );
}
