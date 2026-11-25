namespace JointContracts

structure Contract (Input Observation : Type) where
  eligible : Input → Prop
  guarantee : Input → Observation → Prop

def Allows (contract : Contract Input Observation) (input : Input) (out : Observation) : Prop :=
  contract.eligible input → contract.guarantee input out

def Satisfies (contract : Contract Input Observation) (implementation : Input → Observation) : Prop :=
  ∀ input, Allows contract input (implementation input)

def joint (contracts : List (Contract Input Observation)) : Contract Input Observation where
  eligible input := ∃ contract ∈ contracts, contract.eligible input
  guarantee input out := ∀ contract ∈ contracts, Allows contract input out

theorem jointConformance (contracts : List (Contract Input Observation))
    (implementation : Input → Observation) :
    Satisfies (joint contracts) implementation ↔
      ∀ contract ∈ contracts, Satisfies contract implementation := by
  constructor
  · intro conforms contract member input active
    exact conforms input ⟨contract, member, active⟩ contract member active
  · intro allContracts input _ contract member
    exact allContracts contract member input

theorem jointFeasibility (contracts : List (Contract Input Observation)) :
    (∃ implementation, ∀ contract ∈ contracts, Satisfies contract implementation) ↔
    (∀ input, ∃ out, ∀ contract ∈ contracts, Allows contract input out) := by
  constructor
  · rintro ⟨implementation, valid⟩ input
    exact ⟨implementation input, fun contract member => valid contract member input⟩
  · intro possible
    refine ⟨fun input => Classical.choose (possible input), ?_⟩
    intro contract member input
    exact Classical.choose_spec (possible input) contract member

def resultOnly : Contract Bool (Bool × Bool) :=
  ⟨fun _ => True, fun input observation => observation.1 = input⟩

theorem eventVariantsConform :
    Satisfies resultOnly (fun input => (input, false)) ∧
    Satisfies resultOnly (fun input => (input, true)) :=
  ⟨fun _ _ => rfl, fun _ _ => rfl⟩

theorem eventVariantsDiffer : (false, false) ≠ (false, true) := by decide

#print axioms jointConformance
#print axioms jointFeasibility
#print axioms eventVariantsConform
#print axioms eventVariantsDiffer

end JointContracts
