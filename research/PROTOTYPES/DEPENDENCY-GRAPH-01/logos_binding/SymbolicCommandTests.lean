import SymbolicCommandSemantics

namespace LLMLang.SymbolicCommandTests

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.CheckedSourceSemantics
open LLMLang.SourceCommandSemantics
open LLMLang.SymbolicCommandSemantics

private def input : Declaration := ⟨⟨1⟩, "n", .input, .int⟩
private def flag : Declaration := ⟨⟨2⟩, "flag", .state, .bool⟩
private def counter : Declaration := ⟨⟨3⟩, "counter", .state, .int⟩
private def scratch : Declaration := ⟨⟨4⟩, "scratch", .local, .int⟩

private def entry : SourceScope :=
  { context := ⟨[input, flag, counter, scratch]⟩
    visible := [input.id, flag.id, counter.id, scratch.id]
    initialized := [input.id, flag.id, counter.id] }

private def valuation (enabled : Bool) (n : Int) : Env
  | name, .int => .intValue (if name = "n" then n else 10)
  | _, .bool => .boolValue enabled

-- The first branch changes the flag used by the next test. Its own guard
-- still denotes the entry flag. The nested branch can initialize a local.
private def nested : Command :=
  .seq
    (.branch (.boolVar "flag")
      (.seq
        (.assign (.state counter.id) (.add (.intVar "counter") (.intVar "n")))
        (.assign (.state flag.id) (.boolLit false)))
      .skip)
    (.branch (.boolVar "flag")
      (.assign (.state counter.id) (.intLit 99))
      (.branch (.lt (.intVar "n") (.intLit 0))
        (.assign (.local scratch.id) (.intLit (-6)))
        (.assign (.state counter.id) (.add (.intVar "counter") (.intLit 1)))))

private def paths (command : Command) : List SymbolicState :=
  (translateCommands command entry).getD []

private def activePaths (command : Command) (values : Env) : List SymbolicState :=
  (paths command).filter (·.active values)

private def activeSlot {s : ExprSort} (command : Command) (values : Env) (id : VariableId) :
    List (Option (Value s)) :=
  (activePaths command values).map (fun path => (path.denote values).env.lookup id s)

example : (paths nested).length = 6 := rfl
example : (activePaths nested (valuation true 4)).map (·.guards.length) = [3] := rfl
example : (activePaths nested (valuation false (-2))).map (·.guards.length) = [3] := rfl
example : activeSlot nested (valuation true 4) counter.id = [some (.intValue 15)] := rfl
example : activeSlot nested (valuation false 4) counter.id = [some (.intValue 11)] := rfl
example : activeSlot nested (valuation true (-2)) counter.id = [some (.intValue 8)] := rfl
example : activeSlot nested (valuation false (-2)) counter.id = [some (.intValue 10)] := rfl
example : activeSlot nested (valuation true 4) flag.id = [some (.boolValue false)] := rfl
example : activeSlot (s := .int) nested (valuation false 4) scratch.id = [none] := rfl
example : activeSlot nested (valuation true (-2)) scratch.id = [some (.intValue (-6))] := rfl
example : activeSlot nested (valuation false (-2)) input.id = [some (.intValue (-2))] := rfl

private def joinBeforeRead : Command :=
  .seq
    (.branch (.boolVar "flag")
      (.assign (.local scratch.id) (.add (.intVar "n") (.intLit 1)))
      (.assign (.local scratch.id) (.sub (.intVar "n") (.intLit 1))))
    (.assign (.state counter.id) (.intVar "scratch"))

example : activeSlot joinBeforeRead (valuation true 4) counter.id = [some (.intValue 5)] := rfl
example : activeSlot joinBeforeRead (valuation false 4) counter.id = [some (.intValue 3)] := rfl

example : (translateCommands (.seq
    (.branch (.boolVar "flag") (.assign (.local scratch.id) (.intLit 7)) .skip)
    (.assign (.state counter.id) (.intVar "scratch"))) entry).isNone = true := by decide
example : (translateCommands (.assign (.state counter.id) (.boolLit true)) entry).isNone =
    true := by decide
example : (translateCommands (.assign (.local input.id) (.intLit 0)) entry).isNone =
    true := by decide

end LLMLang.SymbolicCommandTests
