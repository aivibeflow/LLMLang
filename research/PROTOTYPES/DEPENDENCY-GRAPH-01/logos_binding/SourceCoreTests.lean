import CheckedSourceSemantics

namespace LLMLang.SourceCoreTests

open LLMLang.SourceSyntax
open LLMLang.SourceQuerySemantics
open LLMLang.CheckedSourceSemantics

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

private def entryEnv : RuntimeEnv
  | ⟨1⟩ => some ⟨.int, .intValue 4⟩
  | ⟨3⟩ => some ⟨.bool, .boolValue true⟩
  | _ => none

private def expression : Expr .int :=
  .iteInt (.boolVar "enabled") (.add (.mulConst 2 (.intVar "factor")) (.intLit 1)) (.intLit 0)

example : entryEnv.Satisfies entryScope := by decide
example : checkedTranslate entryScope expression = some (translateExpr expression) := rfl
example : evaluateChecked entryScope entryEnv expression = some (.intValue 9) := rfl
example : evaluateChecked entryScope entryEnv (.eqInt expression (.intLit 9)) =
    some (.boolValue true) := rfl

private def otherDefaults : Env
  | _, .int => .intValue (-100)
  | _, .bool => .boolValue false

example :
    evalQuery (translateExpr expression) (extendEnvironment entryScope entryEnv otherDefaults) =
      .intValue 9 :=
  checkedTranslate_preserves_evaluation (by rfl)
    (evaluateChecked_eq_some.mp (by rfl : evaluateChecked entryScope entryEnv expression = _))
    (extendEnvironment_agrees (by decide) (by decide) otherDefaults)

example : (checkedTranslate entryScope (.intVar "missing")).isNone = true := by decide
example : (checkedTranslate entryScope (.intVar "enabled")).isNone = true := by decide
example : (checkedTranslate entryScope (.boolVar "other")).isNone = true := by decide
example : (checkedTranslate entryScope
    (.iteInt (.boolLit true) (.intVar "factor") (.intVar "count"))).isNone = true := by decide

private def wrongSortEnv : RuntimeEnv
  | ⟨1⟩ => some ⟨.bool, .boolValue false⟩
  | other => entryEnv other

example : (evaluateChecked entryScope wrongSortEnv expression).isNone = true := by decide
example : (evaluateChecked entryScope (fun _ => none) (.intLit 7)).isNone = true := by decide

private def localEnv : RuntimeEnv
  | ⟨2⟩ => some ⟨.int, .intValue 17⟩
  | other => entryEnv other

example : (evaluateChecked entryScope localEnv (.intVar "count")).isNone = true := by decide
example : evaluateChecked
    { entryScope with initialized := localDecl.id :: entryScope.initialized }
    localEnv (.intVar "count") = some (.intValue 17) := rfl

end LLMLang.SourceCoreTests
