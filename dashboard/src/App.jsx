import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  Send, 
  CheckCircle, 
  Loader2, 
  Wifi, 
  WifiOff,
  AlertCircle, 
  Cpu, 
  Layers, 
  Globe, 
  Code, 
  FileText, 
  Database,
  Clock,
  MessageSquare,
  Shield,
  Play,
  Activity,
  ArrowRight,
  Server,
  Zap,
  HelpCircle,
  FileCode,
  Download,
  Eye,
  RefreshCw,
  Settings,
  Folder,
  User
} from 'lucide-react';
import './App.css';

export default function App() {
  // Navigation
  const [activeTab, setActiveTab] = useState('overview');

  // WebSocket & Bridge State
  const [wsConnected, setWsConnected] = useState(false);
  const [mongoConnected, setMongoConnected] = useState(false);
  const [task, setTask] = useState(null);
  const [tools, setTools] = useState([]);
  const [status, setStatus] = useState('idle');
  const [whatsapp, setWhatsapp] = useState([]);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [taskText, setTaskText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [expandedTools, setExpandedTools] = useState({});
  const [qrCode, setQrCode] = useState(null);
  const [whatsappConnected, setWhatsappConnected] = useState(false);
  
  // Workspace files state
  const [workspaceFiles, setWorkspaceFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [fileFilter, setFileFilter] = useState('all');

  // WhatsApp manual message state
  const [waTarget, setWaTarget] = useState('923430699325@c.us');
  const [waMessage, setWaMessage] = useState('');
  const [sendingWa, setSendingWa] = useState(false);

  // Executions logs state filter
  const [toolSearch, setToolSearch] = useState('');
  
  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const chatEndRef = useRef(null);

  // Connect to WebSocket Server on port 3001
  useEffect(() => {
    const connectWS = () => {
      console.log('Connecting to WebSocket...');
      const ws = new WebSocket('ws://localhost:3001');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WS Message:', message);
          
          if (message.type === 'init') {
            const data = message.data;
            setTask(data.task);
            setTools(data.tools || []);
            setStatus(data.status || 'idle');
            setWhatsapp(data.whatsapp || []);
            setMongoConnected(data.mongoConnected || false);
            setQrCode(data.qr || null);
            setWhatsappConnected(data.isConnected || false);
          } else if (message.type === 'mongo_status') {
            setMongoConnected(message.data.mongoConnected);
          } else if (message.type === 'qr_code') {
            setQrCode(message.data.qr);
            setWhatsappConnected(false);
          } else if (message.type === 'ready_status') {
            setWhatsappConnected(message.data.isConnected);
            if (message.data.isConnected) {
              setQrCode(null);
            }
          } else if (message.type === 'task_started') {
            setTask(message.data);
            setTools([]);
            setStatus('running');
            setElapsedTime(0);
          } else if (message.type === 'plan_generated') {
            setTask(prev => prev ? { 
              ...prev, 
              goal: message.data.goal,
              plan: message.data.plan,
              current_step: message.data.current_step
            } : null);
          } else if (message.type === 'tool_call') {
            setTools(prev => [...prev, message.data]);
            setStatus('running');
            // Auto refresh files on tool execution complete
            fetchWorkspaceFiles();
          } else if (message.type === 'task_completed') {
            setStatus('completed');
            if (task) {
              setTask(prev => prev ? { ...prev, model: message.data.model } : null);
            }
            fetchWorkspaceFiles();
          } else if (message.type === 'whatsapp_sent') {
            setWhatsapp(prev => [...prev, message.data]);
          }
        } catch (e) {
          console.error('Error parsing WS message:', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        setTimeout(connectWS, 3000);
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
      };
    };

    connectWS();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Timer logic for running state
  useEffect(() => {
    if (status === 'running') {
      timerRef.current = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [status]);

  // Fetch Workspace Files
  const fetchWorkspaceFiles = async () => {
    setLoadingFiles(true);
    try {
      const res = await fetch('http://localhost:3001/api/workspace-files');
      if (res.ok) {
        const data = await res.json();
        setWorkspaceFiles(data.files || []);
      }
    } catch (err) {
      console.error('Error fetching workspace files:', err);
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    fetchWorkspaceFiles();
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [whatsapp, activeTab]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    if (!taskText.trim() || submitting) return;
    
    setSubmitting(true);
    try {
      const res = await fetch('http://localhost:3001/api/manual-task', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ task: taskText }),
      });
      if (res.ok) {
        setTask({
          prompt: taskText,
          started_at: new Date().toISOString()
        });
        setTools([]);
        setStatus('running');
        setElapsedTime(0);
        setTaskText('');
      } else {
        alert('Failed to send task to bridge server.');
      }
    } catch (err) {
      console.error(err);
      alert('Error connecting to bridge server API.');
    } finally {
      setSubmitting(false);
    }
  };

  const runPreset = async (presetText) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch('http://localhost:3001/api/manual-task', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ task: presetText }),
      });
      if (res.ok) {
        setTask({
          prompt: presetText,
          started_at: new Date().toISOString()
        });
        setTools([]);
        setStatus('running');
        setElapsedTime(0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendWaMessage = async (e) => {
    e.preventDefault();
    if (!waMessage.trim() || sendingWa) return;

    setSendingWa(true);
    try {
      const res = await fetch('http://localhost:3001/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ number: waTarget, message: waMessage }),
      });
      if (res.ok) {
        setWaMessage('');
      } else {
        alert('Failed to send message.');
      }
    } catch (err) {
      console.error(err);
      alert('Error sending message.');
    } finally {
      setSendingWa(false);
    }
  };

  const handleWhatsappLogout = async () => {
    if (!window.confirm("Are you sure you want to log out of WhatsApp? This will disconnect the current device.")) return;
    try {
      const res = await fetch('http://localhost:3001/api/whatsapp/logout', {
        method: 'POST',
      });
      if (res.ok) {
        alert("Logout request sent. Reinitializing bridge...");
        setWhatsappConnected(false);
        setQrCode(null);
      } else {
        alert("Failed to send logout request.");
      }
    } catch (err) {
      console.error(err);
      alert("Error logging out.");
    }
  };

  const handleWhatsappConnect = async () => {
    try {
      const res = await fetch('http://localhost:3001/api/whatsapp/connect', {
        method: 'POST',
      });
      if (res.ok) {
        alert("Connection request sent. The QR code should load shortly.");
      } else {
        alert("Failed to send connect request.");
      }
    } catch (err) {
      console.error(err);
      alert("Error initiating connection.");
    }
  };

  const getToolIcon = (name) => {
    switch (name) {
      case 'search_web':
        return <Globe className="text-cyan-400" size={14} />;
      case 'write_and_run_code':
      case 'run_existing_file':
        return <Code className="text-purple-400" size={14} />;
      case 'read_file':
      case 'write_file':
      case 'write_word_file':
        return <FileText className="text-blue-400" size={14} />;
      case 'list_files':
        return <Layers className="text-amber-400" size={14} />;
      case 'whatsapp_send':
      case 'send_whatsapp_file':
      case 'whatsapp_notify_me':
        return <Send className="text-emerald-400" size={14} />;
      default:
        return <Terminal className="text-slate-400" size={14} />;
    }
  };

  const toggleToolExpand = (idx) => {
    setExpandedTools(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileIcon = (filename) => {
    if (filename.endsWith('.docx')) return '📝';
    if (filename.endsWith('.pdf')) return '📕';
    if (filename.endsWith('.png') || filename.endsWith('.webp')) return '🖼️';
    return '📄';
  };

  const quickActions = [
    { title: "🏫 Classroom Upload", desc: "Upload report to Google Classroom and turn it in", prompt: "upload Newton_Laws_Report.docx to class 'Physics Lab' for assignment 'Lab 1 Newton Laws'", icon: <Layers className="text-cyan-400" size={18} /> },
    { title: "💻 Compile Code Online", desc: "Run C++ or JS code online and send the output", prompt: "run this C++ code online and print the result:\n#include <iostream>\nint main() { std::cout << \"C++ code executed on OneCompiler!\"; return 0; }", icon: <Code className="text-purple-400" size={18} /> },
    { title: "🔍 Search RAG Knowledge", desc: "Search the local knowledge base for references", prompt: "search knowledge base for 'lab manuals or guidelines'", icon: <Database className="text-amber-400" size={18} /> },
    { title: "💬 Send Test Ping", desc: "Send test WhatsApp status to confirm active bridge", prompt: "whatsapp_notify_me 'HERALD Control online! Connection is fully functional.'", icon: <Send className="text-emerald-400" size={18} /> }
  ];

  return (
    <div className="app-container">
      {/* Sidebar navigation */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">H</div>
          <div className="logo-text">
            <h1>HERALD CONTROL</h1>
            <p>Cognitive Agent Deck</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
            <Activity size={16} />
            <span>Control Center</span>
          </div>
          <div className={`nav-item ${activeTab === 'executions' ? 'active' : ''}`} onClick={() => setActiveTab('executions')}>
            <Terminal size={16} />
            <span>Tool Executions</span>
          </div>
          <div className={`nav-item ${activeTab === 'whatsapp' ? 'active' : ''}`} onClick={() => setActiveTab('whatsapp')}>
            <MessageSquare size={16} />
            <span>WhatsApp Bridge</span>
          </div>
          <div className={`nav-item ${activeTab === 'workspace' ? 'active' : ''}`} onClick={() => setActiveTab('workspace')}>
            <Folder size={16} />
            <span>Workspace Files</span>
          </div>
          <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
            <Settings size={16} />
            <span>System Settings</span>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: wsConnected ? '#10b981' : '#ef4444' }} />
            <span style={{ fontSize: '11px', fontWeight: 'bold', color: '#64748b' }}>
              v2.1.0 • {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content pane */}
      <main className="main-content">
        {/* Top Header */}
        <header className="main-header">
          <div className="header-title">
            <h2>
              {activeTab === 'overview' && 'Control Dashboard'}
              {activeTab === 'executions' && 'Pipeline Tool Executions'}
              {activeTab === 'whatsapp' && 'WhatsApp Communications'}
              {activeTab === 'workspace' && 'Workspace Explorer'}
              {activeTab === 'settings' && 'System Configuration'}
            </h2>
            <p>
              {activeTab === 'overview' && 'Monitor and trigger autonomous activities'}
              {activeTab === 'executions' && 'Trace real-time tool calls and terminal responses'}
              {activeTab === 'whatsapp' && 'Track live chat inputs and messages sent'}
              {activeTab === 'workspace' && 'Browse, view and download generated report outputs'}
              {activeTab === 'settings' && 'View local environment settings and keys'}
            </p>
          </div>

          <div className="badge-container">
            <div className={`status-badge ${wsConnected ? 'online' : 'offline'}`}>
              <Wifi size={13} />
              <span>Bridge: {wsConnected ? 'Online' : 'Offline'}</span>
            </div>
            <div className={`status-badge ${whatsappConnected ? 'online' : 'offline'}`}>
              <User size={13} />
              <span>WhatsApp: {whatsappConnected ? 'Connected' : 'Disconnected'}</span>
            </div>
            {whatsappConnected ? (
              <button 
                onClick={handleWhatsappLogout} 
                className="status-badge offline" 
                style={{ 
                  cursor: 'pointer',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  background: 'rgba(239, 68, 68, 0.1)',
                  color: '#f87171',
                  transition: 'all 0.2s',
                  padding: '4px 10px',
                  borderRadius: '100px',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                title="Log out from WhatsApp"
              >
                <span>Logout</span>
              </button>
            ) : (
              <button 
                onClick={handleWhatsappConnect} 
                className="status-badge online" 
                style={{ 
                  cursor: 'pointer',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  background: 'rgba(16, 185, 129, 0.1)',
                  color: '#34d399',
                  transition: 'all 0.2s',
                  padding: '4px 10px',
                  borderRadius: '100px',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                title="Generate QR Code to Connect"
              >
                <span>Connect</span>
              </button>
            )}
            {status === 'running' && (
              <div className="status-badge running">
                <Loader2 size={13} className="animate-spin" />
                <span>AGENT RUNNING</span>
              </div>
            )}
          </div>
        </header>

        {/* Overview Tab Content */}
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Connection Telemetry Grid */}
            <div className="stats-grid">
              <div className="cyber-panel stat-widget">
                <div className="stat-icon cyan"><Clock size={20} /></div>
                <div className="stat-data">
                  <p>Elapsed Time</p>
                  <h3>{formatTime(elapsedTime)}</h3>
                </div>
              </div>

              <div className="cyber-panel stat-widget">
                <div className="stat-icon purple"><Terminal size={20} /></div>
                <div className="stat-data">
                  <p>Tool Executions</p>
                  <h3>{tools.length} Steps</h3>
                </div>
              </div>

              <div className="cyber-panel stat-widget">
                <div className="stat-icon green"><Database size={20} /></div>
                <div className="stat-data">
                  <p>MongoDB Cache</p>
                  <h3 style={{ color: mongoConnected ? '#10b981' : '#ef4444' }}>
                    {mongoConnected ? 'CONNECTED' : 'DISCONNECTED'}
                  </h3>
                </div>
              </div>

              <div className="cyber-panel stat-widget">
                <div className="stat-icon amber"><MessageSquare size={20} /></div>
                <div className="stat-data">
                  <p>WhatsApp Node</p>
                  <h3 style={{ color: whatsappConnected ? '#10b981' : '#ef4444' }}>
                    {whatsappConnected ? 'READY' : 'SCAN REQUIRED'}
                  </h3>
                </div>
              </div>
            </div>

            {/* QR Scanner Alert */}
            {!whatsappConnected && qrCode && (
              <div className="cyber-panel" style={{ border: '2px dashed #a855f7', background: 'rgba(168, 85, 247, 0.05)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '24px' }}>
                <div style={{ textAlign: 'center' }}>
                  <h3 style={{ margin: 0, color: '#a855f7', fontSize: '15px', fontWeight: '800', letterSpacing: '1px' }}>
                    ⚠️ WHATSAPP CONNECT REQUIRED
                  </h3>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
                    Scan this QR code with your linked device to activate the HERALD bridge.
                  </p>
                </div>
                <div style={{
                  background: 'white',
                  padding: '12px',
                  borderRadius: '12px',
                  boxShadow: '0 0 25px rgba(168, 85, 247, 0.25)',
                  display: 'inline-block'
                }}>
                  <img 
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(qrCode)}`}
                    alt="WhatsApp QR Code"
                    style={{ display: 'block', width: '200px', height: '200px' }}
                  />
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  Settings &gt; Linked Devices &gt; Link a Device
                </div>
              </div>
            )}

            {/* Direct Command Center */}
            <div className="cyber-panel" style={{ borderLeft: '3px solid var(--neon-cyan)' }}>
              <div className="panel-header">
                <span className="panel-title" style={{ color: 'var(--neon-cyan)' }}><Zap size={14} /> Agent Command Console</span>
                <Activity size={14} className="text-cyan-400" />
              </div>

              <form onSubmit={handleManualSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <textarea
                  className="prompt-area"
                  value={taskText}
                  onChange={(e) => setTaskText(e.target.value)}
                  placeholder="Enter direct instruction prompt for HERALD (e.g. 'generate physics lab report for Lab 3')"
                  disabled={submitting}
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="submit"
                    className="glow-btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      padding: '12px 24px',
                      borderRadius: '8px',
                      fontSize: '13px',
                    }}
                    disabled={submitting || !taskText.trim()}
                  >
                    {submitting ? (
                      <>
                        <Loader2 size={15} className="animate-spin" />
                        <span>PROCESSING...</span>
                      </>
                    ) : (
                      <>
                        <Play size={15} />
                        <span>RUN PIPELINE</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* Presets / Quick Actions */}
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px' }}>
                ⚡ Agent Quick Run Presets
              </div>
              <div className="presets-grid">
                {quickActions.map((action, idx) => (
                  <div key={idx} className="preset-card" onClick={() => runPreset(action.prompt)}>
                    <div className="preset-icon">{action.icon}</div>
                    <div className="preset-info">
                      <h4>{action.title}</h4>
                      <p>{action.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Execution Checklist */}
            {task && (
              <div className="cyber-panel purple-glow" style={{ borderLeft: '3px solid var(--neon-purple)' }}>
                <div className="panel-header">
                  <span className="panel-title" style={{ color: 'var(--neon-purple)' }}><Layers size={14} /> Live Task Checklist</span>
                  {status === 'running' && <span style={{ fontSize: '10px', color: 'var(--neon-purple)', fontWeight: 'bold' }}>PROCESSING</span>}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {task.goal && (
                    <div>
                      <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '800', display: 'block', textTransform: 'uppercase' }}>Target Objective</span>
                      <p style={{ fontSize: '13px', color: 'var(--text-main)', marginTop: '4px', lineHeight: '1.4' }}>{task.goal}</p>
                    </div>
                  )}

                  {task.plan ? (
                    <div style={{ marginTop: '8px' }}>
                      <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '800', display: 'block', textTransform: 'uppercase', marginBottom: '16px' }}>Sequence Checklist</span>
                      <div className="pipeline-container">
                        {(() => {
                          const stepsList = task.plan.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                          const activeStepIdx = stepsList.findIndex(l => {
                            const cleanL = l.replace(/^\d+[\.\-]\s*/, '').replace(/^\-\s*/, '');
                            return task.current_step && (cleanL.toLowerCase().includes(task.current_step.toLowerCase()) || task.current_step.toLowerCase().includes(cleanL.toLowerCase()));
                          });

                          // Calculate progress line height based on completed steps
                          const currentActive = activeStepIdx !== -1 ? activeStepIdx : 0;
                          const progressHeight = stepsList.length > 1
                            ? `${(currentActive / (stepsList.length - 1)) * 100}%`
                            : '0%';

                          return (
                            <>
                              <div className="pipeline-line" />
                              <div className="pipeline-line-progress" style={{ height: progressHeight }} />
                              {stepsList.map((step, idx) => {
                                const cleanStep = step.replace(/^\d+[\.\-]\s*/, '').replace(/^\-\s*/, '');
                                const isCompleted = status === 'completed' || (activeStepIdx !== -1 && idx < activeStepIdx);
                                const isActive = !isCompleted && (idx === activeStepIdx || (activeStepIdx === -1 && idx === 0));

                                return (
                                  <div 
                                    key={idx}
                                    className={`pipeline-step ${isCompleted ? 'pipeline-step-completed' : ''} ${isActive ? 'pipeline-step-active' : ''}`}
                                  >
                                    <div className="pipeline-dot">
                                      {isCompleted ? (
                                        <CheckCircle size={10} style={{ color: 'var(--neon-green)' }} />
                                      ) : isActive ? (
                                        <Loader2 size={10} className="animate-spin" style={{ color: 'var(--neon-purple)' }} />
                                      ) : (
                                        <div style={{ width: '4px', height: '4px', borderRadius: '50%', backgroundColor: '#475569' }} />
                                      )}
                                    </div>
                                    <div className="pipeline-step-content">
                                      <span className="pipeline-step-title">{cleanStep}</span>
                                    </div>
                                  </div>
                                );
                              })}
                            </>
                          );
                        })()}
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', fontSize: '12px', marginTop: '12px' }}>
                      <Loader2 size={12} className="animate-spin" />
                      <span>Generating step checklist...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Executions Tab Content */}
        {activeTab === 'executions' && (
          <div className="cyber-panel" style={{ minHeight: '500px' }}>
            <div className="panel-header">
              <span className="panel-title"><Terminal size={14} /> Executed Tools Telemetry Log</span>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input 
                  type="text" 
                  value={toolSearch} 
                  onChange={(e) => setToolSearch(e.target.value)} 
                  placeholder="Filter tools..." 
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    padding: '4px 10px',
                    color: 'white',
                    fontSize: '12px',
                    outline: 'none'
                  }}
                />
              </div>
            </div>

            <div className="exec-list">
              {tools.length > 0 ? (
                tools
                  .filter(t => !toolSearch || t.tool.toLowerCase().includes(toolSearch.toLowerCase()))
                  .map((item, idx) => {
                    const isExpanded = expandedTools[idx];
                    return (
                      <div key={idx} className="exec-card">
                        <div className="exec-card-header" onClick={() => toggleToolExpand(idx)}>
                          <div className="exec-card-title">
                            {getToolIcon(item.tool)}
                            <span style={{ color: 'var(--neon-cyan)' }}>{item.tool}</span>
                          </div>
                          <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                            {new Date(item.time).toLocaleTimeString()}
                          </span>
                        </div>

                        {isExpanded ? (
                          <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <div className="exec-code-block">
                              <span>Arguments Parameters</span>
                              <pre>{JSON.stringify(item.args, null, 2)}</pre>
                            </div>
                            {item.result_preview && (
                              <div className="exec-code-block output">
                                <span>Output Result Preview</span>
                                <pre>{item.result_preview}</pre>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div 
                            onClick={() => toggleToolExpand(idx)}
                            style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', cursor: 'pointer', fontStyle: 'italic' }}
                          >
                            Click to expand arguments and logs output...
                          </div>
                        )}
                      </div>
                    );
                  })
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 0', opacity: 0.5 }}>
                  <Terminal size={32} style={{ marginBottom: '12px', color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No tool calls executed in the active session.</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* WhatsApp Tab Content */}
        {activeTab === 'whatsapp' && (
          <div className="whatsapp-screen">
            <div className="wa-list-pane">
              <div className="wa-list-header">CONTACT CHATS</div>
              <div className="wa-list-items">
                <div className={`wa-user-item ${waTarget.includes('923430699325') ? 'active' : ''}`} onClick={() => setWaTarget('923430699325@c.us')}>
                  <div className="wa-avatar">A</div>
                  <div className="wa-user-info">
                    <h4>Primary Owner</h4>
                    <p>+923430699325</p>
                  </div>
                </div>
                <div className={`wa-user-item ${waTarget.includes('923004085054') ? 'active' : ''}`} onClick={() => setWaTarget('923004085054@c.us')}>
                  <div className="wa-avatar">H</div>
                  <div className="wa-user-info">
                    <h4>Secondary Owner</h4>
                    <p>+923004085054</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="wa-chat-pane">
              <div className="wa-chat-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="wa-chat-user">
                  <div className="wa-avatar" style={{ background: '#10b981' }}>💬</div>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '13px', fontWeight: '700', color: 'white' }}>
                      {waTarget.includes('923430699325') ? 'Primary Owner' : 'Secondary Owner'}
                    </h4>
                    <span style={{ fontSize: '10px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                      <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                      Active Node Bridge
                    </span>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  {whatsappConnected ? (
                    <button
                      onClick={handleWhatsappLogout}
                      className="glow-btn"
                      style={{
                        padding: '6px 12px',
                        background: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        borderRadius: '6px',
                        fontSize: '11px',
                        color: '#f87171',
                        cursor: 'pointer'
                      }}
                    >
                      Logout Session
                    </button>
                  ) : (
                    <button
                      onClick={handleWhatsappConnect}
                      className="glow-btn"
                      style={{
                        padding: '6px 12px',
                        background: 'rgba(16, 185, 129, 0.2)',
                        border: '1px solid rgba(16, 185, 129, 0.4)',
                        borderRadius: '6px',
                        fontSize: '11px',
                        color: '#34d399',
                        cursor: 'pointer'
                      }}
                    >
                      Connect QR
                    </button>
                  )}
                </div>
              </div>

              <div className="wa-chat-body">
                {whatsapp.length > 0 ? (
                  whatsapp
                    .filter(msg => msg.number.replace('@c.us', '').includes(waTarget.split('@')[0]))
                    .map((msg, index) => (
                      <div key={index} className="wa-bubble outgoing">
                        {msg.message}
                        <span className="wa-time">
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.5 }}>
                    <MessageSquare size={32} style={{ marginBottom: '12px', color: 'var(--text-muted)' }} />
                    <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>No messages logged in this session.</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="wa-chat-footer">
                <form onSubmit={handleSendWaMessage} className="wa-chat-form">
                  <input
                    type="text"
                    className="wa-chat-input"
                    value={waMessage}
                    onChange={(e) => setWaMessage(e.target.value)}
                    placeholder="Type a message to send to linked owner device..."
                    disabled={sendingWa}
                  />
                  <button
                    type="submit"
                    className="glow-btn"
                    style={{
                      borderRadius: '10px',
                      padding: '0 18px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                    disabled={sendingWa || !waMessage.trim()}
                  >
                    {sendingWa ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Workspace Tab Content */}
        {activeTab === 'workspace' && (
          <div className="cyber-panel" style={{ minHeight: '500px' }}>
            <div className="panel-header">
              <span className="panel-title"><Folder size={14} /> Generated Labs & Screenshots Files</span>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <select 
                  value={fileFilter} 
                  onChange={(e) => setFileFilter(e.target.value)}
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    padding: '4px 10px',
                    color: 'white',
                    fontSize: '12px',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="all">All Files</option>
                  <option value="docx">Lab Reports (.docx)</option>
                  <option value="png">Screenshots (.png / .webp)</option>
                </select>

                <button 
                  onClick={fetchWorkspaceFiles} 
                  className="file-action-btn"
                  style={{ padding: '6px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '6px' }}
                >
                  <RefreshCw size={13} className={loadingFiles ? 'animate-spin' : ''} />
                </button>
              </div>
            </div>

            {loadingFiles ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
                <Loader2 size={24} className="animate-spin text-cyan-400" />
              </div>
            ) : (
              <div className="file-grid">
                {workspaceFiles.length > 0 ? (
                  workspaceFiles
                    .filter(file => {
                      if (fileFilter === 'docx') return file.name.endsWith('.docx');
                      if (fileFilter === 'png') return file.name.endsWith('.png') || file.name.endsWith('.webp');
                      return true;
                    })
                    .map((file, idx) => (
                      <div key={idx} className="file-card">
                        <div className="file-type-icon">{getFileIcon(file.name)}</div>
                        <div className="file-card-details">
                          <h4 title={file.name}>{file.name}</h4>
                          <p>{formatBytes(file.size)}</p>
                          <p style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
                            Mod: {new Date(file.mtime).toLocaleString()}
                          </p>
                        </div>
                        <div className="file-card-actions">
                          <a 
                            href={`http://localhost:3001/api/view-file?filepath=${encodeURIComponent(file.path)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="file-action-btn"
                            style={{ textDecoration: 'none' }}
                          >
                            <Eye size={12} />
                            <span>View</span>
                          </a>
                          <a 
                            href={`http://localhost:3001/api/download-file?filepath=${encodeURIComponent(file.path)}`}
                            download={file.name}
                            className="file-action-btn"
                            style={{ textDecoration: 'none' }}
                          >
                            <Download size={12} />
                            <span>Download</span>
                          </a>
                        </div>
                      </div>
                    ))
                ) : (
                  <div style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 0', opacity: 0.5 }}>
                    <Folder size={36} style={{ marginBottom: '12px', color: 'var(--text-muted)' }} />
                    <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No generated workspace files found.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Settings Tab Content */}
        {activeTab === 'settings' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div className="cyber-panel">
              <div className="panel-header">
                <span className="panel-title"><Server size={14} /> Backend Environments</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>WhatsApp Bridge Port</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>3001 (Node Express)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Agent Communication Port</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>5000 (Python Flask)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>MongoDB Connection String</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)' }}>mongodb://localhost:27017/herald</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Primary Owner LID</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>923430699325@c.us</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Secondary Owner LID</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>923004085054@c.us</span>
                </div>
              </div>
            </div>

            <div className="cyber-panel">
              <div className="panel-header">
                <span className="panel-title"><Shield size={14} /> Storage Directories Configuration</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Screenshots Export Folder</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', color: 'var(--neon-purple)', fontFamily: 'var(--font-mono)' }}>/mnt/AhmarData/screenshots</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Classroom Download Buffer</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>/openwork_project/temp_downloads</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>System Logs Output</span>
                  <span style={{ fontSize: '13px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>/openwork_project/logs/startup.log</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
