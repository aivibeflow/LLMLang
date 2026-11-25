namespace CheckedTransfer

theorem reuseByImplication {α : Type}
    (before after stronger weaker : α → Prop)
    (strengthen : ∀ value, stronger value → before value)
    (checked : ∀ value, before value → after value)
    (weaken : ∀ value, after value → weaker value) :
    ∀ value, stronger value → weaker value :=
  fun value premise => weaken value (checked value (strengthen value premise))

theorem transferUnsatCore {α : Type}
    (core stronger : α → Prop)
    (coreUnsat : ∀ value, core value → False)
    (entailsCore : ∀ value, stronger value → core value) :
    ∀ value, stronger value → False :=
  fun value premise => coreUnsat value (entailsCore value premise)

theorem boundedObligation (n : Nat) (requested : n = 3 ∧ n ≠ 0) : n ≤ 5 :=
  reuseByImplication (fun value : Nat => value = 3) (fun value => value ≤ 4)
    (fun value => value = 3 ∧ value ≠ 0) (fun value => value ≤ 5)
    (fun _ premise => premise.1)
    (fun _ premise => premise.symm ▸ Nat.le.step (Nat.le_refl 3))
    (fun _ upper => Nat.le.step upper) n requested

end CheckedTransfer

#print axioms CheckedTransfer.reuseByImplication
#print axioms CheckedTransfer.transferUnsatCore
#print axioms CheckedTransfer.boundedObligation
