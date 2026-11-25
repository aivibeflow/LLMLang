def Covers {Input Outcome : Type} (active : Input → Prop) (layer : Input → Outcome → Prop) : Prop :=
  ∀ x, active x → ∃ y, layer x y

def Refines {Input Outcome : Type} (active : Input → Prop)
    (lower upper : Input → Outcome → Prop) : Prop :=
  ∀ x y, active x → lower x y → upper x y

theorem refinementsCompose {Input Outcome : Type} {active : Input → Prop}
    {spec design implementation : Input → Outcome → Prop}
    (left : Refines active design spec) (right : Refines active implementation design) :
    Refines active implementation spec :=
  fun x y covered result => left x y covered (right x y covered result)

theorem lowerCoverageTransfers {Input Outcome : Type} {active : Input → Prop}
    {upper lower : Input → Outcome → Prop} (refines : Refines active lower upper)
    (coverage : Covers active lower) : Covers active upper := by
  intro x accessible
  obtain ⟨y, result⟩ := coverage x accessible
  exact ⟨y, refines x y accessible result⟩

def sameSide (x y : Bool) : Prop := x = y
def oppositeSide (x y : Bool) : Prop := x = !y
def activeBool (_ : Bool) : Prop := True
def emptyLayer (_ _ : Bool) : Prop := False

theorem sameProjectedOutcomes (y : Bool) :
    (∃ x, sameSide x y) ↔ (∃ x, oppositeSide x y) := by
  exact ⟨fun _ => ⟨!y, rfl⟩, fun _ => ⟨y, rfl⟩⟩

theorem projectionMissesWrongInput : ¬ Refines activeBool oppositeSide sameSide := by
  intro assumed
  have wrong : false = true := assumed false true True.intro rfl
  cases wrong

theorem emptyRefinementWithoutCoverage :
    Refines activeBool emptyLayer sameSide ∧ ¬ Covers activeBool emptyLayer := by
  constructor
  · intro _ _ _ impossible
    exact False.elim impossible
  · intro assumed
    obtain ⟨_, impossible⟩ := assumed false True.intro
    exact impossible

#print axioms refinementsCompose
#print axioms lowerCoverageTransfers
#print axioms sameProjectedOutcomes
#print axioms projectionMissesWrongInput
#print axioms emptyRefinementWithoutCoverage
