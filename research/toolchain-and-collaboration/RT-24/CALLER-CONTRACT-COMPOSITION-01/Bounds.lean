import Std

structure CheckedBound (selected : Nat → Nat) (limit : Nat) : Prop where
  applies : ∀ input, selected input ≤ limit

theorem compose_exact_selected_provider
    (provider : Nat → Nat) (limit fee callerLimit : Nat)
    (receipt : CheckedBound provider limit)
    (permitted : limit + fee ≤ callerLimit) :
    ∀ input, provider input + fee ≤ callerLimit := by
  intro input
  exact Nat.le_trans (Nat.add_le_add_right (receipt.applies input) fee) permitted

theorem ceiling_evidence (ceiling : Nat) :
    CheckedBound (fun input => min input ceiling) ceiling := by
  constructor
  intro input
  exact Nat.min_le_right input ceiling

theorem old_bound_can_fail_after_provider_change :
    CheckedBound (fun input => min input 2) 2 ∧ ¬ CheckedBound (fun input => min input 5) 2 := by
  refine ⟨ceiling_evidence 2, ?_⟩
  intro receipt
  have invalid := receipt.applies 5
  exact (show ¬ (5 ≤ 2) by decide) invalid

#print axioms compose_exact_selected_provider
#print axioms ceiling_evidence
#print axioms old_bound_can_fail_after_provider_change
