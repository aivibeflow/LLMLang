def Preserves (source target : Input → Option Observation) (domain : Input → Prop) : Prop :=
  ∀ input, domain input →
    ∃ observation, source input = some observation ∧ target input = some observation

theorem compose_passes {source middle target : Input → Option Observation}
    {leftDomain rightDomain requested : Input → Prop}
    (left : Preserves source middle leftDomain) (right : Preserves middle target rightDomain)
    (covered : ∀ input, requested input → leftDomain input ∧ rightDomain input) :
    Preserves source target requested := by
  intro input admitted
  obtain ⟨hleft, hright⟩ := covered input admitted
  obtain ⟨first, sourceFact, middleLeft⟩ := left input hleft
  obtain ⟨second, middleRight, targetFact⟩ := right input hright
  have agrees : first = second := Option.some.inj (middleLeft.symm.trans middleRight)
  exact ⟨first, sourceFact, targetFact.trans (congrArg some agrees.symm)⟩

theorem compose_with_midpoint_bridge {source first second target : Input → Option Observation}
    {domain : Input → Prop} (left : Preserves source first domain)
    (bridge : Preserves first second domain) (right : Preserves second target domain) :
    Preserves source target domain :=
  compose_passes (compose_passes left bridge (fun _ admitted => ⟨admitted, admitted⟩))
    right (fun _ admitted => ⟨admitted, admitted⟩)

theorem return_only_can_lose_trace :
    (some (false, [1, 2])).map Prod.fst = (some (false, [2, 1])).map Prod.fst ∧
      some (false, [1, 2]) ≠ some (false, [2, 1]) :=
  ⟨rfl, by decide⟩

#print axioms compose_passes
#print axioms compose_with_midpoint_bridge
#print axioms return_only_can_lose_trace
