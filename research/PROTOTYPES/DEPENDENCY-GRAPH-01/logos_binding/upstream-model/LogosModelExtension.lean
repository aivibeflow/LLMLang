import LogosUpstreamScalarModel
import Cpc.Proofs.TypePreservation.Nonvacuity

namespace LLMLang.LogosScalarDenotation

open Smtm

/-- Overlay resolved scalar constants while retaining all unrelated model entries. -/
noncomputable def extendModel (base : SmtModel) (valuation : Valuation) : SmtModel :=
  { base with values := fun key =>
      if key.isVar then base.values key
      else
        match valuation.find? (fun row => row.1 == key.name) with
        | none => base.values key
        | some (_, value) => if value.sort = key.ty then value.embed else base.values key }

private theorem embedSort (value : Scalar) : __smtx_typeof_value value.embed = value.sort := by
  cases value <;> rfl

private theorem embedCanonical (domain : SmtUSortDom) (value : Scalar) :
    __smtx_value_canonical domain value.embed = true := by
  cases value <;> rfl

private theorem extendKey (base : SmtModel) (wellFormed : model_wf base)
    (valuation : Valuation) (isVar : Bool) (name : SmtEval.native_String) (sort : SmtType)
    (typed : __smtx_type_wf sort = true) :
    let key : SmtModelKey := ⟨isVar, name, sort⟩
    __smtx_typeof_value ((extendModel base valuation).values key) = sort ∧
      __smtx_value_canonical base.usortDom ((extendModel base valuation).values key) = true := by
  have original := And.intro (wellFormed.1 isVar name sort typed) (wellFormed.2.1 isVar name sort typed)
  cases isVar
  · cases found : valuation.find? (fun row => row.1 == name) with
    | none => simpa [extendModel, found] using original
    | some row =>
        rcases row with ⟨key, value⟩
        by_cases valid : value.sort = sort
        · simp [extendModel, found, valid, embedSort, embedCanonical]
        · simpa [extendModel, found, valid] using original
  · exact original

theorem extendModel_wellFormed (base : SmtModel) (wellFormed : model_wf base) (valuation : Valuation) :
    model_wf (extendModel base valuation) := by
  refine ⟨?_, ?_, wellFormed.2.2.1, wellFormed.2.2.2⟩
  · intro isVar key sort typed
    exact (extendKey base wellFormed valuation isVar key sort typed).1
  · intro isVar key sort typed
    exact (extendKey base wellFormed valuation isVar key sort typed).2

theorem extendModel_agrees (base : SmtModel) (valuation : Valuation) :
    modelAgrees (extendModel base valuation) valuation := by
  intro name row found
  rcases row with ⟨key, value⟩
  simp [native_model_lookup, model_key, extendModel, found]

theorem extendModel_preserves_variables (base : SmtModel) (valuation : Valuation)
    (name : SmtEval.native_String) (sort : SmtType) :
    native_model_var_lookup (extendModel base valuation) name sort = native_model_var_lookup base name sort := rfl

theorem exists_wellFormed_agreeing_model (valuation : Valuation) :
    ∃ model, model_wf model ∧ modelAgrees model valuation := by
  obtain ⟨base, wellFormed⟩ := model_wf_nonvacuous
  exact ⟨extendModel base valuation, extendModel_wellFormed base wellFormed valuation,
    extendModel_agrees base valuation⟩

private noncomputable def nameOnly (base : SmtModel) (name : SmtEval.native_String) : SmtModel :=
  { base with values := fun key =>
      if !key.isVar && key.name == name then .Numeral 7 else base.values key }

/-- Giving a Boolean key the integer bound to the same name makes the model ill-formed. -/
theorem nameOnly_breaks_model_typing (base : SmtModel) (name : SmtEval.native_String) :
    ¬ model_wf (nameOnly base name) := by
  intro wellFormed
  have booleanWF : __smtx_type_wf .Bool = true := by
    simp [__smtx_type_wf, __smtx_type_wf_component, __smtx_type_wf_rec,
      SmtEval.native_and]
  have matched := wellFormed.1 false name .Bool booleanWF
  simp [nameOnly, __smtx_typeof_value] at matched

theorem emptyRegexCanonical_kernel :
    __smtx_re_canonical native_re_none = true := rfl

#print axioms extendModel_wellFormed
#print axioms extendModel_agrees
#print axioms exists_wellFormed_agreeing_model
#print axioms nameOnly_breaks_model_typing
#print axioms emptyRegexCanonical_kernel

end LLMLang.LogosScalarDenotation
