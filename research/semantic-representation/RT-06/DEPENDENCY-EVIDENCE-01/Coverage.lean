namespace ScopedDependency

def reachable {Target : Type} (dispatch : Bool → Option Target) (scope : Bool → Prop)
    (target : Target) : Prop :=
  ∃ input, scope input ∧ dispatch input = some target

theorem observed_implies_reachable {Target : Type} (dispatch : Bool → Option Target)
    (scope : Bool → Prop) (target : Target) (input : Bool)
    (admitted : scope input) (witness : dispatch input = some target) :
    reachable dispatch scope target :=
  ⟨input, admitted, witness⟩

theorem upper_bound_exclusion {Target : Type} (dispatch : Bool → Option Target)
    (scope : Bool → Prop) (inUpperBound : Target → Prop) (target : Target)
    (coverage : ∀ value, reachable dispatch scope value → inUpperBound value)
    (excluded : ¬ inUpperBound target) :
    ¬ reachable dispatch scope target :=
  fun witness => excluded (coverage target witness)

theorem exact_boolean_absence {Target : Type} (dispatch : Bool → Option Target)
    (scope : Bool → Prop) (target : Target) :
    ¬ reachable dispatch scope target ↔
      (scope false → dispatch false ≠ some target) ∧
      (scope true → dispatch true ≠ some target) := by
  constructor
  · intro absent
    exact ⟨fun admitted found => absent ⟨false, admitted, found⟩,
           fun admitted found => absent ⟨true, admitted, found⟩⟩
  · intro each ⟨input, admitted, found⟩
    cases input
    · exact each.1 admitted found
    · exact each.2 admitted found

#print axioms observed_implies_reachable
#print axioms upper_bound_exclusion
#print axioms exact_boolean_absence

end ScopedDependency
