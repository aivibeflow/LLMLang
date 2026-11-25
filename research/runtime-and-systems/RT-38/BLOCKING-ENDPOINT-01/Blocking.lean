inductive Completion where
  | message (payload : Nat)
  | cancelled

inductive Phase where
  | ready (completion : Option Completion)
  | running (completion : Option Completion)
  | waiting (generation : Nat)

structure State where
  generation : Nat
  active : Bool
  phase : Phase

inductive Action where
  | schedule
  | preempt
  | block (generation : Nat)
  | send (generation payload : Nat)
  | consume
  | revoke
  | regrant

def step (state : State) (action : Action) : State :=
  match action, state.phase with
  | .schedule, .ready completion => { state with phase := .running completion }
  | .preempt, .running completion => { state with phase := .ready completion }
  | .block presented, .running none =>
    if state.active = true ∧ presented = state.generation then
      { state with phase := .waiting presented }
    else state
  | .send presented payload, .waiting waitingFor =>
    if state.active = true ∧ presented = state.generation ∧ waitingFor = presented then
      { state with phase := .ready (some (.message payload)) }
    else state
  | .consume, .running (some _) => { state with phase := .running none }
  | .revoke, .waiting _ => { state with active := false, phase := .ready (some .cancelled) }
  | .revoke, _ => { state with active := false }
  | .regrant, .ready _ | .regrant, .running _ =>
    if state.active then state else { state with active := true, generation := state.generation + 1 }
  | _, _ => state

def invariant (state : State) : Prop :=
  match state.phase with
  | .waiting generation => state.active = true ∧ generation = state.generation
  | _ => True

theorem step_preserves_waiter (state : State) (action : Action) (valid : invariant state) :
    invariant (step state action) := by
  cases state with
  | mk generation active phase =>
    cases action <;> cases phase <;> simp [invariant, step] at * <;> try assumption
    case mk.block.running presented completion =>
      cases completion with
      | none =>
        by_cases allowed : active = true ∧ presented = generation <;> simp [allowed]
      | some reply => simp
    case mk.consume.running completion => cases completion <;> simp
    case mk.send.waiting presented payload waiter =>
      obtain ⟨rfl, rfl⟩ := valid
      by_cases allowed : presented = waiter
      · subst presented
        simp
      · simp [allowed]
    case mk.regrant.ready completion => cases active <;> simp
    case mk.regrant.running completion => cases active <;> simp

theorem old_generation_does_not_deliver (state : State) (presented payload : Nat)
    (old : presented ≠ state.generation) : step state (.send presented payload) = state := by
  cases state with
  | mk generation active phase =>
    cases phase <;> simp [step, old] at *

theorem waiting_send_wakes_once (generation payload : Nat) :
    step ⟨generation, true, .waiting generation⟩ (.send generation payload) =
      ⟨generation, true, .ready (some (.message payload))⟩ ∧
    step ⟨generation, true, .ready (some (.message payload))⟩ (.send generation payload) =
      ⟨generation, true, .ready (some (.message payload))⟩ := by
  simp [step]

theorem revoke_cancels_waiting (generation : Nat) :
    step ⟨generation, true, .waiting generation⟩ .revoke =
      ⟨generation, false, .ready (some .cancelled)⟩ := by
  rfl

#print axioms step_preserves_waiter
#print axioms old_generation_does_not_deliver
#print axioms waiting_send_wakes_once
#print axioms revoke_cancels_waiting
