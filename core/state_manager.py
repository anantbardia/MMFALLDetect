from enum import Enum
import time
from typing import List, Dict, Any

class SystemState(Enum):
    NORMAL = "NORMAL"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    FALL_CONFIRMED = "FALL_CONFIRMED"
    MEDICAL_ALERT = "MEDICAL_ALERT"
    ALERT_SENT = "ALERT_SENT"
    RECOVERY = "RECOVERY"

class StateManager:
    """
    Manages system state transitions for a monitored patient.
    Tracks full transition history with timestamps and reasons.
    Enforces valid state transitions per the system state machine (spec §11).
    """
    
    # Valid transitions: current_state -> set of allowed next states
    VALID_TRANSITIONS = {
        SystemState.NORMAL: {SystemState.POSSIBLE_FALL, SystemState.FALL_CONFIRMED},
        SystemState.POSSIBLE_FALL: {SystemState.NORMAL, SystemState.FALL_CONFIRMED},
        SystemState.FALL_CONFIRMED: {SystemState.MEDICAL_ALERT, SystemState.ALERT_SENT, SystemState.RECOVERY, SystemState.NORMAL},
        SystemState.MEDICAL_ALERT: {SystemState.ALERT_SENT, SystemState.RECOVERY, SystemState.NORMAL},
        SystemState.ALERT_SENT: {SystemState.RECOVERY, SystemState.NORMAL},
        SystemState.RECOVERY: {SystemState.NORMAL},
    }
    
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        self.state = SystemState.NORMAL
        self.last_transition_time = time.time()
        self.transition_history: List[Dict[str, Any]] = []
        
    def transition_to(self, new_state: SystemState, reason: str = "") -> bool:
        """Attempt a state transition. Returns True if successful."""
        if self.state == new_state:
            return False
        
        # Validate transition is allowed
        allowed = self.VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            print(f"[{self.patient_id}] BLOCKED: {self.state.value} -> {new_state.value} (not a valid transition)")
            return False
            
        old_state = self.state
        self.state = new_state
        now = time.time()
        
        # Record transition in history
        record = {
            "timestamp": now,
            "from_state": old_state.value,
            "to_state": new_state.value,
            "reason": reason,
            "duration_in_previous": round(now - self.last_transition_time, 2),
        }
        self.transition_history.append(record)
        self.last_transition_time = now
        
        print(f"[{self.patient_id}] State Change: {old_state.value} -> {new_state.value} | Reason: {reason}")
        return True
    
    def reset_to_normal(self, reason: str = "Manual reset") -> bool:
        """Go through RECOVERY -> NORMAL sequence."""
        if self.state in (SystemState.ALERT_SENT, SystemState.FALL_CONFIRMED):
            self.transition_to(SystemState.RECOVERY, reason)
        if self.state == SystemState.RECOVERY:
            return self.transition_to(SystemState.NORMAL, "Recovery complete")
        # Direct reset from ALERT_SENT
        if self.state == SystemState.ALERT_SENT:
            return self.transition_to(SystemState.NORMAL, reason)
        return False
        
    def get_current_state(self) -> str:
        return self.state.value
    
    def get_recent_history(self, count: int = 20) -> List[Dict[str, Any]]:
        """Return the last N state transitions."""
        return self.transition_history[-count:]
