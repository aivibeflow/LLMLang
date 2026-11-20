import CanonicalQuerySymbols

namespace LLMLang.ProgramRelationalQuery

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.RelationalSourceQuerySemantics
open LLMLang.CanonicalQuerySymbols

private def guardFormula : List Guard → QueryTerm .bool
  | [] => .boolLit true
  | guard :: rest =>
    .and (if guard.expected then guard.test else .not guard.test) (guardFormula rest)

private theorem eval_guardFormula (guards : List Guard) (valuation : Env) :
    asBool (evalQuery (guardFormula guards) valuation) = guardsHold guards valuation := by
  induction guards with
  | nil => rfl
  | cons guard rest ih =>
    cases guard with
    | mk test expected =>
      change (asBool (evalQuery (if expected then test else .not test) valuation) &&
        asBool (evalQuery (guardFormula rest) valuation)) =
        ((asBool (evalQuery test valuation) == expected) && guardsHold rest valuation)
      rw [ih]
      cases expected <;> simp [evalQuery, asBool]

private def chooseTerm (guard : QueryTerm .bool) :
    (sort : ExprSort) → QueryTerm sort → QueryTerm sort → QueryTerm sort
  | .int, yes, no => .iteInt guard yes no
  | .bool, yes, no => .iteBool guard yes no

private theorem eval_chooseTerm {sort : ExprSort} (guard : QueryTerm .bool)
    (yes no : QueryTerm sort) (valuation : Env) :
    evalQuery (chooseTerm guard sort yes no) valuation =
      if asBool (evalQuery guard valuation) then evalQuery yes valuation else evalQuery no valuation := by
  cases sort <;> rfl

private def chooseFields (guard : QueryTerm .bool) :
    {fields : List StateField} →
    StateValues QueryTerm fields → StateValues QueryTerm fields → StateValues QueryTerm fields
  | _, .nil, .nil => .nil
  | _, .cons (field := field) yes ys, .cons no ns =>
    .cons (chooseTerm guard field.sort yes no) (chooseFields guard ys ns)

private theorem eval_chooseFields (guard : QueryTerm .bool) (valuation : Env)
    {fields : List StateField} (yes no : StateValues QueryTerm fields) :
    (chooseFields guard yes no).denote valuation =
      if asBool (evalQuery guard valuation) then yes.denote valuation else no.denote valuation := by
  induction yes with
  | nil => cases no; simp [chooseFields, StateValues.denote]
  | cons v rest ih =>
    cases no
    cases test : asBool (evalQuery guard valuation) <;>
      simp [chooseFields, StateValues.denote, eval_chooseTerm, ih, test]

private def chooseObservation {sort : ExprSort} {fields : List StateField}
    (guard : QueryTerm .bool) (yes no : Observation QueryTerm sort fields) :
    Observation QueryTerm sort fields :=
  ⟨chooseTerm guard sort yes.returned no.returned, chooseFields guard yes.state no.state⟩

private theorem eval_chooseObservation {sort : ExprSort} {fields : List StateField}
    (guard : QueryTerm .bool) (yes no : Observation QueryTerm sort fields) (valuation : Env) :
    (chooseObservation guard yes no).denote valuation =
      if asBool (evalQuery guard valuation) then yes.denote valuation else no.denote valuation := by
  cases test : asBool (evalQuery guard valuation) <;>
    simp [chooseObservation, Observation.denote, eval_chooseTerm, eval_chooseFields, test]

private def defaultTerm : (sort : ExprSort) → QueryTerm sort
  | .int => .intLit 0
  | .bool => .boolLit false

private def defaultFields : (fields : List StateField) → StateValues QueryTerm fields
  | [] => .nil
  | field :: rest => .cons (defaultTerm field.sort) (defaultFields rest)

/-- Merge guarded alternatives at every observation slot using a typed conditional. -/
private def mergeObservations {sort : ExprSort} {fields : List StateField} :
    List (ObservationPath sort fields) → Observation QueryTerm sort fields
  | [] => ⟨defaultTerm sort, defaultFields fields⟩
  | path :: rest =>
    chooseObservation (guardFormula path.guards) path.terms (mergeObservations rest)

private theorem eval_mergeObservations {sort : ExprSort} {fields : List StateField}
    (paths : List (ObservationPath sort fields)) (valuation : Env)
    {value : Observation Value sort fields} {rest : List (Observation Value sort fields)}
    (selected : (paths.filter (·.active valuation)).map (fun path => path.terms.denote valuation) =
      value :: rest) :
    (mergeObservations paths).denote valuation = value := by
  induction paths with
  | nil => contradiction
  | cons path tail ih =>
    simp only [mergeObservations, eval_chooseObservation, eval_guardFormula]
    change (if path.active valuation then path.terms.denote valuation else
      (mergeObservations tail).denote valuation) = value
    cases active : path.active valuation
    · simp only [List.filter_cons, active, Bool.false_eq_true, ↓reduceIte] at selected
      simpa only [active, Bool.false_eq_true, ↓reduceIte] using ih selected
    · simp [active] at selected
      simpa only [active, ↓reduceIte] using selected.1

