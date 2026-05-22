import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity, Heart, Thermometer, ShieldAlert, CheckCircle2,
  AlertTriangle, UserX, UserCheck, Wifi, WifiOff,
  BatteryFull, BatteryLow, Clock, Zap, History, Cpu,
  RefreshCcw, Volume2, VolumeX, Settings, Save
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

type SystemState = 'NORMAL' | 'POSSIBLE_FALL' | 'FALL_CONFIRMED' | 'MEDICAL_ALERT' | 'ALERT_SENT' | 'RECOVERY';

interface SensorData {
  time: string;
  ax: number;
  ay: number;
  az: number;
  smv: number;
}

interface EventRecord {
  timestamp: number;
  event_type: string;
  confidence: number;
  system_state: string;
}

interface DeviceInfo {
  mac_address: string;
  device_type: string;
  battery_level: number;
  is_active: boolean;
  status: string;
  seconds_since_seen: number;
}

const BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const CAMERA_URL = import.meta.env.VITE_CAMERA_URL || 'http://localhost:8001/video_feed';

export default function App() {
  const [systemState, setSystemState] = useState<SystemState>('NORMAL');
  const [isPersonVisible, setIsPersonVisible] = useState(false);
  const [vitals, setVitals] = useState({ hr: 0, spo2: 0 });
  const [hasVitals, setHasVitals] = useState(false);
  const [motionData, setMotionData] = useState<SensorData[]>([]);
  const [hasMotionData, setHasMotionData] = useState(false);
  const [isAudioDistress, setIsAudioDistress] = useState(false);
  const [fallScore, setFallScore] = useState(0);
  const [eventHistory, setEventHistory] = useState<EventRecord[]>([]);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const [isTestingSiren, setIsTestingSiren] = useState(false);

  // Reference for stable WebSocket subscriptions without reconnection spikes
  const hasVitalsRef = useRef(hasVitals);

  const [cameraUrl, setCameraUrl] = useState(() => {
    return localStorage.getItem('custom_camera_url') || CAMERA_URL;
  });
  const [baseUrl, setBaseUrl] = useState(() => {
    return localStorage.getItem('custom_backend_url') || BASE_URL;
  });
  const [showCameraSettings, setShowCameraSettings] = useState(false);
  const [customCameraUrl, setCustomCameraUrl] = useState(cameraUrl);
  const [customBaseUrl, setCustomBaseUrl] = useState(baseUrl);

  const wsUrl = baseUrl.replace(/^http/, 'ws');

  const saveSettings = useCallback(() => {
    localStorage.setItem('custom_camera_url', customCameraUrl);
    localStorage.setItem('custom_backend_url', customBaseUrl);
    setCameraUrl(customCameraUrl);
    setBaseUrl(customBaseUrl);
    setShowCameraSettings(false);
  }, [customCameraUrl, customBaseUrl]);

  useEffect(() => {
    hasVitalsRef.current = hasVitals;
  }, [hasVitals]);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(`${wsUrl}/ws/live-feed/patient_01`);
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connect, 3000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.system_state) setSystemState(msg.system_state);
          if (msg.state) setSystemState(msg.state);
          if (msg.fall_score !== undefined) setFallScore(msg.fall_score);

          // Heartbeat snapshot from backend
          if (msg.type === 'heartbeat') {
            if (msg.is_person_visible !== undefined) setIsPersonVisible(msg.is_person_visible);
            if (msg.vitals && (msg.vitals.heart_rate !== 75 || msg.vitals.spo2 !== 98 || hasVitalsRef.current)) {
              // Only update vitals if we've received real sensor data
              if (msg.vitals.heart_rate !== 75 || msg.vitals.spo2 !== 98) {
                setHasVitals(true);
              }
              if (hasVitalsRef.current) {
                setVitals({ hr: msg.vitals.heart_rate, spo2: msg.vitals.spo2 });
              }
            }
            if (msg.audio) setIsAudioDistress(msg.audio.distress_sound_detected);
            if (msg.event_history) setEventHistory(msg.event_history);
            if (msg.fall_score !== undefined) setFallScore(msg.fall_score);

            if (msg.motion && (msg.motion.ax !== 0 || msg.motion.ay !== 0 || msg.motion.az !== 0)) {
              setHasMotionData(true);
              
              // Calculate or read SMV to check for fluctuations
              const ax = msg.motion.ax;
              const ay = msg.motion.ay;
              const az = msg.motion.az;
              const smv = msg.motion.smv ?? Math.sqrt(ax * ax + ay * ay + az * az);
              
              // Trigger beep warning on sudden fluctuations
              if ((smv > 2.2 || smv < 0.4) && Date.now() - lastBeepTimeRef.current > 1500) {
                lastBeepTimeRef.current = Date.now();
                playBeepSynth();
                if (beepAudioRef.current) {
                  beepAudioRef.current.play().catch(e => console.log('Beep blocked:', e));
                }
              }

              setMotionData(prev => {
                const point: SensorData = {
                  time: new Date().toLocaleTimeString([], { hour12: false }),
                  ax: ax,
                  ay: ay,
                  az: az,
                  smv: smv,
                };
                const updated = [...prev, point];
                return updated.length > 40 ? updated.slice(-40) : updated;
              });
            }
          }

          // Live CV event
          if (msg.type === 'cv_update') {
            setIsPersonVisible(msg.data?.person_visible ?? false);
          }

          // Live IoT event
          if (msg.type === 'iot_update') {
            const d = msg.data;
            if (d.heart_rate || d.spo2) {
              setHasVitals(true);
              setVitals(v => ({
                hr: d.heart_rate ?? v.hr,
                spo2: d.spo2 ?? v.spo2,
              }));
            }
            if (d.distress_sound_detected !== undefined) setIsAudioDistress(d.distress_sound_detected);
            if (d.ax !== undefined || d.ay !== undefined || d.az !== undefined) {
              setHasMotionData(true);
              
              const ax = d.ax ?? 0;
              const ay = d.ay ?? 0;
              const az = d.az ?? 0;
              const smv = msg.smv ?? Math.sqrt(ax * ax + ay * ay + az * az);

              // Trigger beep warning on sudden fluctuations
              if ((smv > 2.2 || smv < 0.4) && Date.now() - lastBeepTimeRef.current > 1500) {
                lastBeepTimeRef.current = Date.now();
                playBeepSynth();
                if (beepAudioRef.current) {
                  beepAudioRef.current.play().catch(e => console.log('Beep blocked:', e));
                }
              }

              setMotionData(prev => {
                const point: SensorData = {
                  time: new Date().toLocaleTimeString([], { hour12: false }),
                  ax: ax,
                  ay: ay,
                  az: az,
                  smv: smv,
                };
                const updated = [...prev, point];
                return updated.length > 40 ? updated.slice(-40) : updated;
              });
            }
          }
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };
    };

    connect();
    return () => wsRef.current?.close();
  }, [wsUrl]);

  // Fetch device health periodically
  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const res = await fetch(`${baseUrl}/api/v1/devices`);
        const data = await res.json();
        setDevices(data.devices || []);
      } catch { /* backend offline */ }
    };
    fetchDevices();
    const interval = setInterval(fetchDevices, 10000);
    return () => clearInterval(interval);
  }, [baseUrl]);

  // Alert sound and warning beep sound
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const beepAudioRef = useRef<HTMLAudioElement | null>(null);
  const lastBeepTimeRef = useRef<number>(0);

  // Web Audio API Synthesizers (100% network/CORS-independent)
  const audioCtxRef = useRef<AudioContext | null>(null);
  const synthNodesRef = useRef<{ osc: OscillatorNode; lfo: OscillatorNode; gain: GainNode } | null>(null);

  const startSirenSynth = useCallback(() => {
    if (synthNodesRef.current) return;
    try {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtxClass();
      audioCtxRef.current = ctx;

      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();
      const lfo = ctx.createOscillator();
      const lfoGain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(450, ctx.currentTime);

      lfo.frequency.value = 1.8; // Oscillation rate (1.8 wails per sec)
      lfoGain.gain.value = 180; // Pitch sweep range (450 +/- 180 Hz)

      lfo.connect(lfoGain);
      lfoGain.connect(osc.frequency);

      osc.connect(gainNode);
      gainNode.connect(ctx.destination);

      gainNode.gain.setValueAtTime(0.4, ctx.currentTime);

      lfo.start();
      osc.start();

      synthNodesRef.current = { osc, lfo, gain: gainNode };
    } catch (e) {
      console.error('Siren Synth failed:', e);
    }
  }, []);

  const stopSirenSynth = useCallback(() => {
    try {
      if (synthNodesRef.current) {
        const { osc, lfo } = synthNodesRef.current;
        osc.stop();
        lfo.stop();
        osc.disconnect();
        lfo.disconnect();
        synthNodesRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close();
        audioCtxRef.current = null;
      }
    } catch (e) {
      console.error('Siren Synth stop failed:', e);
    }
  }, []);

  const playBeepSynth = useCallback(() => {
    try {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtxClass();
      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // High pitch warning beep

      osc.connect(gainNode);
      gainNode.connect(ctx.destination);

      gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15); // Fade out quickly

      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.log('Beep Synth failed:', e);
    }
  }, []);

  const triggerSoundTest = useCallback(() => {
    setIsTestingSiren(true);
    startSirenSynth();
    setTimeout(() => {
      stopSirenSynth();
      setIsTestingSiren(false);
    }, 1500);
  }, [startSirenSynth, stopSirenSynth]);

  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
      audioRef.current.loop = true;
    }
    if (!beepAudioRef.current) {
      beepAudioRef.current = new Audio('https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3');
    }
  }, []);


  const acknowledgeAlert = useCallback(async () => {
    stopSirenSynth();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    try {
      await fetch(`${baseUrl}/api/v1/alerts/patient_01/acknowledge`, { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  }, [baseUrl, stopSirenSynth]);

  const isEmergency = ['POSSIBLE_FALL', 'FALL_CONFIRMED', 'MEDICAL_ALERT', 'ALERT_SENT'].includes(systemState);



  useEffect(() => {
    if (isEmergency) {
      startSirenSynth();
      if (audioRef.current) {
        audioRef.current.play().catch(e => console.log('Audio play blocked:', e));
      }
    } else {
      stopSirenSynth();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
    }
  }, [isEmergency, startSirenSynth, stopSirenSynth]);

  useEffect(() => {
    const unlockAudio = () => {
      try {
        const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
        const tempCtx = new AudioCtxClass();
        if (tempCtx.state === 'suspended') {
          tempCtx.resume();
        }
        const osc = tempCtx.createOscillator();
        const gain = tempCtx.createGain();
        gain.gain.setValueAtTime(0.0001, tempCtx.currentTime);
        osc.connect(gain);
        gain.connect(tempCtx.destination);
        osc.start();
        osc.stop(tempCtx.currentTime + 0.05);
      } catch (e) {
        console.log('Document-click audio warm up failed:', e);
      }
      document.removeEventListener('click', unlockAudio);
    };
    document.addEventListener('click', unlockAudio);
    return () => document.removeEventListener('click', unlockAudio);
  }, []);

  const getStatusStyle = () => {
    switch (systemState) {
      case 'NORMAL': return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
      case 'POSSIBLE_FALL': return 'text-amber-400 bg-amber-400/10 border-amber-400/30';
      case 'FALL_CONFIRMED': return 'text-orange-500 bg-orange-500/10 border-orange-500/30';
      case 'MEDICAL_ALERT':
      case 'ALERT_SENT': return 'text-rose-500 bg-rose-500/10 border-rose-500/30';
      case 'RECOVERY': return 'text-blue-400 bg-blue-400/10 border-blue-400/30';
      default: return 'text-slate-400 bg-slate-400/10 border-slate-400/30';
    }
  };

  const getStatusIcon = () => {
    switch (systemState) {
      case 'NORMAL': return <CheckCircle2 className="w-5 h-5" />;
      case 'POSSIBLE_FALL': return <AlertTriangle className="w-5 h-5" />;
      case 'RECOVERY': return <RefreshCcw className="w-5 h-5" />;
      default: return <ShieldAlert className="w-5 h-5" />;
    }
  };

  const formatTime = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });

  return (
    <div className="min-h-screen p-4 md:p-6 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-5">

        {/* ═══ Header ═══ */}
        <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-violet-400 bg-clip-text text-transparent">
              ShieldCare Monitor
            </h1>
            <p className="text-slate-500 text-sm mt-1">Intelligent Multi-Modal Fall Detection & Health Monitoring</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={triggerSoundTest}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border font-semibold text-xs tracking-wide transition-all shadow-md active:scale-95 shrink-0 ${isTestingSiren ? 'bg-amber-500 text-white border-amber-400 animate-pulse' : 'bg-slate-900/60 hover:bg-slate-800/80 text-slate-200 border-slate-700/60 hover:scale-[1.02]'}`}
            >
              {isTestingSiren ? <Volume2 className="w-4 h-4 text-white" /> : <VolumeX className="w-4 h-4 text-slate-400" />}
              {isTestingSiren ? "SIREN ACTIVE..." : "TEST ALARM SOUND"}
            </button>
            <div className={`px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-1.5 ${wsConnected ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/30 text-rose-400 bg-rose-500/10'}`}>
              {wsConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {wsConnected ? 'LIVE' : 'OFFLINE'}
            </div>
            <div className={`px-5 py-2 rounded-full border flex items-center gap-2 font-semibold text-sm tracking-wide ${getStatusStyle()}`}>
              {getStatusIcon()}
              {systemState.replaceAll('_', ' ')}
            </div>
          </div>
        </header>

        {/* ═══ Flashing High-Urgency Fall Alert Banner ═══ */}
        {isEmergency && (
          <div className="bg-red-600 border border-red-500 text-white p-6 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-5 animate-pulse shadow-[0_0_30px_rgba(220,38,38,0.5)]">
            <div className="flex items-center gap-4 text-center md:text-left">
              <div className="bg-white/20 p-3 rounded-full animate-bounce">
                <ShieldAlert className="w-12 h-12 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-extrabold tracking-wider animate-pulse">⚠️ CRITICAL: FALL DETECTED!</h2>
                <p className="text-base text-red-100 font-medium mt-1">
                  Emergency state triggered! Camera confidence: {(fallScore * 100).toFixed(0)}%. Vitals: {hasVitals ? `Heart Rate ${vitals.hr} BPM | SpO₂ ${vitals.spo2}%` : 'Wearable Standby'}.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button 
                onClick={acknowledgeAlert} 
                className="bg-white hover:bg-red-50 text-red-600 font-bold px-8 py-3 rounded-xl transition-all shadow-lg active:scale-95 shrink-0"
              >
                Acknowledge & Clear Alarm
              </button>
            </div>
          </div>
        )}

        {/* ═══ Main Grid ═══ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

          {/* ─── Left: Camera + Charts (8 cols) ─── */}
          <div className="lg:col-span-8 space-y-5">

            {/* Camera Feed */}
            <div className="glass-panel p-5 h-[420px] flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold flex items-center gap-2 text-slate-200">
                    <Activity className="w-4 h-4 text-indigo-400" /> Live Camera Feed
                  </h2>
                  <button 
                    onClick={() => setShowCameraSettings(!showCameraSettings)} 
                    className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                    title="Camera Feed Settings"
                  >
                    <Settings className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-1.5 ${isPersonVisible ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-slate-700 text-slate-500 bg-slate-800/50'}`}>
                    {isPersonVisible ? <><UserCheck className="w-3.5 h-3.5" /> Person Tracked</> : <><UserX className="w-3.5 h-3.5" /> No Person</>}
                  </div>
                </div>
              </div>
              
              {showCameraSettings && (
                <div className="bg-slate-900/95 border border-slate-800 p-4 rounded-xl mb-3 flex flex-col gap-3 animate-fadeIn shadow-2xl">
                  <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Camera Feed URL</span>
                      <input 
                        type="text" 
                        value={customCameraUrl} 
                        onChange={(e) => setCustomCameraUrl(e.target.value)} 
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition-all font-mono"
                        placeholder="e.g. http://localhost:8001/video_feed"
                      />
                    </div>
                    <div className="flex-1 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Backend API URL</span>
                      <input 
                        type="text" 
                        value={customBaseUrl} 
                        onChange={(e) => setCustomBaseUrl(e.target.value)} 
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition-all font-mono"
                        placeholder="e.g. http://localhost:8000"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button 
                      onClick={saveSettings} 
                      className="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md hover:scale-[1.02]"
                    >
                      <Save className="w-3.5 h-3.5" /> Save Configuration
                    </button>
                  </div>
                </div>
              )}

              <div className="flex-1 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-center relative overflow-hidden">
                <img 
                  src={cameraUrl} 
                  alt="" 
                  className="absolute inset-0 w-full h-full object-cover z-0 transition-opacity duration-300"
                  onError={(e) => {
                    e.currentTarget.style.opacity = '0';
                    e.currentTarget.nextElementSibling?.classList.remove('hidden');
                    e.currentTarget.nextElementSibling?.classList.add('flex');
                  }}
                  onLoad={(e) => {
                    e.currentTarget.style.opacity = '1';
                    e.currentTarget.nextElementSibling?.classList.add('hidden');
                    e.currentTarget.nextElementSibling?.classList.remove('flex');
                  }}
                />
                <span className="text-slate-600 flex flex-col items-center gap-2 text-sm z-0 hidden">
                  <div className="w-2.5 h-2.5 bg-slate-700 rounded-full animate-pulse"></div>
                  Camera Offline
                </span>
                <div className="absolute top-3 left-3 flex gap-2">
                  <span className="bg-black/60 px-2 py-0.5 rounded text-[10px] text-white/70 backdrop-blur-sm">CAM-01 Living Room</span>
                </div>
                <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg">
                  <span className="text-[10px] text-slate-400 block">FALL SCORE</span>
                  <span className={`text-lg font-bold ${fallScore > 0.5 ? 'text-rose-400' : fallScore > 0.2 ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {(fallScore * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {/* IMU Motion Chart */}
            <div className="glass-panel p-5">
              <h2 className="text-base font-semibold flex items-center gap-2 mb-3 text-slate-200">
                <Zap className="w-4 h-4 text-blue-400" /> Wearable IMU Stream (Accelerometer)
              </h2>
              <div className="h-44 w-full">
                {hasMotionData ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={motionData}>
                      <XAxis dataKey="time" stroke="#334155" fontSize={10} tickMargin={8} />
                      <YAxis stroke="#334155" fontSize={10} domain={['auto', 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '10px', fontSize: '12px' }} />
                      <Line type="monotone" dataKey="ax" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Accel X" />
                      <Line type="monotone" dataKey="ay" stroke="#10b981" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Accel Y" />
                      <Line type="monotone" dataKey="az" stroke="#8b5cf6" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Accel Z" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-600 text-sm">
                    <div className="text-center">
                      <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      Waiting for wearable sensor data...
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* SMV Chart */}
            <div className="glass-panel p-5">
              <h2 className="text-base font-semibold flex items-center gap-2 mb-3 text-slate-200">
                <Activity className="w-4 h-4 text-violet-400" /> Signal Magnitude Vector (SMV)
              </h2>
              <div className="h-32 w-full">
                {hasMotionData ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={motionData}>
                      <XAxis dataKey="time" stroke="#334155" fontSize={10} tickMargin={8} />
                      <YAxis stroke="#334155" fontSize={10} domain={[0, 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '10px', fontSize: '12px' }} />
                      <defs>
                        <linearGradient id="smvGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="smv" stroke="#8b5cf6" fill="url(#smvGrad)" strokeWidth={2} dot={false} isAnimationActive={false} name="SMV" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-600 text-sm">
                    Waiting for SMV data...
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ─── Right: Vitals + Audio + Devices (4 cols) ─── */}
          <div className="lg:col-span-4 space-y-5">

            {/* Heart Rate */}
            <div className={`glass-panel p-5 border-l-4 transition-colors duration-500 ${hasVitals && (vitals.hr > 120 || vitals.hr < 45) ? 'border-l-rose-500 bg-rose-500/5' : 'border-l-rose-500'}`}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold flex items-center gap-2 text-rose-200">
                  <Heart className="w-4 h-4 text-rose-500" /> Heart Rate
                </h2>
                {hasVitals && (
                  <span className="flex h-2.5 w-2.5 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
                  </span>
                )}
              </div>
              {hasVitals ? (
                <>
                  <div className="flex items-end gap-2">
                    <span className="text-5xl font-black tracking-tighter text-white">{vitals.hr}</span>
                    <span className="text-rose-400/70 font-medium pb-1.5 text-base">BPM</span>
                  </div>
                  <div className="mt-3 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-700 ${vitals.hr > 120 ? 'bg-gradient-to-r from-rose-600 to-red-400 animate-pulse' : 'bg-gradient-to-r from-rose-600 to-rose-400'}`} style={{ width: `${Math.min((vitals.hr / 160) * 100, 100)}%` }}></div>
                  </div>
                  {(vitals.hr > 120 || vitals.hr < 45) && (
                    <p className="text-xs text-rose-400 mt-2 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Abnormal reading</p>
                  )}
                </>
              ) : (
                <p className="text-slate-600 text-sm mt-2">Waiting for sensor...</p>
              )}
            </div>

            {/* Blood Oxygen */}
            <div className={`glass-panel p-5 border-l-4 transition-colors duration-500 ${hasVitals && vitals.spo2 < 92 ? 'border-l-amber-500 bg-amber-500/5' : 'border-l-cyan-500'}`}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold flex items-center gap-2 text-cyan-200">
                  <Thermometer className="w-4 h-4 text-cyan-500" /> Blood Oxygen (SpO₂)
                </h2>
              </div>
              {hasVitals ? (
                <>
                  <div className="flex items-end gap-2">
                    <span className="text-5xl font-black tracking-tighter text-white">{vitals.spo2}</span>
                    <span className="text-cyan-400/70 font-medium pb-1.5 text-base">%</span>
                  </div>
                  <div className="mt-3 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-700 ${vitals.spo2 < 92 ? 'bg-gradient-to-r from-amber-600 to-amber-400 animate-pulse' : 'bg-gradient-to-r from-cyan-600 to-cyan-400'}`} style={{ width: `${vitals.spo2}%` }}></div>
                  </div>
                  {vitals.spo2 < 92 && (
                    <p className="text-xs text-amber-400 mt-2 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Low oxygen</p>
                  )}
                </>
              ) : (
                <p className="text-slate-600 text-sm mt-2">Waiting for sensor...</p>
              )}
            </div>

            {/* Audio Distress */}
            <div className={`glass-panel p-5 border-l-4 transition-all duration-500 ${isAudioDistress ? 'border-l-amber-500 bg-amber-500/5' : 'border-l-slate-700'}`}>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold flex items-center gap-2 text-slate-300">
                  {isAudioDistress ? <Volume2 className="w-4 h-4 text-amber-500" /> : <VolumeX className="w-4 h-4 text-slate-600" />}
                  Audio Distress
                </h2>
                <div className={`px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider ${isAudioDistress ? 'bg-amber-500 text-amber-950 animate-pulse' : 'bg-slate-800 text-slate-500'}`}>
                  {isAudioDistress ? 'DISTRESS DETECTED' : 'QUIET'}
                </div>
              </div>
            </div>

            {/* Device Health */}
            <div className="glass-panel p-5">
              <h2 className="text-sm font-semibold flex items-center gap-2 mb-3 text-slate-300">
                <Cpu className="w-4 h-4 text-indigo-400" /> Device Health
              </h2>
              {devices.length > 0 ? devices.map(d => (
                <div key={d.mac_address} className="flex items-center justify-between py-2 border-b border-slate-800/50 last:border-0">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${d.status === 'ONLINE' ? 'bg-emerald-400' : 'bg-slate-600'}`}></div>
                    <div>
                      <p className="text-xs font-medium text-slate-300">{d.mac_address}</p>
                      <p className="text-[10px] text-slate-500">{d.device_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {d.device_type === 'WEARABLE' && (
                      <div className="flex items-center gap-1">
                        {d.battery_level > 20 ? <BatteryFull className="w-3.5 h-3.5 text-emerald-400" /> : <BatteryLow className="w-3.5 h-3.5 text-rose-400" />}
                        <span className="text-[10px] text-slate-400">{d.battery_level}%</span>
                      </div>
                    )}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${d.status === 'ONLINE' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800 text-slate-500'}`}>
                      {d.status}
                    </span>
                  </div>
                </div>
              )) : (
                <p className="text-xs text-slate-600">No devices registered</p>
              )}
            </div>
          </div>
        </div>

        {/* ═══ Event History Table ═══ */}
        <div className="glass-panel p-5">
          <h2 className="text-base font-semibold flex items-center gap-2 mb-4 text-slate-200">
            <History className="w-4 h-4 text-indigo-400" /> Event History
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-800">
                  <th className="pb-2 pr-4 font-medium">Time</th>
                  <th className="pb-2 pr-4 font-medium">Event Type</th>
                  <th className="pb-2 pr-4 font-medium">Confidence</th>
                  <th className="pb-2 font-medium">System State</th>
                </tr>
              </thead>
              <tbody>
                {eventHistory.length > 0 ? (
                  [...eventHistory].reverse().map((ev, i) => (
                    <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/30 transition-colors">
                      <td className="py-2 pr-4 text-slate-400 flex items-center gap-1.5">
                        <Clock className="w-3 h-3" />
                        {formatTime(ev.timestamp)}
                      </td>
                      <td className="py-2 pr-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${ev.event_type.includes('MEDICAL') || ev.event_type.includes('EMERGENCY') ? 'bg-rose-500/20 text-rose-400' :
                          ev.event_type.includes('FALL') || ev.event_type.includes('SPIKE') ? 'bg-amber-500/20 text-amber-400' :
                            ev.event_type.includes('AUDIO') ? 'bg-violet-500/20 text-violet-400' :
                              'bg-slate-700 text-slate-400'
                          }`}>
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-slate-300 font-mono">{(ev.confidence * 100).toFixed(0)}%</td>
                      <td className="py-2 text-slate-400">{ev.system_state}</td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan={4} className="py-6 text-center text-slate-600">No events recorded yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
