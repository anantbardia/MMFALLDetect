import notificationService from './notificationService';

class DecisionEngine {
  constructor() {
    this.lastIotData = null;
    this.lastCvData = null;
    this.lastIotTime = 0;
    this.lastCvTime = 0;
    
    // Track fall events for fusion
    this.iotFallTime = 0;
    this.cvFallTime = 0;
    
    this.onStateChange = null; // Callback for UI updates
    
    // Config
    this.ACTIVE_TIMEOUT_MS = 15000; // If no data for 15s, module is considered inactive
    this.FUSION_WINDOW_MS = 5000;   // How close IoT and CV falls must be to trigger Rule B
    this.SMV_FALL_THRESHOLD = 2.5;  // g-force threshold for a fall
    this.CV_FALL_THRESHOLD = 0.8;   // Confidence score threshold for CV fall
    
    this.currentState = 'NORMAL';
  }

  updateIoTData(data) {
    this.lastIotData = data;
    this.lastIotTime = Date.now();
    
    // Evaluate IoT Fall
    // data payload: {"ax":..., "ay":..., "az":..., "smv":..., "motion": "sudden"|"normal"}
    let isIotFall = false;
    if (data.motion === 'sudden' || (data.smv && data.smv > this.SMV_FALL_THRESHOLD)) {
      isIotFall = true;
      this.iotFallTime = Date.now();
    }
    
    this.evaluateFall();
  }

  updateCVData(data) {
    this.lastCvData = data;
    this.lastCvTime = Date.now();
    
    // Evaluate CV Fall
    // data payload: {"system_state": "FALL_CONFIRMED", "fall_score": 0.85, ...}
    let isCvFall = false;
    if (data.system_state === 'FALL_CONFIRMED' || (data.fall_score && data.fall_score >= this.CV_FALL_THRESHOLD)) {
      isCvFall = true;
      this.cvFallTime = Date.now();
    }
    
    this.evaluateFall();
  }

  evaluateFall() {
    const now = Date.now();
    const isIotActive = (now - this.lastIotTime) < this.ACTIVE_TIMEOUT_MS;
    const isCvActive = (now - this.lastCvTime) < this.ACTIVE_TIMEOUT_MS;
    
    const recentIotFall = (now - this.iotFallTime) < this.FUSION_WINDOW_MS;
    const recentCvFall = (now - this.cvFallTime) < this.FUSION_WINDOW_MS;

    let fallConfirmed = false;

    if (isIotActive && isCvActive) {
      // Rule B: High Accuracy. Both modules active, so BOTH must detect fall.
      if (recentIotFall && recentCvFall) {
        fallConfirmed = true;
      }
    } else if (isIotActive && !isCvActive) {
      // Only IoT active
      if (recentIotFall) {
        fallConfirmed = true;
      }
    } else if (!isIotActive && isCvActive) {
      // Only CV active
      if (recentCvFall) {
        fallConfirmed = true;
      }
    }

    if (fallConfirmed && this.currentState !== 'FALL_CONFIRMED') {
      this.setState('FALL_CONFIRMED');
      this.triggerAlarm();
    } else if (!recentIotFall && !recentCvFall && this.currentState === 'FALL_CONFIRMED') {
      // Cooldown/Recovery if neither is seeing a fall anymore
      // We might want to require manual ack, but for now we let it reset after the window if no new data
    } else if (!fallConfirmed) {
      this.setState('NORMAL');
    }
  }

  setState(newState) {
    if (this.currentState !== newState) {
      this.currentState = newState;
      if (this.onStateChange) {
        this.onStateChange(newState);
      }
    }
  }

  triggerAlarm() {
    console.log('[DecisionEngine] TRIGGERING ALARM!');
    notificationService.sendLocalNotification(
      '⚠️ CRITICAL: FALL DETECTED!',
      'Immediate attention required. Fall verified by active sensors.'
    );
  }
}

const decisionEngine = new DecisionEngine();
export default decisionEngine;
