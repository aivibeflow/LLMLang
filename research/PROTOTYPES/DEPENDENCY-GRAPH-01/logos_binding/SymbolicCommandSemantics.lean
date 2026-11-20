import SourceCommandSemantics

namespace LLMLang.SymbolicCommandSemantics

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics

private abbrev TermEnv := (name : String) → (sort : ExprSort) → QueryTerm sort

/-- Typed substitution in the independent query IR. Substitution retains literal multiplication. -/
private def substitute (bindings : TermEnv) : {s : ExprSort} → QueryTerm s → QueryTerm s
  | _, .intLit n => .intLit n
  | _, .boolLit b => .boolLit b
  | _, .symbolInt name => bindings name .int
  | _, .symbolBool name => bindings name .bool
  | _, .neg e => .neg (substitute bindings e)
  | _, .add a b => .add (substitute bindings a) (substitute bindings b)
  | _, .sub a b => .sub (substitute bindings a) (substitute bindings b)
  | _, .mulConst k e => .mulConst k (substitute bindings e)
  | _, .not e => .not (substitute bindings e)
  | _, .eqInt a b => .eqInt (substitute bindings a) (substitute bindings b)
  | _, .eqBool a b => .eqBool (substitute bindings a) (substitute bindings b)
  | _, .lt a b => .lt (substitute bindings a) (substitute bindings b)
  | _, .le a b => .le (substitute bindings a) (substitute bindings b)
  | _, .and a b => .and (substitute bindings a) (substitute bindings b)
  | _, .or a b => .or (substitute bindings a) (substitute bindings b)
  | _, .iteInt c a b =>
      .iteInt (substitute bindings c) (substitute bindings a) (substitute bindings b)
  | _, .iteBool c a b =>
      .iteBool (substitute bindings c) (substitute bindings a) (substitute bindings b)

private theorem eval_substitute {s : ExprSort} (term : QueryTerm s)
    (bindings : TermEnv) (valuation : Env) :
    evalQuery (substitute bindings term) valuation =
      evalQuery term (fun name sort => evalQuery (bindings name sort) valuation) := by
  induction term <;> simp [substitute, evalQuery, *]

abbrev SymbolicSlots := VariableId → Option (Σ s : ExprSort, QueryTerm s)

structure Guard where
  test : QueryTerm .bool
  expected : Bool

/-- Each path keeps its own initialized slots and the tests it took. -/
structure SymbolicState where
  scope : SourceScope
  slots : SymbolicSlots
  guards : List Guard

private def initialSymbol (name : String) : (sort : ExprSort) → QueryTerm sort
  | .int => .symbolInt name
  | .bool => .symbolBool name

/-- Seed the initialized declarations with symbols using their checked source spellings. -/
def SymbolicState.initial (scope : SourceScope) : SymbolicState :=
  { scope
    slots := fun id => do
      let declaration ← lookupDeclaration scope.context id
      if id ∈ scope.initialized then
        some ⟨declaration.sort, initialSymbol declaration.sourceName declaration.sort⟩
      else none
    guards := [] }

def SymbolicState.denote (state : SymbolicState) (valuation : Env) : Configuration :=
  { scope := state.scope
    env := fun id => (state.slots id).map (fun slot => ⟨slot.1, evalQuery slot.2 valuation⟩) }

private theorem eval_initialSymbol (name : String) (sort : ExprSort) (valuation : Env) :
    evalQuery (initialSymbol name sort) valuation = valuation name sort := by
  cases sort <;> rfl

theorem SymbolicState.initial_lookup {scope : SourceScope} {id : VariableId}
    {declaration : Declaration} (found : lookupDeclaration scope.context id = some declaration)
    (valuation : Env) :
    ((SymbolicState.initial scope).denote valuation).env id =
      if id ∈ scope.initialized then
        some ⟨declaration.sort, valuation declaration.sourceName declaration.sort⟩
      else none := by
  by_cases initialized : id ∈ scope.initialized <;>
    simp [SymbolicState.initial, SymbolicState.denote, found, initialized, eval_initialSymbol]

