import SourceCommandSemantics

namespace LLMLang.SourceCommandTests

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics

private def factor : Declaration := ⟨⟨1⟩, "factor", .input, .int⟩
private def choice : Declaration := ⟨⟨2⟩, "choice", .input, .bool⟩
private def count : Declaration := ⟨⟨3⟩, "count", .local, .int⟩
private def total : Declaration := ⟨⟨4⟩, "total", .state, .int⟩
private def flag : Declaration := ⟨⟨5⟩, "flag", .state, .bool⟩
private def hidden : Declaration := ⟨⟨6⟩, "hidden", .local, .int⟩

private def entry : SourceScope :=
  { context := ⟨[factor, choice, count, total, flag, hidden]⟩
    visible := [factor.id, choice.id, count.id, total.id, flag.id]
    initialized := [factor.id, choice.id, total.id, flag.id] }

private def initial (branch : Bool) : Configuration :=
  { scope := entry
    env := fun
      | ⟨1⟩ => some ⟨.int, .intValue 4⟩
      | ⟨2⟩ => some ⟨.bool, .boolValue branch⟩
      | ⟨4⟩ => some ⟨.int, .intValue 10⟩
      | ⟨5⟩ => some ⟨.bool, .boolValue false⟩
      | _ => none }

private def accumulate : Program .int :=
  { body := .seq
      (.branch (.boolVar "choice")
        (.assign (.local count.id) (.add (.intVar "factor") (.intLit 1)))
        (.assign (.local count.id) (.sub (.intVar "factor") (.intLit 1))))
      (.seq
        (.assign (.state total.id) (.add (.intVar "total") (.intVar "count")))
        (.assign (.local count.id) (.add (.intVar "total") (.intLit 1))))
    result := .add (.intVar "count") (.intVar "total") }

-- The second assignment reads the newly written state. The final return sees both updates.
example : (accumulate.execute (initial true)).map Prod.snd = some (.intValue 31) := rfl
example : (accumulate.execute (initial false)).map Prod.snd = some (.intValue 27) := rfl
example : (accumulate.execute (initial true)).bind
    (fun (final, _) => final.env.lookup total.id .int) = some (.intValue 15) := rfl
example : (accumulate.execute (initial false)).bind
    (fun (final, _) => final.env.lookup count.id .int) = some (.intValue 14) := rfl
example : (accumulate.execute (initial true)).bind
    (fun (final, _) => final.env.lookup factor.id .int) = some (.intValue 4) := rfl
example : (accumulate.execute (initial true)).bind
    (fun (final, _) => final.env.lookup flag.id .bool) = some (.boolValue false) := rfl
example : ∃ final result, accumulate.Executes (initial true) final result :=
  Program.checked_execution_exists (by rfl) (by decide)

private def conditional : Program .bool :=
  { body := .branch (.boolVar "choice")
      (.branch (.lt (.intLit 0) (.intVar "factor"))
        (.assign (.state flag.id) (.boolLit true))
        .skip)
      (.assign (.local count.id) (.intLit 8))
    result := .boolVar "flag" }

example : (conditional.execute (initial true)).map Prod.snd = some (.boolValue true) := rfl
example : (conditional.execute (initial false)).map Prod.snd = some (.boolValue false) := rfl
example : (conditional.execute (initial true)).bind
    (fun (final, _) => final.env.lookup count.id .int) = none := rfl
example : (conditional.execute (initial false)).bind
    (fun (final, _) => final.env.lookup count.id .int) = some (.intValue 8) := rfl
example : (conditional.check entry).map (fun exit => exit.initialized) =
    some entry.initialized := rfl

private def assignAfterJoin : Program .int :=
  { body := .seq conditional.body (.assign (.local count.id) (.intVar "total"))
    result := .intVar "count" }

example : (assignAfterJoin.execute (initial true)).map Prod.snd = some (.intValue 10) := rfl
example : (assignAfterJoin.execute (initial false)).map Prod.snd = some (.intValue 10) := rfl

-- The candidate source contract checks both arms and only trusts definite initialization at joins.
example : ((Program.mk conditional.body (.intVar "count")).execute (initial false)).isNone =
    true := by decide
example : ((Program.mk (.branch (.boolLit true) .skip
    (.assign (.state total.id) (.intVar "count"))) (.intLit 0)).check entry).isNone =
    true := by decide
example : ((Program.mk (.assign (.local count.id) (.intVar "count")) (.intLit 0)).check
    entry).isNone = true := by decide
example : ((Program.mk (.assign (.local factor.id) (.intLit 7)) (.intLit 0)).check
    entry).isNone = true := by decide
example : ((Program.mk (.assign (.state count.id) (.intLit 7)) (.intLit 0)).check
    entry).isNone = true := by decide
example : ((Program.mk (.assign (.local hidden.id) (.intLit 7)) (.intLit 0)).check
    entry).isNone = true := by decide
example : ((Program.mk (.assign (.state total.id) (.boolLit false)) (.intLit 0)).check
    entry).isNone = true := by decide
example : (accumulate.execute { initial true with env := fun _ => none }).isNone =
    true := by decide

end LLMLang.SourceCommandTests
