import Cpc.Api

namespace LLMLang.LogosBinding

/-- The three executable gates checked by the pinned Logos verdict. -/
def VerdictConditions (assumptions : List Eo.Term) (commands : Eo.CCmdList) : Prop :=
  Eo.logos_check_refutation assumptions commands = true ∧
    Eo.logos_check_translatableAssumptionList assumptions = true ∧
    Eo.logos_check_cmdListTranslationOk commands = true

theorem correctVerdict_conditions (assumptions : List Eo.Term) (commands : Eo.CCmdList) :
    Eo.logos_verdict assumptions commands = .correct ↔ VerdictConditions assumptions commands := by
  cases href : Eo.logos_check_refutation assumptions commands <;>
    cases hassumptions : Eo.logos_check_translatableAssumptionList assumptions <;>
    cases hcommands : Eo.logos_check_cmdListTranslationOk commands <;>
    simp [Eo.logos_verdict, VerdictConditions, href, hassumptions, hcommands]

theorem incorrectVerdict_condition (assumptions : List Eo.Term) (commands : Eo.CCmdList) :
    Eo.logos_verdict assumptions commands = .incorrect ↔
      Eo.logos_check_refutation assumptions commands = false := by
  cases href : Eo.logos_check_refutation assumptions commands <;>
    cases hassumptions : Eo.logos_check_translatableAssumptionList assumptions <;>
    cases hcommands : Eo.logos_check_cmdListTranslationOk commands <;>
    simp [Eo.logos_verdict, href, hassumptions, hcommands]

theorem incompleteVerdict_condition (assumptions : List Eo.Term) (commands : Eo.CCmdList) :
    Eo.logos_verdict assumptions commands = .incomplete ↔
      Eo.logos_check_refutation assumptions commands = true ∧
      (Eo.logos_check_translatableAssumptionList assumptions = false ∨
        Eo.logos_check_cmdListTranslationOk commands = false) := by
  cases href : Eo.logos_check_refutation assumptions commands <;>
    cases hassumptions : Eo.logos_check_translatableAssumptionList assumptions <;>
    cases hcommands : Eo.logos_check_cmdListTranslationOk commands <;>
    simp [Eo.logos_verdict, href, hassumptions, hcommands]

/-- A correct proof-file verdict binds all gates to one exact parser result. -/
theorem correctFile_conditions {proof : String}
    (accepted : Eo.logos_check_proof proof = .ok .correct) :
    ∃ assumptions commands, Eo.parseProof proof = .ok (assumptions, commands) ∧
      VerdictConditions assumptions commands := by
  unfold Eo.logos_check_proof at accepted
  cases parsed : Eo.parseProof proof with
  | error reason =>
      rw [parsed] at accepted
      cases accepted
  | ok pair =>
      obtain ⟨assumptions, commands⟩ := pair
      rw [parsed] at accepted
      change Except.ok (Eo.logos_verdict assumptions commands) = .ok .correct at accepted
      exact ⟨assumptions, commands, rfl,
        (correctVerdict_conditions assumptions commands).mp (Except.ok.inj accepted)⟩

#print axioms correctVerdict_conditions
#print axioms incorrectVerdict_condition
#print axioms incompleteVerdict_condition
#print axioms correctFile_conditions

end LLMLang.LogosBinding
