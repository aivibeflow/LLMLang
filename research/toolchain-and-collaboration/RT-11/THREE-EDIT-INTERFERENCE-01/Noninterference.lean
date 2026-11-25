theorem preserves_fold (observe : State → Observation) (admitted : State → Prop)
    (steps : List (State → State)) (initial : State) (initial_ok : admitted initial)
    (each : ∀ edit, edit ∈ steps → ∀ state, admitted state →
      admitted (edit state) ∧ observe (edit state) = observe state) :
    admitted (steps.foldl (fun state edit => edit state) initial) ∧
      observe (steps.foldl (fun state edit => edit state) initial) = observe initial := by
  induction steps generalizing initial with
  | nil => exact ⟨initial_ok, rfl⟩
  | cons edit steps induction =>
    have head := each edit (List.Mem.head _) initial initial_ok
    have tail := induction (edit initial) head.1
      (fun other member => each other (List.Mem.tail _ member))
    exact ⟨tail.1, tail.2.trans head.2⟩

def trigger (a b c : Bool) : Bool := a && b && c

theorem each_pair_from_baseline_preserves :
    trigger true true false = trigger false false false ∧
    trigger true false true = trigger false false false ∧
    trigger false true true = trigger false false false :=
  ⟨rfl, rfl, rfl⟩

theorem combining_all_three_changes_observation :
    trigger true true true ≠ trigger false false false := by decide

#print axioms preserves_fold
#print axioms each_pair_from_baseline_preserves
#print axioms combining_all_three_changes_observation
