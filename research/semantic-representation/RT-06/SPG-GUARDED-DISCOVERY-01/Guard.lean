inductive Provider where
  | alpha | beta | gamma
  deriving DecidableEq

def selected (first second input : Int) (gate : Bool) : Provider :=
  if gate then
    if input = first then .alpha else .beta
  else if input = second then .gamma else .beta

def enabled (first second input : Int) (gate : Bool) : Provider → Prop
  | .alpha => gate = true ∧ input = first
  | .gamma => gate = false ∧ input = second
  | .beta => (gate = true ∧ input ≠ first) ∨ (gate = false ∧ input ≠ second)

theorem exact_guard (first second input : Int) (gate : Bool) (provider : Provider) :
    selected first second input gate = provider ↔ enabled first second input gate provider := by
  cases gate <;> cases provider <;> simp [selected, enabled] <;> split <;> simp_all

theorem expand_guard_sound (first second input : Int) (actual : Bool) :
    ∃ gate : Bool, enabled first second input gate (selected first second input actual) :=
  ⟨actual, (exact_guard first second input actual _).mp rfl⟩

#print axioms exact_guard
#print axioms expand_guard_sound
