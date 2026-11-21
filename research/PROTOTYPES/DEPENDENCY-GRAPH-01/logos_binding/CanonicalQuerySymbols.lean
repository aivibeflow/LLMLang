import Std.Data.String.ToNat
import PairedObservationSemantics
import RelationalSourceQuerySemantics

namespace LLMLang.CanonicalQuerySymbols

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.RelationalSourceQuerySemantics

inductive SymbolRole where
  | shared
  | left
  | right
  deriving DecidableEq

private def SymbolRole.code : SymbolRole → Nat
  | .shared => 0
  | .left => 1
  | .right => 2

structure SymbolBinding where
  declaration : Declaration
  role : SymbolRole

/-- The symbol key uses the stable declaration ID and a disjoint role tag. -/
def SymbolBinding.name (binding : SymbolBinding) : String :=
  "i_" ++ Nat.repr (3 * binding.declaration.id.value + binding.role.code)

def SymbolBinding.reference (binding : SymbolBinding) : Reference :=
  ⟨binding.name, binding.declaration.sort⟩

theorem SymbolBinding.name_key {a b : SymbolBinding} (same : a.name = b.name) :
    a.declaration.id = b.declaration.id ∧ a.role = b.role := by
  have numbers := Nat.repr_injective ((String.append_right_inj "i_").mp same)
  obtain ⟨⟨⟨aId⟩, aName, aRole, aSort⟩, aSide⟩ := a
  obtain ⟨⟨⟨bId⟩, bName, bRole, bSort⟩, bSide⟩ := b
  cases aSide <;> cases bSide <;> simp [SymbolRole.code] at numbers ⊢ <;>
    first | omega | exact congrArg VariableId.mk (by omega)

private def rolesFor (declaration : Declaration) (factor : VariableId) : List SymbolRole :=
  if declaration.id = factor then [.left, .right] else [.shared]

def symbolBindings (scope : SourceScope) (factor : VariableId) : List SymbolBinding :=
  (scope.context.entries.filter (fun declaration => decide (declaration.id ∈ scope.initialized))).flatMap
    (fun declaration => (rolesFor declaration factor).map (fun role => ⟨declaration, role⟩))

theorem mem_symbolBindings {scope : SourceScope} {factor : VariableId} {binding : SymbolBinding} :
    binding ∈ symbolBindings scope factor ↔
      binding.declaration ∈ scope.context.entries ∧ binding.declaration.id ∈ scope.initialized ∧
      binding.role ∈ rolesFor binding.declaration factor := by
  constructor
  · intro member
    obtain ⟨declaration, initialized, fromRole⟩ := List.mem_flatMap.mp member
    obtain ⟨role, allowed, rfl⟩ := List.mem_map.mp fromRole
    obtain ⟨declared, present⟩ := List.mem_filter.mp initialized
    exact ⟨declared, of_decide_eq_true present, allowed⟩
  · rintro ⟨declared, initialized, role⟩
    exact List.mem_flatMap.mpr ⟨binding.declaration,
      List.mem_filter.mpr ⟨declared, decide_eq_true initialized⟩,
      List.mem_map.mpr ⟨binding.role, role, by cases binding <;> rfl⟩⟩

theorem symbolBindings_name_unique {scope : SourceScope} {factor : VariableId}
    {a b : SymbolBinding} (valid : scope.WellFormed)
    (inA : a ∈ symbolBindings scope factor) (inB : b ∈ symbolBindings scope factor)
    (same : a.name = b.name) : a = b := by
  obtain ⟨sameId, sameRole⟩ := SymbolBinding.name_key same
  have aFound := scope.context.lookupDeclaration_of_mem valid.1 (mem_symbolBindings.mp inA).1
  have bFound := scope.context.lookupDeclaration_of_mem valid.1 (mem_symbolBindings.mp inB).1
  rw [sameId] at aFound
  have sameDeclaration := Option.some.inj (aFound.symm.trans bFound)
  cases a
  cases b
  simp_all

def bindingOnSide (declaration : Declaration) (factor : VariableId) (side : RunSide) :
    SymbolBinding :=
  ⟨declaration, if declaration.id = factor then
    (match side with | .left => .left | .right => .right)
  else .shared⟩

theorem shared_binding {declaration : Declaration} {factor : VariableId}
    (other : declaration.id ≠ factor) :
    bindingOnSide declaration factor .left = bindingOnSide declaration factor .right := by
  simp [bindingOnSide, other]

theorem factor_names_distinct {declaration : Declaration} {factor : VariableId}
    (selected : declaration.id = factor) :
    (bindingOnSide declaration factor .left).name ≠
      (bindingOnSide declaration factor .right).name := by
  intro same
  have role := (SymbolBinding.name_key same).2
  simp [bindingOnSide, selected] at role

