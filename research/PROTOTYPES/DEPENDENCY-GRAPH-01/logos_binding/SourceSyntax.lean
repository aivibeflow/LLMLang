import SourceQuerySemantics

namespace LLMLang.SourceSyntax

open LLMLang.SourceQuerySemantics

/-- Stable declaration identity; source-name text is descriptive, not identity. -/
structure VariableId where
  value : Nat
  deriving DecidableEq, BEq, Repr

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

/--
A finite ordered collection of declarations. This is a data representation,
not yet a well-formedness proof: duplicate IDs/names and scope violations are
rejected by the SCW-06 validator.
-/
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

end LLMLang.SourceSyntax
