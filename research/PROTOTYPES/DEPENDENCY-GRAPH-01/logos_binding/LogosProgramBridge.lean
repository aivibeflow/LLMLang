import LogosRenderedSorts
import LogosValuationBinding
import SourceQueryEnvelope

namespace LLMLang.LogosScalarDenotation

open LLMLang.LogosBinding (QuerySort renderQueryTerm DecodedRelationalQuery CheckedQueryAssumptions
  renderRelationalAssumptions_parts)
open LLMLang.SourceQuerySemantics
open LLMLang.LogosQueryAdapter

private def reify (rename : String → String) : {sort : QuerySort} → QueryTerm sort → Expr sort
  | .int, .intLit n => .intLit n
  | .bool, .boolLit b => .boolLit b
  | .int, .symbolInt name => .intVar (rename name)
  | .bool, .symbolBool name => .boolVar (rename name)
  | .int, .neg e => .neg (reify rename e)
  | .int, .add a b => .add (reify rename a) (reify rename b)
  | .int, .sub a b => .sub (reify rename a) (reify rename b)
  | .int, .mulConst n e => .mulConst n (reify rename e)
  | .bool, .not e => .not (reify rename e)
  | .bool, .eqInt a b => .eqInt (reify rename a) (reify rename b)
  | .bool, .eqBool a b => .eqBool (reify rename a) (reify rename b)
  | .bool, .lt a b => .lt (reify rename a) (reify rename b)
  | .bool, .le a b => .le (reify rename a) (reify rename b)
  | .bool, .and a b => .and (reify rename a) (reify rename b)
  | .bool, .or a b => .or (reify rename a) (reify rename b)
  | .int, .iteInt g a b => .iteInt (reify rename g) (reify rename a) (reify rename b)
  | .bool, .iteBool g a b => .iteBool (reify rename g) (reify rename a) (reify rename b)

private theorem renderReified (rename : String → String) {sort : QuerySort}
    (query : QueryTerm sort) :
    toLogosQueryTerm (translateExpr (reify rename query)) =
      QuerySymbolRenaming.rename rename (toLogosQueryTerm query) := by
  induction query <;>
    simp_all [reify, translateExpr, toLogosQueryTerm, QuerySymbolRenaming.rename, QuerySymbolRenaming.renameList]

private theorem evaluateReified (rename : String → String) (env : Env) {sort : QuerySort}
    (query : QueryTerm sort) :
    evalExpr (reify rename query) env = evalQuery query (QuerySymbolRenaming.pullback rename env) := by
  induction query <;>
    simp_all [reify, evalExpr, evalQuery, QuerySymbolRenaming.pullback]

theorem renamed_query_preservation (rename : String → String)
    (bindings : List (String × Eo.Term)) (env : Env)
    {model : Valuation} (built : liftValuation bindings env = .ok model)
    {sort : QuerySort} (query : QueryTerm sort) {rendered : Eo.Term}
    (hasTerm : renderQueryTerm bindings
      (QuerySymbolRenaming.rename rename (toLogosQueryTerm query)) = .ok rendered) :
    evalSmt model (__eo_to_smt rendered) =
      .ok (fromSource (evalQuery query (QuerySymbolRenaming.pullback rename env))) := by
  rw [← renderReified] at hasTerm
  exact (expression_preservation_lifted bindings env built _ hasTerm).trans
    (congrArg (fun value => Except.ok (ε := String) (fromSource value)) (evaluateReified rename env query))

open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.ProgramRelationalQuery
open LLMLang.SourceQueryEnvelope

private theorem fromBool (value : Value .bool) : fromSource value = .bool (asBool value) := by
  cases value
  rfl

/-- The conjunction of the exact parsed assumptions has the value of the source query. -/
theorem acceptedAssumptions_formulaValues {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {wire proof : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor wire = .ok decoded)
    (bound : CheckedQueryAssumptions proof decoded) (env : Env)
    {model : Valuation} (lifted : liftValuation bound.bindings env = .ok model) :
    ∃ (query : RelationalQuery scope factor) (factorChanged observationChanged : Bool),
      compileRelationalQuery program contract scope factor = some query ∧
      bound.parsed.assumptions.mapM (fun term => evalSmt model (__eo_to_smt term)) =
        .ok [.bool factorChanged, .bool observationChanged] ∧
      (factorChanged && observationChanged) =
        asBool (evalQuery query.formula (QuerySymbolRenaming.pullback (wireNames query.lower.bindings) env)) := by
  obtain ⟨query, factorQuery, observationQuery, compiled, formula, _, factorWire, observationWire⟩ :=
    sourceTypedEnvelope_parts (decodeSourceEnvelope_typed accepted).1
  obtain ⟨factorTerm, observationTerm, terms, factorRendered, observationRendered⟩ :=
    renderRelationalAssumptions_parts _ _ _ _ _ _ bound.assumptions
  rw [factorWire, wireTerm] at factorRendered
  rw [observationWire, wireTerm] at observationRendered
  have factorValue := renamed_query_preservation _ _ env lifted factorQuery factorRendered
  have observationValue := renamed_query_preservation _ _ env lifted observationQuery observationRendered
  let original := QuerySymbolRenaming.pullback (wireNames query.lower.bindings) env
  refine ⟨query, asBool (evalQuery factorQuery original), asBool (evalQuery observationQuery original),
    compiled, ?_, ?_⟩
  · rw [terms]
    simp only [List.mapM_cons, List.mapM_nil, factorValue, observationValue, fromBool]
    rfl
  · rw [formula]
    rfl

/-- The parsed ordered assumptions denote a concrete source dependence test. -/
theorem acceptedAssumptions_sourcePair {sort : QuerySort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {wire proof : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor wire = .ok decoded)
    (bound : CheckedQueryAssumptions proof decoded) (env : Env)
    {model : Valuation} (lifted : liftValuation bound.bindings env = .ok model) :
    ∃ (query : RelationalQuery scope factor) (a b : Observation Value sort contract.fields)
      (factorChanged observationChanged : Bool),
      compileRelationalQuery program contract scope factor = some query ∧
      let pair := query.inputPair (QuerySymbolRenaming.pullback (wireNames query.lower.bindings) env)
      observeConcretePair program contract pair = some (a, b) ∧
      bound.parsed.assumptions.mapM (fun term => evalSmt model (__eo_to_smt term)) =
        .ok [.bool factorChanged, .bool observationChanged] ∧
      ((factorChanged && observationChanged) = true ↔
        pair.left query.selected.sourceName query.selected.sort ≠
          pair.right query.selected.sourceName query.selected.sort ∧ a ≠ b) := by
  obtain ⟨query, factorChanged, observationChanged, compiled, ran, value⟩ :=
    acceptedAssumptions_formulaValues accepted bound env lifted
  let original := QuerySymbolRenaming.pullback (wireNames query.lower.bindings) env
  obtain ⟨a, b, observed, different⟩ := compileRelationalQuery_correct compiled original
  refine ⟨query, a, b, factorChanged, observationChanged, compiled, observed, ran, ?_⟩
  rw [value]
  exact different

#print axioms acceptedAssumptions_sourcePair

end LLMLang.LogosScalarDenotation
