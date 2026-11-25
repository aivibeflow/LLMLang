import Lean

namespace Worker

inductive Outcome where
  | ok | cancelled | ioFailure
  deriving DecidableEq, Repr

inductive Phase where
  | idle | active | revoked (owns : Bool) | known (result : Outcome) | settled (result : Outcome)
  deriving DecidableEq, Repr

inductive Request where
  | start | cancel | write (writable : Bool) | settle
  deriving DecidableEq, Repr

inductive Event where
  | started | requested | skipped | tooLate | written | writeFailed | blocked
  | settled (result : Outcome) | already (result : Outcome)
  deriving DecidableEq, Repr

structure Decision where
  phase : Phase
  event : Event
  closed : Bool
  deriving DecidableEq, Repr

def owns : Phase → Bool
  | .active | .known _ => true
  | .revoked openHandle => openHandle
  | _ => false

def revoked : Phase → Bool
  | .revoked _ | .settled .cancelled => true
  | _ => false

def attemptedWrite : Event → Bool
  | .written | .writeFailed => true
  | _ => false

def terminalReport : Event → Bool
  | .settled _ | .already _ => true
  | _ => false

def step : Phase → Request → Decision
  | .settled result, _ => ⟨.settled result, .already result, false⟩
  | .idle, .start => ⟨.active, .started, false⟩
  | .revoked hasHandle, .start => ⟨.revoked hasHandle, .skipped, false⟩
  | .idle, .cancel => ⟨.revoked false, .requested, false⟩
  | .active, .cancel => ⟨.revoked true, .requested, false⟩
  | .revoked hasHandle, .cancel => ⟨.revoked hasHandle, .requested, false⟩
  | .known result, .cancel => ⟨.known result, .tooLate, false⟩
  | .active, .write true => ⟨.known .ok, .written, false⟩
  | .active, .write false => ⟨.known .ioFailure, .writeFailed, false⟩
  | .known result, .settle => ⟨.settled result, .settled result, true⟩
  | .revoked hasHandle, .settle => ⟨.settled .cancelled, .settled .cancelled, hasHandle⟩
  | phase, _ => ⟨phase, .blocked, false⟩

theorem noWriteAfterRevocation (phase : Phase) (request : Request)
    (isRevoked : revoked phase = true) :
    revoked (step phase request).phase = true ∧
      attemptedWrite (step phase request).event = false := by
  cases phase with
  | idle => simp [revoked] at isRevoked
  | active => simp [revoked] at isRevoked
  | known _ => simp [revoked] at isRevoked
  | revoked holding => cases request <;> simp [revoked, step, attemptedWrite]
  | settled outcome => simp [step, isRevoked, attemptedWrite]

theorem terminalReportReleasesOwnership (phase : Phase) (request : Request)
    (reported : terminalReport (step phase request).event = true) :
    owns (step phase request).phase = false := by
  cases phase <;> cases request <;> simp [step, terminalReport, owns] at *
  next writable => cases writable <;> simp at reported

theorem closeLeavesTerminal (phase : Phase) (request : Request)
    (closed : (step phase request).closed = true) :
    ∃ result, (step phase request).phase = .settled result := by
  cases phase <;> cases request <;> simp [step] at *
  next writable => cases writable <;> simp at closed

theorem writeRequiresOwnership (phase : Phase) (request : Request)
    (attempted : attemptedWrite (step phase request).event = true) :
    owns phase = true := by
  cases phase <;> cases request <;> simp [step, attemptedWrite, owns] at *

theorem knownResultResistsCancel (result : Outcome) :
    step (.known result) .cancel = ⟨.known result, .tooLate, false⟩ := rfl

theorem settledIsAbsorbing (result : Outcome) (request : Request) :
    step (.settled result) request = ⟨.settled result, .already result, false⟩ := rfl

def closes : Phase → List Request → Nat
  | _, [] => 0
  | phase, request :: rest =>
    let decision := step phase request
    (if decision.closed then 1 else 0) + closes decision.phase rest

