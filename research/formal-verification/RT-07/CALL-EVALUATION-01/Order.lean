inductive Result (α : Type) where
  | ok (value : α)
  | error (stage : Nat)

structure Observation (α : Type) where
  result : Result α
  state : Bool
  trace : List Nat

def bind (first : Observation α) (next : α → Bool → Observation β) : Observation β :=
  match first.result with
  | .error stage => ⟨.error stage, first.state, first.trace⟩
  | .ok value =>
    let second := next value first.state
    ⟨second.result, second.state, first.trace ++ second.trace⟩

def pureStep (value : α) (state : Bool) : Observation α :=
  ⟨.ok value, state, []⟩

theorem failed_prefix_stops (stage : Nat) (state : Bool) (trace : List Nat)
    (later : α → Bool → Observation β) :
    bind (⟨.error stage, state, trace⟩ : Observation α) later =
      (⟨.error stage, state, trace⟩ : Observation β) := rfl

theorem pure_total_operand_commutes (effectful : Bool → Observation α) (constant : β)
    (body : α → β → Bool → Observation γ) (state : Bool) :
    bind (effectful state) (fun left afterLeft =>
      bind (pureStep constant afterLeft) (fun right => body left right)) =
    bind (pureStep constant state) (fun right afterRight =>
      bind (effectful afterRight) (fun left => body left right)) := rfl

#print axioms failed_prefix_stops
#print axioms pure_total_operand_commutes