private structure BoundTerm (table : List SymbolBinding) (sort : ExprSort) where
  term : QueryTerm sort
  declared : DeclaredSymbols table term

private def BoundTerm.no {table : List SymbolBinding} : BoundTerm table .bool :=
  ⟨.boolLit false, by simp [DeclaredSymbols, querySymbols]⟩

private def BoundTerm.and {table : List SymbolBinding} (left right : BoundTerm table .bool) :
    BoundTerm table .bool :=
  ⟨.and left.term right.term, by
    simpa only [DeclaredSymbols, querySymbols, List.forall_mem_append] using
      And.intro left.declared right.declared⟩

private def BoundTerm.or {table : List SymbolBinding} (left right : BoundTerm table .bool) :
    BoundTerm table .bool :=
  ⟨.or left.term right.term, by
    simpa only [DeclaredSymbols, querySymbols, List.forall_mem_append] using
      And.intro left.declared right.declared⟩

private def BoundTerm.ne {table : List SymbolBinding} {sort : ExprSort}
    (left right : BoundTerm table sort) : BoundTerm table .bool :=
  ⟨observationDifference sort left.term right.term, by
    cases sort <;>
      simpa only [observationDifference, querySortOf, DeclaredSymbols, querySymbols,
        List.forall_mem_append] using And.intro left.declared right.declared⟩