theorem settledDoesNotCloseAgain (result : Outcome) (requests : List Request) :
    closes (.settled result) requests = 0 := by
  induction requests <;> simp_all [closes, step]

theorem closesAtMostOnce (phase : Phase) (requests : List Request) :
    closes phase requests ≤ 1 := by
  induction requests generalizing phase with
  | nil => simp [closes]
  | cons first rest ih =>
    cases guard : (step phase first).closed with
    | false => simpa [closes, guard] using ih (step phase first).phase
    | true =>
      obtain ⟨result, ended⟩ := closeLeavesTerminal phase first guard
      simp [closes, guard, ended, settledDoesNotCloseAgain]

def attempts : Phase → List Request → Nat
  | _, [] => 0
  | phase, request :: rest =>
    let decision := step phase request
    (if attemptedWrite decision.event then 1 else 0) + attempts decision.phase rest

theorem revokedNeverWrites (phase : Phase) (requests : List Request) (initial : revoked phase = true) :
    attempts phase requests = 0 := by
  induction requests generalizing phase with
  | nil => rfl
  | cons first rest ih =>
    have stable := noWriteAfterRevocation phase first initial
    simp [attempts, stable.2, ih (step phase first).phase stable.1]

def update (world : Phase × Phase) (second : Bool) (request : Request) : Phase × Phase :=
  if second then (world.1, (step world.2 request).phase) else ((step world.1 request).phase, world.2)

theorem separateJobStatesCommute (world : Phase × Phase) (first second : Request) :
    update (update world false first) true second = update (update world true second) false first := rfl

def admittedOnce (phase : Phase) (request : Request) : Event :=
  match phase, request with
  | .revoked true, .write true => .written
  | _, _ => (step phase request).event

def prematureCancel (phase : Phase) : Decision := ⟨phase, .settled .cancelled, false⟩

theorem staleAdmissionCopiesARevokedWrite :
    attemptedWrite (admittedOnce (.revoked true) (.write true)) = true ∧
      attemptedWrite (step (.revoked true) (.write true)).event = false := by decide

theorem earlyTerminalLeavesOwnership :
    terminalReport (prematureCancel .active).event = true ∧
      owns (prematureCancel .active).phase = true := by decide

def outcomeName : Outcome → String
  | .ok => "ok"
  | .cancelled => "cancelled"
  | .ioFailure => "io_failure"

def eventName : Event → String
  | .started => "started"
  | .requested => "requested"
  | .skipped => "skipped"
  | .tooLate => "too_late"
  | .written => "written"
  | .writeFailed => "write_failed"
  | .blocked => "blocked"
  | .settled result => "settled_" ++ outcomeName result
  | .already result => "already_" ++ outcomeName result

def finalName : Phase → String
  | .settled result => outcomeName result
  | _ => "unsettled"

def fileByte (phase : Phase) (byte : String) : String :=
  if phase = .settled .ok then byte else ""

def summary (world : Phase × Phase) : List String × List String :=
  ([finalName world.1, finalName world.2], [fileByte world.1 "A", fileByte world.2 "B"])

def bit (flag : Bool) : String := if flag then "1" else "0"

def replay : (Phase × Phase) → List (Bool × Request) → List (String × String × Bool) ×
    (List String × List String)
  | world, [] => ([], summary world)
  | world, (second, command) :: rest =>
    let selected := if second then world.2 else world.1
    let decision := step selected command
    let after := update world second command
    let event := (eventName decision.event, bit (owns after.1) ++ bit (owns after.2), decision.closed)
    let (events, outcome) := replay after rest
    (event :: events, outcome)

#print axioms noWriteAfterRevocation
#print axioms terminalReportReleasesOwnership
#print axioms closeLeavesTerminal
#print axioms writeRequiresOwnership
#print axioms knownResultResistsCancel
#print axioms settledIsAbsorbing
#print axioms settledDoesNotCloseAgain
#print axioms closesAtMostOnce
#print axioms revokedNeverWrites
#print axioms separateJobStatesCommute
#print axioms staleAdmissionCopiesARevokedWrite
#print axioms earlyTerminalLeavesOwnership

end Worker
