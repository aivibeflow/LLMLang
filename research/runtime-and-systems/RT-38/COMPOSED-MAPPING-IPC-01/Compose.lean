namespace Combined

structure State where
  task : Nat
  frame : Mapping.Frame
  endpoint : Endpoint.State

def publishedFor (task : Nat) (frame : Mapping.Frame) : Bool :=
  match frame with
  | .owned lease .published => lease.owner == task
  | _ => false

def needsMapping : Endpoint.Phase → Prop
  | .ready _ => False
  | .running _ | .waiting _ => True

def invariant (state : State) : Prop :=
  Endpoint.invariant state.endpoint ∧
    (needsMapping state.endpoint.phase → publishedFor state.task state.frame = true)

def suspend (state : Endpoint.State) : Endpoint.State :=
  Endpoint.step (Endpoint.step state .preempt) .revoke

def changeFrame (state : State) (action : Mapping.Action) : State :=
  let current := Mapping.operate state.frame action
  { state with
    frame := current
    endpoint := if publishedFor state.task current then state.endpoint else suspend state.endpoint }

def dispatch (state : State) (lease : Mapping.Handle) (action : Endpoint.Action) : State :=
  if state.frame = .owned lease .published ∧ lease.owner = state.task then
    { state with endpoint := Endpoint.step state.endpoint action }
  else state

theorem suspended_has_no_active_waiter_or_runner (endpoint : Endpoint.State) :
    ¬ needsMapping (suspend endpoint).phase := by
  cases endpoint with
  | mk generation active phase =>
    cases phase <;> simp [suspend, Endpoint.step, needsMapping]

theorem frame_change_preserves_joint_invariant (state : State) (action : Mapping.Action)
    (wellFormed : invariant state) : invariant (changeFrame state action) := by
  unfold changeFrame invariant
  by_cases live : publishedFor state.task (Mapping.operate state.frame action) = true
  · simp [live, wellFormed.1]
  · simp [live]
    exact ⟨Endpoint.step_preserves_waiter _ _ (Endpoint.step_preserves_waiter _ _ wellFormed.1),
      suspended_has_no_active_waiter_or_runner state.endpoint⟩

theorem endpoint_change_preserves_joint_invariant (state : State) (lease : Mapping.Handle)
    (action : Endpoint.Action) (wellFormed : invariant state) :
    invariant (dispatch state lease action) := by
  unfold dispatch
  split
  next admitted =>
    obtain ⟨frame, owner⟩ := admitted
    exact ⟨Endpoint.step_preserves_waiter _ _ wellFormed.1,
      fun _ => by simp [publishedFor, frame, owner]⟩
  next => exact wellFormed

theorem stale_frame_lease_refuses_dispatch (state : State) (lease : Mapping.Handle)
    (action : Endpoint.Action) (stale : state.frame ≠ .owned lease .published) :
    dispatch state lease action = state := by
  simp [dispatch, stale]

theorem detaching_cancels_waiting_receiver (lease : Mapping.Handle) (generation : Nat) :
    changeFrame ⟨lease.owner, .owned lease .published, ⟨generation, true, .waiting generation⟩⟩
      (.detach lease) =
        ⟨lease.owner, .owned lease .revoking, ⟨generation, false, .ready (some .cancelled)⟩⟩ := by
  simp [changeFrame, Mapping.operate, publishedFor, suspend, Endpoint.step]

#print axioms suspended_has_no_active_waiter_or_runner
#print axioms frame_change_preserves_joint_invariant
#print axioms endpoint_change_preserves_joint_invariant
#print axioms stale_frame_lease_refuses_dispatch
#print axioms detaching_cancels_waiting_receiver

end Combined
