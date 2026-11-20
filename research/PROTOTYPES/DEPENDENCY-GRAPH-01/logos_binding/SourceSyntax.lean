import SourceQuerySemantics

namespace LLMLang.SourceSyntax

open LLMLang.SourceQuerySemantics

/-- Stable declaration identity; source-name text is descriptive, not identity. -/
structure VariableId where
  value : Nat
  deriving DecidableEq, BEq, ReflBEq, LawfulBEq, Repr

/-- The role a declared variable plays in the initial source fragment. -/
inductive DeclarationRole where
  | input
  | local
  | state
  deriving DecidableEq, BEq, Repr

/-- A declaration couples identity, source spelling, role, and value sort. -/
structure Declaration where
  id : VariableId
  sourceName : String
  role : DeclarationRole
  sort : ExprSort
  deriving DecidableEq, BEq, Repr

/-- Finite declarations in source order, before context validation. -/
structure DeclarationContext where
  entries : List Declaration
  deriving DecidableEq, Repr

/-- Find a declaration by stable identity, preserving the full declaration. -/
def lookupDeclaration (context : DeclarationContext) (id : VariableId) :
    Option Declaration :=
  context.entries.find? (fun declaration => decide (declaration.id = id))

theorem lookupDeclaration_head (declaration : Declaration) (rest : List Declaration) :
    lookupDeclaration ⟨declaration :: rest⟩ declaration.id = some declaration := by
  simp [lookupDeclaration]

theorem lookupDeclaration_miss_empty (id : VariableId) :
    lookupDeclaration ⟨[]⟩ id = none := by
  rfl

/-- The fragment has a single namespace and does not permit shadowing. -/
def DeclarationContext.WellFormed (context : DeclarationContext) : Prop :=
  (context.entries.map Declaration.id).Nodup ∧
  (context.entries.map Declaration.sourceName).Nodup

instance (context : DeclarationContext) : Decidable context.WellFormed := by
  unfold DeclarationContext.WellFormed
  infer_instance

/-- Resolve the spelling in the expression AST to a declaration. -/
def DeclarationContext.lookupName (context : DeclarationContext) (name : String) :
    Option Declaration :=
  context.entries.find? (fun declaration => decide (declaration.sourceName = name))

theorem DeclarationContext.lookupName_mem {context : DeclarationContext}
    {name : String} {declaration : Declaration}
    (found : context.lookupName name = some declaration) :
    declaration ∈ context.entries :=
  List.mem_of_find?_eq_some found

theorem DeclarationContext.lookupName_spelling {context : DeclarationContext}
    {name : String} {declaration : Declaration}
    (found : context.lookupName name = some declaration) :
    declaration.sourceName = name :=
  of_decide_eq_true (List.find?_some
    (p := fun entry : Declaration => decide (entry.sourceName = name)) found)

private theorem find_unique_key {α κ : Type} [DecidableEq κ] (key : α → κ)
    {entries : List α} {entry : α}
    (unique : (entries.map key).Nodup) (member : entry ∈ entries) :
    entries.find? (fun other => decide (key other = key entry)) = some entry := by
  induction entries with
  | nil => simp at member
  | cons head rest ih =>
    rcases List.mem_cons.mp member with rfl | member
    · simp
    · have keys := List.nodup_cons.mp unique
      have different : key head ≠ key entry := by
        intro same
        apply keys.1
        rw [same]
        exact List.mem_map_of_mem member
      simpa [List.find?_cons, different] using ih keys.2 member

/-- A named reference and its stable-ID lookup select the same declaration. -/
theorem DeclarationContext.lookupName_binds_identity {context : DeclarationContext}
    {name : String} {declaration : Declaration} (wellFormed : context.WellFormed)
    (found : context.lookupName name = some declaration) :
    lookupDeclaration context declaration.id = some declaration :=
  find_unique_key Declaration.id wellFormed.1 (context.lookupName_mem found)

