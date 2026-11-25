namespace ProvidedContractIdentity

structure Contract (Input Output : Type) where
  accepts : Input → Prop
  permits : Input → Output → Prop

def satisfies (body : Input → Output) (contract : Contract Input Output) : Prop :=
  ∀ x, contract.accepts x → contract.permits x (body x)

def refines (provided required : Contract Input Output) : Prop :=
  ∀ x, required.accepts x →
    provided.accepts x ∧ ∀ y, provided.permits x y → required.permits x y

theorem twoStageAdmission (body : Input → Output) (provided required : Contract Input Output)
    (implementation : satisfies body provided) (refinement : refines provided required) :
    satisfies body required := by
  intro input accepted
  obtain ⟨domain, outputs⟩ := refinement input accepted
  exact outputs (body input) (implementation input domain)

def allowsAny : Contract Bool Bool := ⟨fun _ => True, fun _ _ => True⟩
def requiresTrue : Contract Bool Bool := ⟨fun _ => True, fun _ out => out = true⟩

theorem fixedBodyCanSatisfyOneDeclarationAndRefuteAnother :
    satisfies (fun _ => false) allowsAny ∧ ¬ satisfies (fun _ => false) requiresTrue := by
  constructor
  · exact fun _ _ => True.intro
  · intro satisfaction
    exact Bool.noConfusion (satisfaction false True.intro)

theorem sameBodyProofCannotDischargeDistinctRefinement :
    satisfies (fun _ => true) allowsAny ∧ satisfies (fun _ => true) requiresTrue ∧
      refines requiresTrue requiresTrue ∧ ¬ refines allowsAny requiresTrue := by
  refine ⟨fun _ _ => True.intro, fun _ _ => rfl, fun _ domain => ⟨domain, fun _ h => h⟩, ?_⟩
  intro refinement
  exact Bool.noConfusion ((refinement false True.intro).2 false True.intro)

#print axioms twoStageAdmission
#print axioms fixedBodyCanSatisfyOneDeclarationAndRefuteAnother
#print axioms sameBodyProofCannotDischargeDistinctRefinement

end ProvidedContractIdentity