theorem SymbolicState.initial_valid {scope : SourceScope} (valid : scope.WellFormed)
    (valuation : Env) : ((SymbolicState.initial scope).denote valuation).Valid := by
  refine ⟨valid, ?_⟩
  intro declaration member
  have found := scope.context.lookupDeclaration_of_mem valid.1 member
  by_cases initialized : declaration.id ∈ scope.initialized <;>
    simp [SymbolicState.initial, SymbolicState.denote, found, initialized]

/-- Every satisfying runtime store is represented on the declared slots. -/
theorem SymbolicState.initial_represents {scope : SourceScope} {env : RuntimeEnv}
    (valid : scope.WellFormed) (satisfies : env.Satisfies scope) (fallback : Env) :
    (SymbolicState.initial scope).denote (extendEnvironment scope env fallback) =
      ⟨scope, fun id => (lookupDeclaration scope.context id).bind (fun _ => env id)⟩ := by
  unfold SymbolicState.denote
  congr 1
  funext id
  cases found : lookupDeclaration scope.context id with
  | none => simp [SymbolicState.initial, found]
  | some declaration =>
    have stable := lookupDeclaration_id found
    subst id
    have member : declaration ∈ scope.context.entries := List.mem_of_find?_eq_some found
    have validSlot := satisfies declaration member
    by_cases initialized : declaration.id ∈ scope.initialized
    · cases stored : env declaration.id with
      | none => simp [stored, initialized] at validSlot
      | some slot =>
        obtain ⟨sort, value⟩ := slot
        have sameSort : sort = declaration.sort := by
          simpa [stored, initialized] using validSlot
        subst sort
        have visible := valid.2.2.1 declaration.id initialized
        have resolved : scope.resolveRead ⟨declaration.sourceName, declaration.sort⟩ =
            some declaration := SourceScope.resolveRead_eq_some.mpr
          ⟨scope.context.lookupName_of_mem valid.1 member, rfl, visible, initialized⟩
        have read : env.read scope ⟨declaration.sourceName, declaration.sort⟩ = some value := by
          simp [RuntimeEnv.read, RuntimeEnv.lookup, resolved, stored]
        simp [SymbolicState.initial, found, initialized, eval_initialSymbol,
          extendEnvironment, read]
    · cases stored : env declaration.id with
      | none => simp [SymbolicState.initial, found, initialized]
      | some _ => simp [stored, initialized] at validSlot

private def SymbolicState.lookupTerm (state : SymbolicState) (id : VariableId)
    (sort : ExprSort) : Option (QueryTerm sort) := do
  let ⟨actual, term⟩ ← state.slots id
  if same : actual = sort then some (same ▸ term) else none

private theorem SymbolicState.lookupTerm_denotes (state : SymbolicState)
    (id : VariableId) (sort : ExprSort) (valuation : Env) :
    (state.lookupTerm id sort).map (fun term => evalQuery term valuation) =
      (state.denote valuation).env.lookup id sort := by
  cases stored : state.slots id with
  | none => simp [SymbolicState.lookupTerm, SymbolicState.denote, RuntimeEnv.lookup, stored]
  | some slot =>
    obtain ⟨actual, term⟩ := slot
    by_cases same : actual = sort
    · subst actual
      simp [SymbolicState.lookupTerm, SymbolicState.denote, RuntimeEnv.lookup, stored]
    · simp [SymbolicState.lookupTerm, SymbolicState.denote, RuntimeEnv.lookup, stored, same]

private def SymbolicState.readTerm (state : SymbolicState) (ref : Reference) :
    Option (QueryTerm ref.sort) := do
  let declaration ← state.scope.resolveRead ref
  state.lookupTerm declaration.id ref.sort

