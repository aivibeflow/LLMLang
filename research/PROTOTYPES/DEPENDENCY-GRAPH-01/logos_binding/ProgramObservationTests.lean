import ProgramObservationSemantics

namespace LLMLang.ProgramObservationTests

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics
open LLMLang.ProgramObservationSemantics

private def input : Declaration := ⟨⟨1⟩, "n", .input, .int⟩
private def internal : Declaration := ⟨⟨2⟩, "internal", .state, .int⟩
private def score : Declaration := ⟨⟨3⟩, "score", .state, .int⟩
private def flag : Declaration := ⟨⟨4⟩, "flag", .state, .bool⟩
private def hidden : Declaration := ⟨⟨5⟩, "hidden", .state, .int⟩
private def scratch : Declaration := ⟨⟨6⟩, "scratch", .local, .int⟩

private def entry : SourceScope :=
  { context := ⟨[input, internal, score, flag, hidden, scratch]⟩
    visible := [input.id, internal.id, score.id, flag.id, scratch.id]
    initialized := [input.id, internal.id, score.id, flag.id] }

private def valuation (enabled : Bool) : Env
  | name, .int => .intValue (if name = "n" then 4 else 10)
  | _, .bool => .boolValue enabled

private def initial (enabled : Bool) : Configuration :=
  (SymbolicState.initial entry).denote (valuation enabled)

private def program (internalValue : Int) : Program .int :=
  { body := .seq
      (.branch (.boolVar "flag")
        (.seq
          (.assign (.state score.id) (.add (.intVar "score") (.intVar "n")))
          (.assign (.state flag.id) (.boolLit false)))
        (.seq
          (.assign (.state score.id) (.sub (.intVar "score") (.intVar "n")))
          (.assign (.state flag.id) (.boolLit true))))
      (.seq
        (.assign (.state internal.id) (.intLit internalValue))
        (.assign (.local scratch.id) (.add (.intVar "score") (.intLit 1))))
    result := .intVar "scratch" }

private def selected : ObservationContract := ⟨[⟨flag.id, .bool⟩, ⟨score.id, .int⟩]⟩
private def reversed : ObservationContract := ⟨[⟨score.id, .int⟩, ⟨flag.id, .bool⟩]⟩
private def returnOnly : ObservationContract := ⟨[]⟩

private def symbolicValues (program : Program .int) (contract : ObservationContract)
    (values : Env) : List (Observation Value .int contract.fields) :=
  let paths := (translateProgramObservations program contract entry).getD []
  (paths.filter (·.active values)).map (fun path => path.terms.denote values)

example : observeProgram (program 20) selected (initial true) =
    some ⟨.intValue 15, .cons (.boolValue false) (.cons (.intValue 14) .nil)⟩ := rfl
example : observeProgram (program 20) selected (initial false) =
    some ⟨.intValue 7, .cons (.boolValue true) (.cons (.intValue 6) .nil)⟩ := rfl
example : symbolicValues (program 20) selected (valuation true) =
    [⟨.intValue 15, .cons (.boolValue false) (.cons (.intValue 14) .nil)⟩] := rfl
example : symbolicValues (program 20) selected (valuation false) =
    [⟨.intValue 7, .cons (.boolValue true) (.cons (.intValue 6) .nil)⟩] := rfl
example : symbolicValues (program 20) reversed (valuation true) =
    [⟨.intValue 15, .cons (.intValue 14) (.cons (.boolValue false) .nil)⟩] := rfl
example : symbolicValues (program 20) returnOnly (valuation true) =
    [⟨.intValue 15, .nil⟩] := rfl

-- The two programs write different internal values and agree on every selected output.
example : ((program 20).execute (initial true)).bind
    (fun (final, _) => final.env.lookup internal.id .int) = some (.intValue 20) := rfl
example : ((program 30).execute (initial true)).bind
    (fun (final, _) => final.env.lookup internal.id .int) = some (.intValue 30) := rfl
example : observeProgram (program 20) selected (initial true) =
    observeProgram (program 30) selected (initial true) := rfl
example : symbolicValues (program 20) selected (valuation false) =
    symbolicValues (program 30) selected (valuation false) := rfl

example : ∃ observation,
    observeProgram (program 20) selected (initial true) = some observation ∧
    symbolicValues (program 20) selected (valuation true) = [observation] :=
  translateProgramObservations_preserves (by rfl) (valuation true)

example : (translateProgramObservations (program 20)
    ⟨[⟨score.id, .int⟩, ⟨score.id, .int⟩]⟩ entry).isNone = true := by decide
example : (translateProgramObservations (program 20) ⟨[⟨input.id, .int⟩]⟩ entry).isNone =
    true := by decide
example : (translateProgramObservations (program 20) ⟨[⟨scratch.id, .int⟩]⟩ entry).isNone =
    true := by decide
example : (translateProgramObservations (program 20) ⟨[⟨hidden.id, .int⟩]⟩ entry).isNone =
    true := by decide
example : (translateProgramObservations (program 20) ⟨[⟨⟨99⟩, .int⟩]⟩ entry).isNone =
    true := by decide
example : (translateProgramObservations (program 20) ⟨[⟨score.id, .bool⟩]⟩ entry).isNone =
    true := by decide
example : (observeProgram (program 20) ⟨[⟨flag.id, .bool⟩, ⟨flag.id, .bool⟩]⟩
    (initial false)).isNone = true := by decide

end LLMLang.ProgramObservationTests
