import SourceSyntax

namespace LLMLang.SourceCoreTests

open LLMLang.SourceSyntax

private def inputDecl : Declaration := ⟨⟨1⟩, "factor", .input, .int⟩
private def localDecl : Declaration := ⟨⟨2⟩, "count", .local, .int⟩
private def stateDecl : Declaration := ⟨⟨3⟩, "enabled", .state, .bool⟩
private def hiddenDecl : Declaration := ⟨⟨4⟩, "other", .local, .bool⟩

private def entryScope : SourceScope :=
  { context := ⟨[inputDecl, localDecl, stateDecl, hiddenDecl]⟩
    visible := [inputDecl.id, localDecl.id, stateDecl.id]
    initialized := [inputDecl.id, stateDecl.id] }

example : entryScope.WellFormed := by decide

-- The duplicate keys disagree in spelling or stable identity, respectively.
example : ¬ (DeclarationContext.mk [inputDecl, { localDecl with id := inputDecl.id }]).WellFormed := by
  decide
example : ¬ (DeclarationContext.mk
    [inputDecl, { localDecl with sourceName := inputDecl.sourceName }]).WellFormed := by
  decide
example : ¬ ({ entryScope with visible := ⟨99⟩ :: entryScope.visible }).WellFormed := by decide
example : ¬ ({ entryScope with initialized := hiddenDecl.id :: entryScope.initialized }).WellFormed := by
  decide
example : ¬ ({ entryScope with initialized := [inputDecl.id] }).WellFormed := by decide
example : ¬ ({ entryScope with initialized := [stateDecl.id] }).WellFormed := by decide

example : entryScope.permits .read inputDecl.id .int = true := by decide
example : entryScope.permits .read inputDecl.id .bool = false := by decide
example : entryScope.permits .read localDecl.id .int = false := by decide
example : entryScope.permits .write localDecl.id .int = true := by decide
example : entryScope.permits .write inputDecl.id .int = false := by decide
example : entryScope.permits .write hiddenDecl.id .bool = false := by decide
example : entryScope.permits .write stateDecl.id .bool = true := by decide
example : entryScope.permits .observe stateDecl.id .bool = true := by decide
example : entryScope.permits .observe inputDecl.id .int = false := by decide

end LLMLang.SourceCoreTests
