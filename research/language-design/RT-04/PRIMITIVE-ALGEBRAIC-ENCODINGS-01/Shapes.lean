abbrev ProductFirst (α : Type) := Bool × (Unit ⊕ α)
abbrev SumFirst (α : Type) := Bool ⊕ (Bool × α)

def distribute (source : ProductFirst α) : SumFirst α :=
  match source with
  | (flag, .inl _) => .inl flag
  | (flag, .inr data) => .inr (flag, data)

def factor (source : SumFirst α) : ProductFirst α :=
  match source with
  | .inl flag => (flag, .inl ())
  | .inr (flag, data) => (flag, .inr data)

theorem factor_after_distribute (source : ProductFirst α) :
    factor (distribute source) = source := by
  cases source with
  | mk flag branch =>
    cases branch with
    | inl unitValue => cases unitValue; rfl
    | inr payload => rfl

theorem distribute_after_factor (source : SumFirst α) :
    distribute (factor source) = source := by
  cases source with
  | inl flag => rfl
  | inr branch => cases branch; rfl

def discardEmpty (value : Empty ⊕ α) : α :=
  match value with
  | .inl impossible => nomatch impossible
  | .inr payload => payload

theorem empty_has_no_branch (value : Empty ⊕ α) :
    Sum.inr (discardEmpty value) = value := by
  cases value with
  | inl impossible => nomatch impossible
  | inr payload => rfl

def decodeFlag : Nat → Option Bool
  | 0 => some false
  | 1 => some true
  | _ => none

theorem flag_roundtrip (flag : Bool) : decodeFlag (if flag then 1 else 0) = some flag := by
  cases flag <;> rfl

theorem invalid_flag (word : Nat) (bound : 2 ≤ word) : decodeFlag word = none := by
  match word with
  | 0 => omega
  | 1 => omega
  | n + 2 => rfl

#print axioms factor_after_distribute
#print axioms distribute_after_factor
#print axioms empty_has_no_branch
#print axioms flag_roundtrip
#print axioms invalid_flag
