import LogosProgramBridge

namespace LLMLang.LogosScalarDenotation

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics (querySymbols)
open LLMLang.CanonicalQuerySymbols
open LLMLang.ProgramRelationalQuery
open LLMLang.SourceQueryEnvelope

private theorem findUnique {α : Type} (key : α → String)
    {rows : List α} {item : α} (unique : (rows.map key).Nodup) (present : item ∈ rows) :
    rows.find? (fun row => key row == key item) = some item := by
  induction rows with
  | nil => simp at present
  | cons head tail ih =>
      obtain ⟨outside, internallyUnique⟩ := List.nodup_cons.mp unique
      rcases List.mem_cons.mp present with same | later
      · subst head
        simp
      · have different : key head ≠ key item := by
          intro shared
          apply outside
          rw [shared]
          exact List.mem_map.mpr ⟨item, later, rfl⟩
        simp [different, ih internallyUnique later]

private theorem evalAgrees {sort : ExprSort} (term : QueryTerm sort) (a b : Env)
    (agree : ∀ ref ∈ querySymbols term, a ref.name ref.sort = b ref.name ref.sort) :
    evalQuery term a = evalQuery term b := by
  induction term <;> simp_all [evalQuery, querySymbols]

private theorem wireRoundTrip {scope : SourceScope} {selected : VariableId}
    (compiled : RelationalQuery scope selected) (original : Env)
    (unique : (compiled.lower.bindings.map wireName).Nodup)
    {ref : Reference} (present : ref ∈ querySymbols compiled.formula) :
    QuerySymbolRenaming.pullback (wireNames compiled.lower.bindings)
      (wireValuation compiled.lower.bindings original) ref.name ref.sort = original ref.name ref.sort := by
  obtain ⟨binding, registered, exactRef, _⟩ := compiled.symbol_binding present
  have inLower : binding ∈ compiled.lower.bindings := registered
  have sourceFound := compiled.lower_binding_lookup inLower
  have wireFound := findUnique wireName unique inLower
  have predicate : (fun (row : SymbolBinding) => row.name == binding.name) =
      fun row => decide (row.name = binding.name) := by
    funext row
    by_cases same : row.name = binding.name <;> simp [same]
  have spell : wireNames compiled.lower.bindings binding.name = wireName binding := by
    unfold wireNames
    rw [predicate, sourceFound]
    rfl
  rw [← exactRef]
  change wireValuation compiled.lower.bindings original
    (wireNames compiled.lower.bindings binding.name) binding.declaration.sort = _
  simp [wireValuation, spell, wireFound, SymbolBinding.reference]

theorem wireValuation_preservesFormula {scope : SourceScope} {selected : VariableId}
    (compiled : RelationalQuery scope selected) (original : Env)
    (unique : (compiled.lower.bindings.map wireName).Nodup) :
    evalQuery compiled.formula (QuerySymbolRenaming.pullback (wireNames compiled.lower.bindings)
      (wireValuation compiled.lower.bindings original)) = evalQuery compiled.formula original :=
  evalAgrees _ _ _ (fun _ present => wireRoundTrip compiled original unique present)

open LLMLang.LogosBinding (DecodedRelationalQuery CheckedQueryAssumptions)
open LLMLang.SourceCommandSemantics (Program)
open LLMLang.ProgramObservationSemantics (ObservationContract Observation)
open LLMLang.PairedObservationSemantics (PairedValuations observeConcretePair)

/-- The source-owned wire valuation represents the dependence test for any admitted concrete pair. -/
theorem acceptedAssumptions_forConcretePair {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    {wire proof : String} {decoded : DecodedRelationalQuery}
    (accepted : decodeSourceEnvelope program contract scope factor wire = .ok decoded)
    (bound : CheckedQueryAssumptions proof decoded) (pair : PairedValuations scope factor)
    {earlier : Env} {previous : Valuation}
    (validated : liftValuation bound.bindings earlier = .ok previous) :
    ∃ (model : Valuation) (a b : Observation Value sort contract.fields)
      (factorChanged observationChanged : Bool),
      liftValuation bound.bindings (wireValuation query.lower.bindings (valuationForPair pair)) =
        .ok model ∧
      observeConcretePair program contract pair = some (a, b) ∧
      bound.parsed.assumptions.mapM (fun term => evalSmt model (__eo_to_smt term)) =
        .ok [.bool factorChanged, .bool observationChanged] ∧
      ((factorChanged && observationChanged) = true ↔
        pair.left query.selected.sourceName query.selected.sort ≠
          pair.right query.selected.sourceName query.selected.sort ∧ a ≠ b) := by
  obtain ⟨admitted, _, _, admittedCompiled, _, unique, _, _⟩ :=
    sourceTypedEnvelope_parts (decodeSourceEnvelope_typed accepted).1
  have same := Option.some.inj (admittedCompiled.symm.trans compiled)
  subst admitted
  let wireEnv := wireValuation query.lower.bindings (valuationForPair pair)
  obtain ⟨model, lifted, _⟩ := liftValuation_revalues validated wireEnv
  obtain ⟨wireQuery, factorChanged, observationChanged, compiledWire, ran, value⟩ :=
    acceptedAssumptions_formulaValues accepted bound wireEnv lifted
  have sameQuery := Option.some.inj (compiledWire.symm.trans compiled)
  subst wireQuery
  obtain ⟨a, b, observations, dependence⟩ := compileRelationalQuery_forPair compiled pair
  refine ⟨model, a, b, factorChanged, observationChanged, lifted, observations, ran, ?_⟩
  rw [value]
  change asBool (evalQuery query.formula (QuerySymbolRenaming.pullback (wireNames query.lower.bindings)
    (wireValuation query.lower.bindings (valuationForPair pair)))) = true ↔ _
  rw [wireValuation_preservesFormula query _ unique]
  exact dependence

#print axioms liftValuation_revalues
#print axioms wireValuation_preservesFormula
#print axioms acceptedAssumptions_forConcretePair

end LLMLang.LogosScalarDenotation
