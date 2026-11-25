import Lean

namespace LLMLang.RequirementCoverage

theorem checkedRequirementsCompose {R X : Type} (active recorded : R → Prop)
    (permits : R → X → Prop) (design implementation : X → Prop)
    (covered : ∀ r, active r → recorded r)
    (checked : ∀ r, recorded r → ∀ x, design x → permits r x)
    (implementsDesign : ∀ x, implementation x → design x) :
    ∀ x, implementation x → ∀ r, active r → permits r x :=
  fun x implemented r required =>
    checked r (covered r required) x (implementsDesign x implemented)

theorem nonemptyDesignSuppliesSharedWitness {R X : Type} (active : R → Prop)
    (permits : R → X → Prop) (design : X → Prop)
    (checked : ∀ r, active r → ∀ x, design x → permits r x)
    (feasible : ∃ x, design x) :
    ∃ x, (∀ r, active r → permits r x) := by
  obtain ⟨x, hx⟩ := feasible
  exact ⟨x, fun r hr => checked r hr x hx⟩

theorem localWitnessesCanDisagree :
    ∃ permits : Bool → Bool → Prop,
      (∀ r, ∃ x, permits r x) ∧ ¬ (∃ x, ∀ r, permits r x) := by
  refine ⟨fun r x => x = r, fun r => ⟨r, rfl⟩, ?_⟩
  rintro ⟨x, hx⟩
  have both : false = true := (hx false).symm.trans (hx true)
  cases both

theorem omittingAnActiveRequirementCanHideFailure :
    ∃ (active recorded : Bool → Prop) (permits : Bool → Bool → Prop),
      (∀ r x, recorded r → permits r x) ∧
      (∃ r x, active r ∧ ¬ permits r x) := by
  refine ⟨fun _ => True, fun r => r = false, fun r _ => r = false, ?_, ?_⟩
  · exact fun _ _ h => h
  · refine ⟨true, true, trivial, ?_⟩
    intro h
    cases h

#print axioms checkedRequirementsCompose
#print axioms nonemptyDesignSuppliesSharedWitness
#print axioms localWitnessesCanDisagree
#print axioms omittingAnActiveRequirementCanHideFailure

end LLMLang.RequirementCoverage