theorem symbolBindings_names_nodup {scope : SourceScope} (valid : scope.WellFormed)
    (factor : VariableId) : ((symbolBindings scope factor).map SymbolBinding.name).Nodup := by
  unfold symbolBindings List.Nodup
  rw [List.pairwise_map, List.pairwise_flatMap]
  constructor
  · intro declaration _
    by_cases selected : declaration.id = factor
    · simpa [rolesFor, bindingOnSide, selected] using factor_names_distinct selected
    · simp [rolesFor, selected]
  · have distinct := (List.pairwise_map.mp valid.1.1).filter
      (fun declaration => decide (declaration.id ∈ scope.initialized))
    apply distinct.imp
    intro a b different left inLeft right inRight same
    obtain ⟨_, _, rfl⟩ := List.mem_map.mp inLeft
    obtain ⟨_, _, rfl⟩ := List.mem_map.mp inRight
    exact different (SymbolBinding.name_key same).1

theorem bindingOnSide_mem {scope : SourceScope} {declaration : Declaration}
    {factor : VariableId} (side : RunSide) (member : declaration ∈ scope.context.entries)
    (initialized : declaration.id ∈ scope.initialized) :
    bindingOnSide declaration factor side ∈ symbolBindings scope factor := by
  apply mem_symbolBindings.mpr
  refine ⟨member, initialized, ?_⟩
  cases side <;> by_cases chosen : declaration.id = factor <;>
    simp [bindingOnSide, rolesFor, chosen]

def DeclaredSymbols {sort : ExprSort} (bindings : List SymbolBinding) (term : QueryTerm sort) :
    Prop :=
  ∀ ref ∈ querySymbols term, ref ∈ bindings.map SymbolBinding.reference

theorem resolved_of_initialized {scope : SourceScope} {declaration : Declaration}
    (valid : scope.WellFormed) (member : declaration ∈ scope.context.entries)
    (initialized : declaration.id ∈ scope.initialized) :
    scope.resolveRead ⟨declaration.sourceName, declaration.sort⟩ = some declaration :=
  SourceScope.resolveRead_eq_some.mpr
    ⟨scope.context.lookupName_of_mem valid.1 member, rfl,
      valid.2.2.1 declaration.id initialized, initialized⟩

private def symbol (name : String) : (sort : ExprSort) → QueryTerm sort
  | .int => .symbolInt name
  | .bool => .symbolBool name

private def literalDefault : (sort : ExprSort) → QueryTerm sort
  | .int => .intLit 0
  | .bool => .boolLit false

/-- Replace a typed source spelling by its entry symbol for this run. -/
def replacement (scope : SourceScope) (factor : VariableId) (side : RunSide) : TermEnv :=
  fun name sort =>
    match scope.resolveRead ⟨name, sort⟩ with
    | none => literalDefault sort
    | some declaration => symbol (bindingOnSide declaration factor side).name sort

theorem replacement_declared (scope : SourceScope) (factor : VariableId) (side : RunSide)
    (name : String) (sort : ExprSort) :
    DeclaredSymbols (symbolBindings scope factor) (replacement scope factor side name sort) := by
  cases found : scope.resolveRead ⟨name, sort⟩ with
  | none =>
    cases sort <;> simp [replacement, found, literalDefault, DeclaredSymbols, querySymbols]
  | some declaration =>
    obtain ⟨byName, sameSort, readable⟩ := SourceScope.resolveRead_eq_some.mp found
    have member := scope.context.lookupName_mem byName
    have bound := bindingOnSide_mem (factor := factor) side member readable.2
    intro ref seen
    have sameRef : ref = (bindingOnSide declaration factor side).reference := by
      cases sort <;>
        simpa [replacement, found, symbol, querySymbols, SymbolBinding.reference, bindingOnSide,
          sameSort] using seen
    rw [sameRef]
    exact List.mem_map_of_mem bound

theorem substitute_declared {sort : ExprSort} (term : QueryTerm sort)
    {bindings : List SymbolBinding} {replace : TermEnv}
    (declared : ∀ (name : String) (sort : ExprSort), DeclaredSymbols bindings (replace name sort)) :
    DeclaredSymbols bindings (substitute replace term) := by
  induction term <;>
    simp only [DeclaredSymbols, substitute, querySymbols, List.forall_mem_append] at * <;>
    first | exact declared _ _ | simp_all

def sideValuation (scope : SourceScope) (factor : VariableId) (side : RunSide)
    (queryEnv : Env) : Env :=
  fun name sort => evalQuery (replacement scope factor side name sort) queryEnv

theorem sideValuation_slot {scope : SourceScope} {declaration : Declaration}
    (valid : scope.WellFormed) (member : declaration ∈ scope.context.entries)
    (initialized : declaration.id ∈ scope.initialized)
    (factor : VariableId) (side : RunSide) (queryEnv : Env) :
    sideValuation scope factor side queryEnv declaration.sourceName declaration.sort =
      queryEnv (bindingOnSide declaration factor side).name declaration.sort := by
  simp only [sideValuation, replacement, resolved_of_initialized valid member initialized]
  cases declaration.sort <;> rfl