private theorem SymbolicState.readTerm_denotes (state : SymbolicState)
    (ref : Reference) (valuation : Env) :
    (state.readTerm ref).map (fun term => evalQuery term valuation) =
      (state.denote valuation).env.read state.scope ref := by
  cases h : state.scope.resolveRead ref with
  | none => simp [SymbolicState.readTerm, RuntimeEnv.read, h]
  | some declaration =>
    simpa [SymbolicState.readTerm, RuntimeEnv.read, h] using
      state.lookupTerm_denotes declaration.id ref.sort valuation

private def defaultTerm : (sort : ExprSort) → QueryTerm sort
  | .int => .intLit 0
  | .bool => .boolLit false

/-- Lower a slot selected by an admitted observation contract. -/
def SymbolicState.lowerSlot (state : SymbolicState) (id : VariableId)
    (sort : ExprSort) : QueryTerm sort :=
  (state.lookupTerm id sort).getD (defaultTerm sort)

theorem SymbolicState.lowerSlot_preserves_lookup {state : SymbolicState}
    {id : VariableId} {sort : ExprSort} {valuation : Env} {value : Value sort}
    (present : (state.denote valuation).env.lookup id sort = some value) :
    evalQuery (state.lowerSlot id sort) valuation = value := by
  rw [← state.lookupTerm_denotes id sort valuation] at present
  obtain ⟨term, stored, computed⟩ := Option.map_eq_some_iff.mp present
  simpa [SymbolicState.lowerSlot, stored] using computed

private def SymbolicState.bindings (state : SymbolicState) : TermEnv :=
  fun name sort => (state.readTerm ⟨name, sort⟩).getD (defaultTerm sort)

/-- Lower a checked expression in the current symbolic slots. -/
def SymbolicState.lower {s : ExprSort} (state : SymbolicState) (expr : Expr s) :
    QueryTerm s :=
  substitute state.bindings (translateExpr expr)

theorem SymbolicState.lower_preserves_eval {s : ExprSort} {state : SymbolicState}
    {valuation : Env} {expr : Expr s} {value : Value s}
    (evaluated : Evaluates state.scope (state.denote valuation).env expr value) :
    evalQuery (state.lower expr) valuation = value := by
  rw [SymbolicState.lower, eval_substitute, translateExpr_preserves_eval]
  obtain ⟨_, typed, satisfies, sourceEnv, sourceAgrees, result⟩ := evaluated
  have agrees : ExtendsReads state.scope (state.denote valuation).env expr
      (fun name sort => evalQuery (state.bindings name sort) valuation) := by
    intro ref mentioned
    obtain ⟨actual, available⟩ := RuntimeEnv.read_available typed satisfies mentioned
    rw [← state.readTerm_denotes ref valuation] at available ⊢
    obtain ⟨term, bound, _⟩ := Option.map_eq_some_iff.mp available
    cases ref
    simp [SymbolicState.bindings, bound]
  exact (evalExpr_eq_of_extensions agrees sourceAgrees).trans result

def guardsHold (guards : List Guard) (valuation : Env) : Bool :=
  guards.all (fun guard => asBool (evalQuery guard.test valuation) == guard.expected)

def SymbolicState.active (state : SymbolicState) (valuation : Env) : Bool :=
  guardsHold state.guards valuation

private def SymbolicState.assume (state : SymbolicState) (test : QueryTerm .bool)
    (expected : Bool) : SymbolicState :=
  { state with guards := ⟨test, expected⟩ :: state.guards }

private theorem SymbolicState.active_assume (state : SymbolicState)
    (test : QueryTerm .bool) (expected : Bool) (valuation : Env) :
    (state.assume test expected).active valuation =
      ((asBool (evalQuery test valuation) == expected) && state.active valuation) := rfl

private def SymbolicState.write {s : ExprSort} (state : SymbolicState)
    (target : WriteTarget) (term : QueryTerm s) : SymbolicState :=
  { state with
    scope := { state.scope with initialized := state.scope.initialized.insert target.id }
    slots := fun id => if id = target.id then some ⟨s, term⟩ else state.slots id }

