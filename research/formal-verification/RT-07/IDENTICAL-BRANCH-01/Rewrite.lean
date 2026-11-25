inductive Result (α : Type) where
  | ok (value : α)
  | error | diverge | cancel

structure Observation (α : Type) where
  result : Result α
  state : Nat
  trace : List Nat

def evaluateIf (guard : Nat → Observation Bool) (yes no : Nat → Observation Nat)
    (initial : Nat) : Observation Nat :=
  let probe := guard initial
  match probe.result with
  | .ok condition =>
    let final := (if condition then yes else no) probe.state
    ⟨final.result, final.state, probe.trace ++ final.trace⟩
  | .error => ⟨.error, probe.state, probe.trace⟩
  | .diverge => ⟨.diverge, probe.state, probe.trace⟩
  | .cancel => ⟨.cancel, probe.state, probe.trace⟩

def sequenceGuard (guard : Nat → Observation Bool) (body : Nat → Observation Nat)
    (initial : Nat) : Observation Nat :=
  let probe := guard initial
  match probe.result with
  | .ok _ =>
    let final := body probe.state
    ⟨final.result, final.state, probe.trace ++ final.trace⟩
  | .error => ⟨.error, probe.state, probe.trace⟩
  | .diverge => ⟨.diverge, probe.state, probe.trace⟩
  | .cancel => ⟨.cancel, probe.state, probe.trace⟩

theorem identical_branches_preserve_guard (guard : Nat → Observation Bool)
    (body : Nat → Observation Nat) (initial : Nat) :
    evaluateIf guard body body initial = sequenceGuard guard body initial := by
  cases equation : guard initial with
  | mk result state trace =>
    cases result with
    | ok flag => cases flag <;> simp [evaluateIf, sequenceGuard, equation]
    | error | diverge | cancel => simp [evaluateIf, sequenceGuard, equation]

theorem erasure_iff_transparent (guard : Nat → Observation Bool) (initial : Nat) :
    (∀ body, sequenceGuard guard body initial = body initial) ↔
      (∃ flag, guard initial = ⟨.ok flag, initial, []⟩) := by
  constructor
  · intro erased
    have identity := erased (fun state => ⟨.ok 0, state, []⟩)
    cases equation : guard initial with
    | mk result state trace =>
      cases result with
      | ok flag =>
        have agrees : (state, trace) = (initial, []) := by
          simpa [sequenceGuard, equation] using congrArg
            (fun obs : Observation Nat => (obs.state, obs.trace)) identity
        have stateEq : state = initial := congrArg Prod.fst agrees
        have traceEq : trace = [] := congrArg Prod.snd agrees
        exact ⟨flag, by rw [stateEq, traceEq]⟩
      | error | diverge | cancel =>
        simp [sequenceGuard, equation] at identity
  · intro ⟨flag, equation⟩ body
    simp [sequenceGuard, equation]

#print axioms identical_branches_preserve_guard
#print axioms erasure_iff_transparent
