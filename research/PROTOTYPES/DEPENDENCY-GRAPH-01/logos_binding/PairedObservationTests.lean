import PairedObservationSemantics

namespace LLMLang.PairedObservationTests

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics

private def x : Declaration := ⟨⟨1⟩, "x", .input, .int⟩
private def y : Declaration := ⟨⟨2⟩, "y", .input, .int⟩
private def gate : Declaration := ⟨⟨3⟩, "gate", .input, .bool⟩
private def counter : Declaration := ⟨⟨4⟩, "counter", .state, .int⟩
private def bias : Declaration := ⟨⟨5⟩, "bias", .local, .int⟩
private def hidden : Declaration := ⟨⟨6⟩, "hidden", .input, .int⟩

private def entry : SourceScope :=
  { context := ⟨[x, y, gate, counter, bias, hidden]⟩
    visible := [x.id, y.id, gate.id, counter.id, bias.id]
    initialized := [x.id, y.id, gate.id, counter.id, bias.id] }

private def values (xValue yValue counterValue biasValue : Int) (gateValue : Bool) : Env
  | name, .int =>
    .intValue (if name = "x" then xValue else if name = "y" then yValue
      else if name = "counter" then counterValue else biasValue)
  | _, .bool => .boolValue gateValue

private def baseline : Env := values 4 3 10 2 false
private def intPair := PairedValuations.check entry x.id (values (-4) 3 10 2 false)
  (values 9 3 10 2 false)
private def boolPair := PairedValuations.check entry gate.id (values 4 3 10 2 true) baseline

private def program : Program .int :=
  { body := .branch (.or (.lt (.intVar "x") (.intLit 0)) (.boolVar "gate"))
      (.assign (.state counter.id) (.add (.intVar "counter") (.intVar "x")))
      (.assign (.state counter.id) (.add (.intVar "counter") (.intVar "y")))
    result := .add (.intVar "counter") (.intVar "bias") }

private def contract : ObservationContract := ⟨[⟨counter.id, .int⟩]⟩

private def symbolic {factor : VariableId} (entryPair : Option (PairedValuations entry factor)) :
    Option (Observation Value .int contract.fields × Observation Value .int contract.fields) := do
  let pair ← entryPair
  let paths ← translateProgramObservations program contract entry
  observeSymbolicPair paths pair

example : intPair.isSome = true := by decide
example : boolPair.isSome = true := by decide
example : (PairedValuations.check entry x.id baseline baseline).isSome = true := by decide

example : intPair.bind (observeConcretePair program contract) =
    some (⟨.intValue 8, .cons (.intValue 6) .nil⟩, ⟨.intValue 15, .cons (.intValue 13) .nil⟩) := rfl
example : symbolic intPair =
    some (⟨.intValue 8, .cons (.intValue 6) .nil⟩, ⟨.intValue 15, .cons (.intValue 13) .nil⟩) := rfl
example : boolPair.bind (observeConcretePair program contract) =
    some (⟨.intValue 16, .cons (.intValue 14) .nil⟩, ⟨.intValue 15, .cons (.intValue 13) .nil⟩) := rfl
example : symbolic boolPair =
    some (⟨.intValue 16, .cons (.intValue 14) .nil⟩, ⟨.intValue 15, .cons (.intValue 13) .nil⟩) := rfl

example (pair : PairedValuations entry x.id) :
    pair.leftInitial.env counter.id = pair.rightInitial.env counter.id :=
  pair.shared_state (by simp [entry]) rfl

example : (PairedValuations.check entry counter.id baseline baseline).isNone = true := by decide
example : (PairedValuations.check entry bias.id baseline baseline).isNone = true := by decide
example : (PairedValuations.check entry hidden.id baseline baseline).isNone = true := by decide
example : (PairedValuations.check entry ⟨99⟩ baseline baseline).isNone = true := by decide
example : (PairedValuations.check entry x.id baseline (values 9 4 10 2 false)).isNone =
    true := by decide
example : (PairedValuations.check entry x.id baseline (values 9 3 11 2 false)).isNone =
    true := by decide
example : (PairedValuations.check entry x.id baseline (values 9 3 10 5 false)).isNone =
    true := by decide
example : (PairedValuations.check entry x.id baseline (values 9 3 10 2 true)).isNone =
    true := by decide

end LLMLang.PairedObservationTests
