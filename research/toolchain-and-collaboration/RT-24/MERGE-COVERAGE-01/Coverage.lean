import Std

structure Coverage where
  scope : Nat
  source : List (Nat × Nat)
  reverse : List (Nat × List Nat)

def Clean (structural : Bool) (authority observed : Coverage) : Prop :=
  structural = true ∧
    observed.scope = authority.scope ∧
    observed.source = authority.source ∧
    observed.reverse = authority.reverse

theorem no_clean_with_missing_source (authority observed : Coverage)
    (structural : Bool) (row : Nat × Nat)
    (required : row ∈ authority.source) (omitted : row ∉ observed.source) :
    ¬ Clean structural authority observed := by
  intro accepted
  exact omitted (accepted.2.2.1.symm ▸ required)

theorem no_clean_with_missing_reverse_query (authority observed : Coverage)
    (structural : Bool) (row : Nat × List Nat)
    (required : row ∈ authority.reverse) (omitted : row ∉ observed.reverse) :
    ¬ Clean structural authority observed := by
  intro accepted
  exact omitted (accepted.2.2.2.symm ▸ required)

theorem no_clean_with_stale_scope (authority observed : Coverage)
    (structural : Bool) (stale : observed.scope ≠ authority.scope) :
    ¬ Clean structural authority observed := by
  intro accepted
  exact stale accepted.2.1

#print axioms no_clean_with_missing_source
#print axioms no_clean_with_missing_reverse_query
#print axioms no_clean_with_stale_scope