/-- Every query environment induces a source pair with exactly one split slot. -/
def pairedValuations {scope : SourceScope} {factor : VariableId}
    (admitted : (resolveInputFactor scope factor).isSome = true) (queryEnv : Env) :
    PairedValuations scope factor where
  left := sideValuation scope factor .left queryEnv
  right := sideValuation scope factor .right queryEnv
  factorAdmitted := admitted
  shared := by
    obtain ⟨_, found⟩ := Option.isSome_iff_exists.mp admitted
    have valid := (resolveInputFactor_eq_some.mp found).1
    intro declaration member initialized other
    rw [sideValuation_slot valid member initialized, sideValuation_slot valid member initialized,
      shared_binding other]

/-- Looking up the name of a canonical binding recovers that exact binding. -/
theorem symbolBindings_find {scope : SourceScope} {factor : VariableId} {binding : SymbolBinding}
    (valid : scope.WellFormed) (member : binding ∈ symbolBindings scope factor) :
    (symbolBindings scope factor).find? (fun other => decide (other.name = binding.name)) =
      some binding := by
  cases found : (symbolBindings scope factor).find? (fun other => decide (other.name = binding.name)) with
  | none =>
    have present : ((symbolBindings scope factor).find?
        (fun other => decide (other.name = binding.name))).isSome = true :=
      List.find?_isSome.mpr ⟨binding, member, decide_eq_true rfl⟩
    rw [found] at present
    contradiction
  | some other =>
    have inTable := List.mem_of_find?_eq_some found
    have sameName := of_decide_eq_true (List.find?_some
      (p := fun other : SymbolBinding => decide (other.name = binding.name)) found)
    exact congrArg some (symbolBindings_name_unique valid inTable member sameName)

/-- Encode any admitted concrete pair as one valuation over the canonical symbols. -/
def valuationForPair {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) : Env :=
  fun name sort =>
    match (symbolBindings scope factor).find? (fun binding => decide (binding.name = name)) with
    | some binding =>
      match binding.role with
      | .right => pair.right binding.declaration.sourceName sort
      | .left | .shared => pair.left binding.declaration.sourceName sort
    | none => pair.left name sort

theorem sideValuation_forPair_slot {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) (side : RunSide) {declaration : Declaration}
    (member : declaration ∈ scope.context.entries) (initialized : declaration.id ∈ scope.initialized) :
    sideValuation scope factor side (valuationForPair pair) declaration.sourceName declaration.sort =
      (match side with | .left => pair.left | .right => pair.right)
        declaration.sourceName declaration.sort := by
  obtain ⟨_, found⟩ := Option.isSome_iff_exists.mp pair.factorAdmitted
  have valid := (resolveInputFactor_eq_some.mp found).1
  rw [sideValuation_slot valid member initialized]
  simp only [valuationForPair,
    symbolBindings_find valid (bindingOnSide_mem (factor := factor) side member initialized)]
  cases side with
  | left => by_cases selected : declaration.id = factor <;> simp [bindingOnSide, selected]
  | right =>
    by_cases selected : declaration.id = factor
    · simp [bindingOnSide, selected]
    · simpa [bindingOnSide, selected] using pair.shared declaration member initialized selected

private theorem initial_eq_of_slots (scope : SourceScope) {left right : Env}
    (agrees : ∀ declaration ∈ scope.context.entries, declaration.id ∈ scope.initialized →
      left declaration.sourceName declaration.sort = right declaration.sourceName declaration.sort) :
    (SymbolicState.initial scope).denote left = (SymbolicState.initial scope).denote right := by
  apply congrArg (Configuration.mk scope)
  funext id
  change ((SymbolicState.initial scope).denote left).env id =
    ((SymbolicState.initial scope).denote right).env id
  cases found : lookupDeclaration scope.context id with
  | none => simp [SymbolicState.denote, SymbolicState.initial, found]
  | some declaration =>
    by_cases initialized : id ∈ scope.initialized
    · have member : declaration ∈ scope.context.entries := List.mem_of_find?_eq_some found
      have same := agrees declaration member (lookupDeclaration_id found ▸ initialized)
      simp [SymbolicState.initial_lookup found, initialized, same]
    · simp [SymbolicState.initial_lookup found, initialized]

theorem pairedValuations_forPair_initials {scope : SourceScope} {factor : VariableId}
    (pair : PairedValuations scope factor) :
    (pairedValuations pair.factorAdmitted (valuationForPair pair)).leftInitial = pair.leftInitial ∧
    (pairedValuations pair.factorAdmitted (valuationForPair pair)).rightInitial = pair.rightInitial := by
  constructor <;> apply initial_eq_of_slots
  · intro declaration member initialized
    exact sideValuation_forPair_slot pair .left member initialized
  · intro declaration member initialized
    exact sideValuation_forPair_slot pair .right member initialized

end LLMLang.CanonicalQuerySymbols
