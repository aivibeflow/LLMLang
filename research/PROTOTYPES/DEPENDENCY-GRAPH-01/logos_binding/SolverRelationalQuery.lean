import QfLiaAdmissibility

namespace LLMLang.ProgramRelationalQuery

open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.CanonicalQuerySymbols
open LLMLang.LogosQueryAdapter
open LLMLang.LogosBinding (QueryTerm WireDeclaration)

/-- The lowered formula and its declarations, with their source bindings. -/
structure SolverRelationalQuery where
  formula : QueryTerm .bool
  bindings : List SymbolBinding
  namesNodup : (bindings.map SymbolBinding.name).Nodup
  declared : ∀ ref ∈ formula.symbols, ref ∈ bindings.map SymbolBinding.reference
  qfLia : formula.isQfLia = true

def SolverRelationalQuery.declarations (query : SolverRelationalQuery) : List WireDeclaration :=
  query.bindings.map (fun binding => ⟨binding.name, binding.declaration.sort⟩)

theorem SolverRelationalQuery.declaration_names_nodup (query : SolverRelationalQuery) :
    (query.declarations.map WireDeclaration.name).Nodup := by
  simpa only [SolverRelationalQuery.declarations, List.map_map, Function.comp_def]
    using query.namesNodup

/-- The exact sort is declared, and its name occurs once in the declaration table. -/
theorem SolverRelationalQuery.symbol_declared_once (query : SolverRelationalQuery)
    {ref : Reference} (present : ref ∈ query.formula.symbols) :
    (⟨ref.name, ref.sort⟩ : WireDeclaration) ∈ query.declarations ∧
      (query.declarations.map WireDeclaration.name).count ref.name = 1 := by
  obtain ⟨binding, member, same⟩ := List.mem_map.mp (query.declared ref present)
  have declared : (⟨ref.name, ref.sort⟩ : WireDeclaration) ∈ query.declarations := by
    rw [← same]
    exact List.mem_map_of_mem member
  exact ⟨declared, query.declaration_names_nodup.count_of_mem (List.mem_map_of_mem declared)⟩

def RelationalQuery.lower {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) : SolverRelationalQuery where
  formula := toLogosQueryTerm query.formula
  bindings := symbolBindings scope factor
  namesNodup := symbolBindings_names_nodup (resolveInputFactor_eq_some.mp query.selectedInput).1 factor
  declared := by
    rw [toLogosQueryTerm_symbols]
    exact query.declared
  qfLia := query.qfLia

theorem RelationalQuery.lower_binding_lookup {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) {binding : SymbolBinding}
    (member : binding ∈ symbolBindings scope factor) :
    query.lower.bindings.find? (fun candidate => decide (candidate.name = binding.name)) =
      some binding :=
  symbolBindings_find (resolveInputFactor_eq_some.mp query.selectedInput).1 member

/-- A symbol in the lowered formula resolves to its original source declaration and role. -/
theorem RelationalQuery.lower_symbol_binding {scope : SourceScope} {factor : VariableId}
    (query : RelationalQuery scope factor) {ref : Reference}
    (present : ref ∈ query.lower.formula.symbols) :
    ∃ binding ∈ symbolBindings scope factor, binding.reference = ref ∧
      query.lower.bindings.find? (fun candidate => decide (candidate.name = ref.name)) =
        some binding := by
  change ref ∈ (toLogosQueryTerm query.formula).symbols at present
  rw [toLogosQueryTerm_symbols] at present
  obtain ⟨binding, member, same, _⟩ := query.symbol_binding present
  refine ⟨binding, member, same, ?_⟩
  rw [← same]
  exact query.lower_binding_lookup member

end LLMLang.ProgramRelationalQuery
