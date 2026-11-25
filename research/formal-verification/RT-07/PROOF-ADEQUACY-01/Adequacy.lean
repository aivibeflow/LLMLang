namespace ProofAdequacy

structure Contract (Input Output : Type) where
  eligible : Input → Prop
  permits : Input → Output → Prop

def Allows (contract : Contract Input Output) (input : Input) (output : Output) : Prop :=
  contract.eligible input → contract.permits input output

def Satisfies (contract : Contract Input Output) (implementation : Input → Output) : Prop :=
  ∀ input, Allows contract input (implementation input)

def Feasible (contract : Contract Input Output) : Prop :=
  ∃ implementation, Satisfies contract implementation

theorem transfer (candidate intent : Contract Input Output)
    (pointwise : ∀ input output, Allows candidate input output → Allows intent input output)
    (implementation : Input → Output) (valid : Satisfies candidate implementation) :
    Satisfies intent implementation :=
  fun input => pointwise input (implementation input) (valid input)

theorem exactTransfer [DecidableEq Input] (candidate intent : Contract Input Output)
    (feasible : Feasible candidate) :
    (∀ implementation, Satisfies candidate implementation → Satisfies intent implementation) ↔
    (∀ input output, Allows candidate input output → Allows intent input output) := by
  constructor
  · intro universal input output allowed
    obtain ⟨base, baseValid⟩ := feasible
    let patched := fun key => if key = input then output else base key
    have patchedValid : Satisfies candidate patched := by
      intro key
      by_cases same : key = input
      · subst key
        simpa [patched] using allowed
      · simpa [patched, same] using baseValid key
    simpa [patched] using universal patched patchedValid input
  · exact transfer candidate intent

def Covers (candidate intent : Contract Input Output) : Prop :=
  ∀ input, intent.eligible input → candidate.eligible input

theorem transferWithCoverage (candidate intent : Contract Input Output)
    (coverage : Covers candidate intent)
    (preservation : ∀ input output, intent.eligible input →
        candidate.permits input output → intent.permits input output)
    (implementation : Input → Output) (valid : Satisfies candidate implementation) :
    Satisfies intent implementation :=
  fun input eligible => preservation input (implementation input) eligible
    (valid input (coverage input eligible))

def recordedIntent : Contract Bool Bool :=
  ⟨fun _ => True, fun input output => input = output⟩

def tooWeak : Contract Bool Bool :=
  ⟨fun _ => True, fun _ _ => True⟩

def narrowed : Contract Bool Bool :=
  ⟨fun input => input = false, fun input output => input = output⟩

def impossible : Contract Bool Bool :=
  ⟨fun _ => True, fun _ _ => False⟩

def constantFalse (_ : Bool) : Bool := false

theorem weakProof : Satisfies tooWeak constantFalse := fun _ _ => trivial

theorem narrowedProof : Satisfies narrowed constantFalse := fun _ h => h

theorem intentFailure : ¬ Satisfies recordedIntent constantFalse :=
  fun h => Bool.noConfusion (h true trivial)

theorem noImplementation : ¬ Feasible impossible :=
  fun ⟨_, h⟩ => h false trivial

#print axioms transfer
#print axioms exactTransfer
#print axioms transferWithCoverage
#print axioms weakProof
#print axioms narrowedProof
#print axioms intentFailure
#print axioms noImplementation

end ProofAdequacy