private theorem SymbolicState.denote_write {s : ExprSort} (state : SymbolicState)
    (target : WriteTarget) (term : QueryTerm s) (valuation : Env) :
    (state.write target term).denote valuation =
      (state.denote valuation).write target (evalQuery term valuation) := by
  simp only [SymbolicState.denote, SymbolicState.write, Configuration.write]
  congr 1
  funext id
  by_cases same : id = target.id <;> simp [same]

/-- Symbolic execution keeps the guarded alternatives at a join. -/
private def executeSymbolically : Command → SymbolicState → List SymbolicState
  | .skip, initial => [initial]
  | .assign target expr, initial => [initial.write target (initial.lower expr)]
  | .seq first second, initial =>
      (executeSymbolically first initial).flatMap (executeSymbolically second)
  | .branch condition onTrue onFalse, initial =>
      let test := initial.lower condition
      executeSymbolically onTrue (initial.assume test true) ++
        executeSymbolically onFalse (initial.assume test false)

/-- Admit only the existing concrete checker's command fragment. -/
def translateCommands (command : Command) (scope : SourceScope) : Option (List SymbolicState) :=
  if scope.WellFormed ∧ (command.check scope).isSome = true then
    some (executeSymbolically command (SymbolicState.initial scope))
  else none

private theorem active_requires_prefix {command : Command} {initial path : SymbolicState}
    {valuation : Env} (generated : path ∈ executeSymbolically command initial)
    (active : path.active valuation = true) : initial.active valuation = true := by
  induction command generalizing initial path with
  | skip =>
    simp only [executeSymbolically, List.mem_singleton] at generated
    subst path
    exact active
  | assign target expr =>
    simp only [executeSymbolically, List.mem_singleton] at generated
    subst path
    exact active
  | seq first second firstIH secondIH =>
    obtain ⟨middle, inFirst, inSecond⟩ := List.mem_flatMap.mp generated
    exact firstIH inFirst (secondIH inSecond active)
  | branch condition onTrue onFalse trueIH falseIH =>
    rcases List.mem_append.mp generated with inTrue | inFalse
    · have branchActive := trueIH inTrue active
      simp only [SymbolicState.active_assume, Bool.and_eq_true] at branchActive
      exact branchActive.2
    · have branchActive := falseIH inFalse active
      simp only [SymbolicState.active_assume, Bool.and_eq_true] at branchActive
      exact branchActive.2

private theorem no_active_descendants (command : Command) (initial : SymbolicState)
    (valuation : Env) (inactive : initial.active valuation = false) :
    (executeSymbolically command initial).filter (·.active valuation) = [] := by
  apply List.filter_eq_nil_iff.mpr
  intro path generated active
  have initialActive := active_requires_prefix generated active
  simp [inactive] at initialActive

private theorem filter_through_sequence (command : Command) (paths : List SymbolicState)
    (valuation : Env) :
    (paths.flatMap (executeSymbolically command)).filter (·.active valuation) =
      (paths.filter (·.active valuation)).flatMap
        (fun path => (executeSymbolically command path).filter (·.active valuation)) := by
  rw [List.filter_flatMap]
  induction paths with
  | nil => rfl
  | cons path rest ih =>
    cases active : path.active valuation
    · simp [active, no_active_descendants command path valuation active, ih]
    · simp [active, ih]

private theorem lowers_concrete_expr {s : ExprSort} {state : SymbolicState}
    {valuation : Env} {initial : Configuration} {expr : Expr s} {value : Value s}
    (represents : state.denote valuation = initial)
    (evaluated : Evaluates initial.scope initial.env expr value) :
    evalQuery (state.lower expr) valuation = value := by
  subst initial
  exact SymbolicState.lower_preserves_eval evaluated