private theorem eval_ne {table : List SymbolBinding} {sort : ExprSort}
    (left right : BoundTerm table sort) (valuation : Env) :
    asBool (evalQuery (left.ne right).term valuation) = true ↔
      evalQuery left.term valuation ≠ evalQuery right.term valuation := by
  cases sort
  · simp only [BoundTerm.ne, observationDifference, evalQuery, asBool]
    cases evalQuery left.term valuation
    cases evalQuery right.term valuation
    rw [Bool.not_eq_true', ne_eq, Value.intValue.injEq]
    exact decide_eq_false_iff_not
  · simp only [BoundTerm.ne, observationDifference, evalQuery, asBool]
    cases evalQuery left.term valuation
    cases evalQuery right.term valuation
    rw [Bool.not_eq_true', ne_eq, Value.boolValue.injEq]
    exact decide_eq_false_iff_not

private def rename {sort : ExprSort} (scope : SourceScope) (factor : VariableId)
    (side : RunSide) (term : QueryTerm sort) : BoundTerm (symbolBindings scope factor) sort :=
  ⟨substitute (replacement scope factor side) term,
    substitute_declared term (replacement_declared scope factor side)⟩

private theorem eval_rename {sort : ExprSort} (scope : SourceScope) (factor : VariableId)
    (side : RunSide) (term : QueryTerm sort) (valuation : Env) :
    evalQuery (rename scope factor side term).term valuation =
      evalQuery term (sideValuation scope factor side valuation) :=
  eval_substitute term (replacement scope factor side) valuation

private def fieldsDiffer (scope : SourceScope) (factor : VariableId) :
    {fields : List StateField} →
    StateValues QueryTerm fields → StateValues QueryTerm fields →
      BoundTerm (symbolBindings scope factor) .bool
  | _, .nil, .nil => .no
  | _, .cons left ls, .cons right rs =>
    ((rename scope factor .left left).ne (rename scope factor .right right)).or
      (fieldsDiffer scope factor ls rs)

private theorem eval_fieldsDiffer (scope : SourceScope) (factor : VariableId)
    (valuation : Env) {fields : List StateField} (left right : StateValues QueryTerm fields) :
    asBool (evalQuery (fieldsDiffer scope factor left right).term valuation) = true ↔
      left.denote (sideValuation scope factor .left valuation) ≠
        right.denote (sideValuation scope factor .right valuation) := by
  induction left with
  | nil => cases right; simp [fieldsDiffer, BoundTerm.no, StateValues.denote, evalQuery, asBool]
  | cons term tail ih =>
    cases right with
    | cons right rest =>
      change (asBool (evalQuery ((rename scope factor .left term).ne
        (rename scope factor .right right)).term valuation) ||
        asBool (evalQuery (fieldsDiffer scope factor tail rest).term valuation)) = true ↔ _
      simp only [Bool.or_eq_true, eval_ne, eval_rename, ih, StateValues.denote,
        ne_eq, StateValues.cons.injEq, Classical.not_and_iff_not_or_not]

private def observationsDiffer {sort : ExprSort} {fields : List StateField}
    (scope : SourceScope) (factor : VariableId)
    (left right : Observation QueryTerm sort fields) : BoundTerm (symbolBindings scope factor) .bool :=
  ((rename scope factor .left left.returned).ne (rename scope factor .right right.returned)).or
    (fieldsDiffer scope factor left.state right.state)

private theorem eval_observationsDiffer {sort : ExprSort} {fields : List StateField}
    (scope : SourceScope) (factor : VariableId) (valuation : Env)
    (left right : Observation QueryTerm sort fields) :
    asBool (evalQuery (observationsDiffer scope factor left right).term valuation) = true ↔
      left.denote (sideValuation scope factor .left valuation) ≠
        right.denote (sideValuation scope factor .right valuation) := by
  change (asBool (evalQuery ((rename scope factor .left left.returned).ne
    (rename scope factor .right right.returned)).term valuation) ||
    asBool (evalQuery (fieldsDiffer scope factor left.state right.state).term valuation)) = true ↔ _
  simp only [Bool.or_eq_true, eval_ne, eval_rename, eval_fieldsDiffer,
    Observation.denote, ne_eq, Observation.mk.injEq, Classical.not_and_iff_not_or_not]

private def sourceSymbol (declaration : Declaration) : QueryTerm declaration.sort :=
  match declaration.sort with
  | .int => .symbolInt declaration.sourceName
  | .bool => .symbolBool declaration.sourceName

private theorem eval_sourceSymbol (declaration : Declaration) (valuation : Env) :
    evalQuery (sourceSymbol declaration) valuation =
      valuation declaration.sourceName declaration.sort := by
  cases declaration with
  | mk id name role sort => cases sort <;> rfl

private def buildFormula {sort : ExprSort} {fields : List StateField}
    (scope : SourceScope) (factor : VariableId) (selected : Declaration)
    (paths : List (ObservationPath sort fields)) : BoundTerm (symbolBindings scope factor) .bool :=
  let term := sourceSymbol selected
  let observation := mergeObservations paths
  ((rename scope factor .left term).ne (rename scope factor .right term)).and
    (observationsDiffer scope factor observation observation)

structure RelationalQuery (scope : SourceScope) (factor : VariableId) where
  selected : Declaration
  selectedInput : resolveInputFactor scope factor = some selected
  formula : QueryTerm .bool
  declared : DeclaredSymbols (symbolBindings scope factor) formula

def compileRelationalQuery {sort : ExprSort} (program : Program sort) (contract : ObservationContract)
    (scope : SourceScope) (factor : VariableId) : Option (RelationalQuery scope factor) :=
  match selected : resolveInputFactor scope factor with
  | none => none
  | some declaration => do
    let paths ← translateProgramObservations program contract scope
    let bound := buildFormula scope factor declaration paths
    pure ⟨declaration, selected, bound.term, bound.declared⟩

def RelationalQuery.inputPair {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) (valuation : Env) : PairedValuations scope factor :=
  pairedValuations (by simp [query.selectedInput]) valuation

/-- A program and factor admitted by the source checker always give a formula. -/
theorem compileRelationalQuery_exists {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope exit : SourceScope} {factor : VariableId}
    (checked : checkObservedProgram program contract scope = some exit)
    (selected : (resolveInputFactor scope factor).isSome = true) :
    ∃ query, compileRelationalQuery program contract scope factor = some query := by
  obtain ⟨declaration, found⟩ := Option.isSome_iff_exists.mp selected
  obtain ⟨paths, translated⟩ := translateProgramObservations_exists checked
  let bound := buildFormula scope factor declaration paths
  refine ⟨⟨declaration, found, bound.term, bound.declared⟩, ?_⟩
  unfold compileRelationalQuery
  split
  · rename_i missing
    rw [found] at missing
    contradiction
  · rename_i chosen resolved
    have same := Option.some.inj (resolved.symm.trans found)
    subst chosen
    simp only [translated]
    rfl

/-- Every emitted symbol resolves to one declaration with its declared sort. -/
theorem RelationalQuery.symbol_binding {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) {ref : Reference} (present : ref ∈ querySymbols query.formula) :
    ∃ binding, binding ∈ symbolBindings scope factor ∧ binding.reference = ref ∧
      ∀ other ∈ symbolBindings scope factor, other.name = ref.name → other = binding := by
  obtain ⟨binding, inTable, reference⟩ := List.mem_map.mp (query.declared ref present)
  refine ⟨binding, inTable, reference, ?_⟩
  intro other otherIn same
  apply symbolBindings_name_unique (resolveInputFactor_eq_some.mp query.selectedInput).1 otherIn inTable
  rw [same, ← reference]
  rfl

/-- SC-6 connects one canonical query to the two concrete observations. -/
theorem compileRelationalQuery_correct {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    (valuation : Env) :
    ∃ left right,
      observeConcretePair program contract (query.inputPair valuation) = some (left, right) ∧
      (asBool (evalQuery query.formula valuation) = true ↔
        (query.inputPair valuation).left query.selected.sourceName query.selected.sort ≠
          (query.inputPair valuation).right query.selected.sourceName query.selected.sort ∧
        left ≠ right) := by
  unfold compileRelationalQuery at compiled
  split at compiled
  · contradiction
  · rename_i declaration found
    obtain ⟨paths, translated, produced⟩ := Option.bind_eq_some_iff.mp compiled
    cases Option.some.inj produced
    obtain ⟨left, ranLeft, activeLeft⟩ := translateProgramObservations_preserves translated
      (sideValuation scope factor .left valuation)
    obtain ⟨right, ranRight, activeRight⟩ := translateProgramObservations_preserves translated
      (sideValuation scope factor .right valuation)
    have mergedLeft := eval_mergeObservations paths _ activeLeft
    have mergedRight := eval_mergeObservations paths _ activeRight
    refine ⟨left, right, ?_, ?_⟩
    · simp [observeConcretePair, RelationalQuery.inputPair, pairedValuations,
        PairedValuations.leftInitial, PairedValuations.rightInitial, ranLeft, ranRight]
    · change (asBool (evalQuery
        ((rename scope factor .left (sourceSymbol declaration)).ne
          (rename scope factor .right (sourceSymbol declaration))).term valuation) &&
        asBool (evalQuery (observationsDiffer scope factor (mergeObservations paths)
          (mergeObservations paths)).term valuation)) = true ↔ _
      simp only [Bool.and_eq_true, eval_observationsDiffer, eval_ne, eval_rename,
        eval_sourceSymbol, mergedLeft, mergedRight, RelationalQuery.inputPair, pairedValuations]

/-- Encoding an admitted pair preserves the observations and the factor values. -/
theorem compileRelationalQuery_forPair {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query)
    (pair : PairedValuations scope factor) :
    ∃ left right,
      observeConcretePair program contract pair = some (left, right) ∧
      (asBool (evalQuery query.formula (valuationForPair pair)) = true ↔
        pair.left query.selected.sourceName query.selected.sort ≠
          pair.right query.selected.sourceName query.selected.sort ∧ left ≠ right) := by
  obtain ⟨left, right, observed, different⟩ :=
    compileRelationalQuery_correct compiled (valuationForPair pair)
  obtain ⟨sameLeft, sameRight⟩ := pairedValuations_forPair_initials pair
  obtain ⟨_, found, _, readable⟩ := resolveInputFactor_eq_some.mp query.selectedInput
  have member : query.selected ∈ scope.context.entries := List.mem_of_find?_eq_some found
  refine ⟨left, right, ?_, ?_⟩
  · simpa only [observeConcretePair, RelationalQuery.inputPair, sameLeft, sameRight] using observed
  · simpa only [RelationalQuery.inputPair, pairedValuations,
      sideValuation_forPair_slot pair .left member readable.2,
      sideValuation_forPair_slot pair .right member readable.2] using different

/-- Query satisfiability is equivalent to the existence of a concrete dependence witness. -/
theorem compileRelationalQuery_satisfiable_iff {sort : ExprSort} {program : Program sort}
    {contract : ObservationContract} {scope : SourceScope} {factor : VariableId}
    {query : RelationalQuery scope factor}
    (compiled : compileRelationalQuery program contract scope factor = some query) :
    (∃ valuation, asBool (evalQuery query.formula valuation) = true) ↔
      ∃ (pair : PairedValuations scope factor) (left right : Observation Value sort contract.fields),
        observeConcretePair program contract pair = some (left, right) ∧
        pair.left query.selected.sourceName query.selected.sort ≠
          pair.right query.selected.sourceName query.selected.sort ∧ left ≠ right := by
  constructor
  · rintro ⟨valuation, holds⟩
    obtain ⟨left, right, observed, different⟩ := compileRelationalQuery_correct compiled valuation
    exact ⟨query.inputPair valuation, left, right, observed, different.mp holds⟩
  · rintro ⟨pair, left, right, observed, factorDiff, observationDiff⟩
    obtain ⟨_, _, actual, different⟩ := compileRelationalQuery_forPair compiled pair
    rw [observed] at actual
    cases Option.some.inj actual
    exact ⟨valuationForPair pair, different.mpr ⟨factorDiff, observationDiff⟩⟩

end LLMLang.ProgramRelationalQuery
