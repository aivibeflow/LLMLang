def Admitted (input : Option Bool) (choice : Bool) : Prop :=
  match input with
  | none => True
  | some value => value = choice

def OneChoice (input : Option Bool) (output : Bool × Bool) : Prop :=
  ∃ bit, Admitted input bit ∧ output = (bit, !bit)

def TwoChoices (input : Option Bool) (output : Bool × Bool) : Prop :=
  ∃ left right, Admitted input left ∧ Admitted input right ∧ output = (left, !right)

def Pin (input : Option Bool) (output : Bool × Bool) : Prop :=
  output = (input.getD false, !(input.getD false))

theorem stable_refines_independent (input : Option Bool) (output : Bool × Bool) :
    OneChoice input output → TwoChoices input output := by
  intro ⟨bit, good, result⟩
  exact ⟨bit, bit, good, good, result⟩

theorem pin_refines_stable (input : Option Bool) (output : Bool × Bool) :
    Pin input output → OneChoice input output := by
  intro pinned
  exact ⟨input.getD false, by cases input <;> first | trivial | rfl, pinned⟩

theorem independent_can_break_stability :
    TwoChoices none (false, false) ∧ ¬ OneChoice none (false, false) := by
  refine ⟨⟨false, true, trivial, trivial, rfl⟩, ?_⟩
  intro ⟨bit, _, result⟩
  cases bit <;> contradiction

theorem stable_can_exceed_pin :
    OneChoice none (true, false) ∧ ¬ Pin none (true, false) := by
  exact ⟨⟨true, trivial, rfl⟩, by intro impossible; unfold Pin at impossible; contradiction⟩

#print axioms stable_refines_independent
#print axioms pin_refines_stable
#print axioms independent_can_break_stability
#print axioms stable_can_exceed_pin