private theorem preserves_run {command : Command} {initial final : Configuration}
    (run : Executes command initial final) (valuation : Env) :
    ∀ state : SymbolicState, state.denote valuation = initial → state.active valuation = true →
      ∃ path, (executeSymbolically command state).filter (·.active valuation) = [path] ∧
        path.denote valuation = final := by
  induction run with
  | skip initial =>
    intro state represents active
    exact ⟨state, by simp [executeSymbolically, active], represents⟩
  | @assign sort target expr initial value permitted evaluated =>
    intro state represents active
    have correct := lowers_concrete_expr represents evaluated
    let path := state.write target (state.lower expr)
    have activePath : path.active valuation = true := active
    refine ⟨path, ?_, ?_⟩
    · change [path].filter (·.active valuation) = [path]
      simp [activePath]
    · unfold path
      rw [SymbolicState.denote_write, correct, represents]
  | seq _ _ firstIH secondIH =>
    intro state represents active
    obtain ⟨middle, selectedFirst, denotesMiddle⟩ := firstIH state represents active
    have activeMiddle : middle.active valuation = true := by
      have member := selectedFirst.symm ▸ List.mem_singleton_self middle
      exact (List.mem_filter.mp member).2
    obtain ⟨path, selectedSecond, denotesFinal⟩ :=
      secondIH middle denotesMiddle activeMiddle
    refine ⟨path, ?_, denotesFinal⟩
    simp only [executeSymbolically, filter_through_sequence, selectedFirst, List.flatMap_cons,
      List.flatMap_nil, List.append_nil, selectedSecond]
  | @branchTrue condition onTrue onFalse initial final tested _ ih =>
    intro state represents active
    have test := lowers_concrete_expr represents tested
    let yes := state.assume (state.lower condition) true
    let no := state.assume (state.lower condition) false
    have activeYes : yes.active valuation = true := by
      simp [yes, SymbolicState.active_assume, test, asBool, active]
    have inactiveNo : no.active valuation = false := by
      simp [no, SymbolicState.active_assume, test, asBool]
    obtain ⟨path, selected, denotesFinal⟩ := ih yes represents activeYes
    refine ⟨path, ?_, denotesFinal⟩
    change ((executeSymbolically onTrue yes) ++ (executeSymbolically onFalse no)).filter
      (·.active valuation) = [path]
    rw [List.filter_append, selected, no_active_descendants onFalse no valuation inactiveNo]
    rfl
  | @branchFalse condition onTrue onFalse initial final tested _ ih =>
    intro state represents active
    have test := lowers_concrete_expr represents tested
    let yes := state.assume (state.lower condition) true
    let no := state.assume (state.lower condition) false
    have inactiveYes : yes.active valuation = false := by
      simp [yes, SymbolicState.active_assume, test, asBool]
    have activeNo : no.active valuation = true := by
      simp [no, SymbolicState.active_assume, test, asBool, active]
    obtain ⟨path, selected, denotesFinal⟩ := ih no represents activeNo
    refine ⟨path, ?_, denotesFinal⟩
    change ((executeSymbolically onTrue yes) ++ (executeSymbolically onFalse no)).filter
      (·.active valuation) = [path]
    rw [List.filter_append, no_active_descendants onTrue yes valuation inactiveYes, selected]
    rfl

/--
SC-3 for the checked command fragment. Every valuation selects exactly one
guarded result, which denotes the entire concrete final configuration.
-/
theorem translateCommands_preserves {command : Command} {scope : SourceScope}
    {paths : List SymbolicState} (translated : translateCommands command scope = some paths)
    (valuation : Env) :
    ∃ final path, Executes command ((SymbolicState.initial scope).denote valuation) final ∧
      paths.filter (·.active valuation) = [path] ∧ path.denote valuation = final := by
  unfold translateCommands at translated
  split at translated
  · rename_i checked
    cases Option.some.inj translated
    obtain ⟨_, commandChecked⟩ := Option.isSome_iff_exists.mp checked.2
    obtain ⟨final, ran, _⟩ := Command.check_has_execution commandChecked
      ⟨rfl, rfl, fun _ member => member⟩ (SymbolicState.initial_valid checked.1 valuation)
    obtain ⟨path, active, denotesFinal⟩ := preserves_run ran valuation _ rfl rfl
    exact ⟨final, path, ran, active, denotesFinal⟩
  · contradiction

end LLMLang.SymbolicCommandSemantics
