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
    
    // CV-only debounce: require N consecutive CV fall events
    this.cvFallEventCount = 0;
    this.CV_DEBOUNCE_COUNT = 2;
    
    this.onStateChange = null; // Callback for UI updates
    
    // Config
    this.ACTIVE_TIMEOUT_MS = 15000; // If no data for 15s, module is considered inactive
    this.FUSION_WINDOW_MS = 5000;   // How close IoT and CV falls must be to trigger Rule B
    this.CV_FALL_THRESHOLD = 0.8;   // Confidence score threshold for CV fall
    
    this.currentState = 'NORMAL';
    
    // Notification cooldown (prevent spam)
    this.lastNotificationTime = 0;
    this.NOTIFICATION_COOLDOWN_MS = 60000; // 60 seconds
  }

  updateIoTData(data) {
    this.lastIotData = data;
    this.lastIotTime = Date.now();
    
    let isIotFall = false;
    if (data.motion === 'sudden') {
      isIotFall = true;
      this.iotFallTime = Date.now();
    }
    
    this.evaluateFall();
  }

  updateCVData(data) {
    this.lastCvData = data;
    this.lastCvTime = Date.now();
    
    let isCvFall = false;
    if (data.system_state === 'FALL_CONFIRMED' || (data.fall_score && data.fall_score >= this.CV_FALL_THRESHOLD)) {
      isCvFall = true;
      this.cvFallTime = Date.now();
      this.cvFallEventCount++;
    } else {
      // Reset consecutive counter on non-fall CV event
      this.cvFallEventCount = 0;
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
      // Only CV active: require debounced consecutive events
      if (recentCvFall && this.cvFallEventCount >= this.CV_DEBOUNCE_COUNT) {
        fallConfirmed = true;
      }
    }

    if (fallConfirmed && this.currentState !== 'FALL_CONFIRMED') {
      this.setState('FALL_CONFIRMED');
      this.triggerAlarm();
    } else if (this.currentState === 'FALL_CONFIRMED') {
      // Cooldown/Recovery: We require manual ack! Do not auto-reset if it's already confirmed.
    } else if (!fallConfirmed) {
      this.setState('NORMAL');
    }
  }

  acknowledge() {
    this.iotFallTime = 0;
    this.cvFallTime = 0;
    this.cvFallEventCount = 0;
    this.setState('NORMAL');
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
    const now = Date.now();
    // Cooldown: suppress duplicate notifications within 60s
    if (now - this.lastNotificationTime < this.NOTIFICATION_COOLDOWN_MS) {
      console.log('[DecisionEngine] Alarm suppressed (cooldown active)');
      return;
    }
    this.lastNotificationTime = now;
    
    console.log('[DecisionEngine] TRIGGERING ALARM!');
    notificationService.sendLocalNotification(
      '⚠️ CRITICAL: FALL DETECTED!',
      'Immediate attention required. Fall verified by active sensors.'
    );
  }
}

const decisionEngine = new DecisionEngine();
export default decisionEngine;

