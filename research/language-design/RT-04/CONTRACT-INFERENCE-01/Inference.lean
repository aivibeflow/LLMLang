namespace ContractInference

def Compatible (recorded : Input → Bool) (projection : Observation → Seen)
    (anchor : Input → Observation) (input : Input) (out : Observation) : Prop :=
  recorded input = true → projection out = projection (anchor input)

def Agrees (recorded : Input → Bool) (projection : Observation → Seen)
    (anchor candidate : Input → Observation) : Prop :=
  ∀ input, Compatible recorded projection anchor input (candidate input)

theorem exactInference [DecidableEq Input] (recorded : Input → Bool)
    (projection : Observation → Seen) (anchor : Input → Observation)
    (property : Input → Observation → Prop) :
    (∀ candidate, Agrees recorded projection anchor candidate →
      ∀ input, property input (candidate input)) ↔
    (∀ input out, Compatible recorded projection anchor input out → property input out) := by
  constructor
  · intro forced input out compatible
    let replacement := fun key => if key = input then out else anchor key
    have consistent : Agrees recorded projection anchor replacement := by
      intro key
      by_cases same : key = input
      · subst key
        simpa [replacement] using compatible
      · simp [Compatible, replacement, same]
    simpa [replacement] using forced replacement consistent input
  · intro forced candidate agrees input
    exact forced input (candidate input) (agrees input)

theorem fullObservationsDetermineFunction (anchor candidate : Input → Observation)
    (agree : Agrees (fun _ => true) id anchor candidate) : candidate = anchor :=
  funext fun input => agree input rfl

def valueOnly (observation : Bool × Bool) : Bool :=
  observation.1

theorem fullValueProjectionDoesNotDetermineEffects :
    Agrees (fun _ => true) valueOnly (fun input => (input, false)) (fun input => (input, true)) ∧
      (false, true) ≠ (false, false) :=
  ⟨fun _ _ => rfl, by decide⟩

#print axioms exactInference
#print axioms fullObservationsDetermineFunction
#print axioms fullValueProjectionDoesNotDetermineEffects

end ContractInference
