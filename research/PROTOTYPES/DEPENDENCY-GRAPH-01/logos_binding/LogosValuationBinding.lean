import LogosScalarPreservation

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding
open LLMLang.SourceQuerySemantics (Env)
open Smtm (SmtType)

private theorem resolveEntry {bindings : List (String × Eo.Term)} {name : String}
    {sort : QuerySort} {term : Eo.Term}
    (found : resolveQuerySymbol bindings name sort = .ok term) :
    (name, term) ∈ bindings ∧ hasExpectedSort term sort.expected = true := by
  unfold resolveQuerySymbol at found
  split at found
  · rename_i spelling entry entries
    split at found
    · rename_i valid
      simp only [pure, Except.pure, Except.ok.injEq] at found
      subst term
      have seen : (spelling, entry) ∈ bindings.filter (fun candidate => candidate.1 == name) := by
        rw [entries]
        exact List.mem_singleton_self _
      obtain ⟨present, same⟩ := List.mem_filter.mp seen
      have eq : spelling = name := eq_of_beq same
      subst spelling
      exact ⟨present, valid⟩
    · contradiction
  · contradiction
  · contradiction

private theorem mappedMember {f : α → Except String β} {source : List α} {output : List β}
    {entry : α} {converted : β} (mem : entry ∈ source) (value : f entry = .ok converted)
    (built : source.mapM f = .ok output) : converted ∈ output := by
  induction source generalizing output with
  | nil => simp at mem
  | cons head tail ih =>
      rw [List.mapM_cons] at built
      cases first : f head with
      | error _ =>
          rw [first] at built
          cases built
      | ok a =>
          rw [first] at built
          cases rest : tail.mapM f with
          | error _ =>
              rw [rest] at built
              cases built
          | ok bs =>
              rw [rest] at built
              change Except.ok (a :: bs) = Except.ok output at built
              cases built
              rcases List.mem_cons.mp mem with rfl | later
              · rw [first] at value
                cases value
                exact List.mem_cons_self
              · exact List.mem_cons_of_mem _ (ih later rest)

private theorem findValue {model : Valuation} {key : SmtEval.native_String} {value : Scalar}
    (unique : (model.map Prod.fst).Nodup) (mem : (key, value) ∈ model) :
    model.find? (fun row => row.1 == key) = some (key, value) := by
  induction model with
  | nil => simp at mem
  | cons head tail ih =>
      obtain ⟨first, rest⟩ := List.nodup_cons.mp unique
      rcases List.mem_cons.mp mem with same | later
      · subst head
        simp
      · have other : head.1 ≠ key := by
          intro same
          apply first
          rw [same]
          exact List.mem_map.mpr ⟨(key, value), later, rfl⟩
        simp [other, ih rest later]

private def smtSort : QuerySort → SmtType
  | .int => .Int
  | .bool => .Bool

private theorem bindingInterprets {name : String} {term : Eo.Term} {sort : QuerySort}
    (input : Env) (valid : hasExpectedSort term sort.expected = true) :
    ∃ key, __eo_to_smt term = .UConst key (smtSort sort) ∧
      liftBinding input (name, term) = .ok (key, fromSource (input name sort)) := by
  cases sort with
  | int =>
      have shape : ∃ id, term = .UConst id (.UOp .Int) := by
        unfold QuerySort.expected hasExpectedSort at valid
        split at valid <;> first | contradiction | exact ⟨_, rfl⟩
      obtain ⟨id, rfl⟩ := shape
      refine ⟨_, rfl, ?_⟩
      change Except.ok (Smtm.native_uconst_id id,
        Scalar.int (SourceQuerySemantics.asInt (input name .int))) = _
      cases input name .int
      rfl
  | bool =>
      have shape : ∃ id, term = .UConst id .Bool := by
        unfold QuerySort.expected hasExpectedSort at valid
        split at valid <;> first | contradiction | exact ⟨_, rfl⟩
      obtain ⟨id, rfl⟩ := shape
      refine ⟨_, rfl, ?_⟩
      change Except.ok (Smtm.native_uconst_id id,
        Scalar.bool (SourceQuerySemantics.asBool (input name .bool))) = _
      cases input name .bool
      rfl

private theorem fromSourceSort {sort : QuerySort} (value : SourceQuerySemantics.Value sort) :
    (fromSource value).sort = smtSort sort := by
  cases value <;> rfl

/-- A successful valuation lift realizes every exact name and sort resolved by Logos. -/
theorem liftValuation_corresponds {bindings : List (String × Eo.Term)} {input : Env} {model : Valuation}
    (built : liftValuation bindings input = .ok model) : Corresponds bindings input model := by
  intro name sort term resolved
  obtain ⟨present, approved⟩ := resolveEntry resolved
  obtain ⟨key, translated, mapped⟩ := bindingInterprets input approved
  unfold liftValuation at built
  cases lifted : bindings.mapM (liftBinding input) with
  | error _ =>
      rw [lifted] at built
      cases built
  | ok rows =>
      rw [lifted] at built
      change (if (rows.map Prod.fst).Nodup then .ok rows else .error "ambiguous SMT constants") =
        Except.ok model at built
      split at built
      · rename_i unique
        have seen := mappedMember present mapped lifted
        have indexed := findValue unique seen
        cases built
        rw [translated, evalSmt, indexed]
        change (if ((fromSource (input name sort)).sort == smtSort sort) = true
          then pure (fromSource (input name sort)) else throw "wrong SMT constant sort") = _
        rw [fromSourceSort]
        simp only [beq_self_eq_true, ite_true, pure, Except.pure]
      · contradiction

/-- A source expression preserves its value using the table constructed by the adapter. -/
theorem expression_preservation_lifted (bindings : List (String × Eo.Term)) (input : Env)
    {model : Valuation} (built : liftValuation bindings input = .ok model)
    {sort : QuerySort} (expr : SourceQuerySemantics.Expr sort) {term : Eo.Term}
    (compiled : renderQueryTerm bindings
      (LogosQueryAdapter.toLogosQueryTerm (SourceQuerySemantics.translateExpr expr)) = .ok term) :
    evalSmt model (__eo_to_smt term) = .ok (fromSource (SourceQuerySemantics.evalExpr expr input)) :=
  expression_preservation bindings input model (liftValuation_corresponds built) expr compiled

#print axioms liftValuation_corresponds
#print axioms expression_preservation_lifted

end LLMLang.LogosScalarDenotation