/-- Visibility and definite initialization at one source point. -/
structure SourceScope where
  context : DeclarationContext
  visible : List VariableId
  initialized : List VariableId

/--
The scope contains only declared IDs and initialization only covers visible
slots. Visible inputs and state regions must be supplied at entry. A visible
local can be uninitialized until its first assignment.
-/
def SourceScope.WellFormed (scope : SourceScope) : Prop :=
  scope.context.WellFormed ∧
  (∀ id ∈ scope.visible, id ∈ scope.context.entries.map Declaration.id) ∧
  (∀ id ∈ scope.initialized, id ∈ scope.visible) ∧
  (∀ declaration ∈ scope.context.entries,
    declaration.id ∈ scope.visible → declaration.role ≠ .local →
      declaration.id ∈ scope.initialized)

instance (scope : SourceScope) : Decidable scope.WellFormed := by
  letI := List.decidableBAll (fun id => id ∈ scope.context.entries.map Declaration.id)
    scope.visible
  letI := List.decidableBAll (fun id => id ∈ scope.visible) scope.initialized
  letI := List.decidableBAll (fun (declaration : Declaration) =>
    declaration.id ∈ scope.visible → declaration.role ≠ .local →
      declaration.id ∈ scope.initialized) scope.context.entries
  unfold SourceScope.WellFormed
  infer_instance

inductive SourceAccess where
  | read
  | write
  | observe

/-- Observation eligibility leaves actual state selection to the contract. -/
def SourceScope.Allows (scope : SourceScope) (access : SourceAccess)
    (declaration : Declaration) : Prop :=
  declaration.id ∈ scope.visible ∧
    match access with
    | .read => declaration.id ∈ scope.initialized
    | .write => declaration.role ≠ .input
    | .observe => declaration.role = .state ∧ declaration.id ∈ scope.initialized

instance (scope : SourceScope) (access : SourceAccess) (declaration : Declaration) :
    Decidable (scope.Allows access declaration) := by
  cases access <;> simp only [SourceScope.Allows] <;> infer_instance

/-- Check a resolved target at the declaration's sort and current source point. -/
def SourceScope.permits (scope : SourceScope) (access : SourceAccess)
    (id : VariableId) (sort : ExprSort) : Bool :=
  decide scope.WellFormed &&
    ((lookupDeclaration scope.context id).filter (fun declaration =>
      decide (declaration.sort = sort ∧ scope.Allows access declaration))).isSome

theorem SourceScope.permits_eq_true {scope : SourceScope} {access : SourceAccess}
    {id : VariableId} {sort : ExprSort} :
    scope.permits access id sort = true ↔ scope.WellFormed ∧
      ∃ declaration, lookupDeclaration scope.context id = some declaration ∧
        declaration.sort = sort ∧ scope.Allows access declaration := by
  simp only [SourceScope.permits, Bool.and_eq_true, decide_eq_true_eq, Option.isSome_iff_exists,
    Option.filter_eq_some_iff]

/-- The variables in the current expression AST carry a spelling and a sort. -/
structure Reference where
  name : String
  sort : ExprSort
  deriving DecidableEq

/-- Resolve a read in a scope whose context is validated by the caller. -/
def SourceScope.resolveRead (scope : SourceScope) (ref : Reference) : Option Declaration :=
  (scope.context.lookupName ref.name).filter (fun declaration =>
    decide (declaration.sort = ref.sort ∧ scope.Allows .read declaration))

theorem SourceScope.resolveRead_eq_some {scope : SourceScope} {ref : Reference}
    {declaration : Declaration} :
    scope.resolveRead ref = some declaration ↔
      scope.context.lookupName ref.name = some declaration ∧
      declaration.sort = ref.sort ∧ scope.Allows .read declaration := by
  simp [SourceScope.resolveRead, Option.filter_eq_some_iff]

end LLMLang.SourceSyntax
