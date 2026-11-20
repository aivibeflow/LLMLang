import QfLiaAdmissibility

namespace LLMLang.ProgramRelationalQueryTests

open LLMLang.SourceQuerySemantics
open LLMLang.SourceSyntax
open LLMLang.SourceCommandSemantics
open LLMLang.ProgramObservationSemantics
open LLMLang.PairedObservationSemantics
open LLMLang.CanonicalQuerySymbols
open LLMLang.ProgramRelationalQuery

-- This source spelling is also the canonical symbol for the shared input y.
private def x : Declaration := ⟨⟨1⟩, "i_6", .input, .int⟩
private def y : Declaration := ⟨⟨2⟩, "y", .input, .int⟩
private def counter : Declaration := ⟨⟨3⟩, "counter", .state, .int⟩
private def bias : Declaration := ⟨⟨4⟩, "bias", .local, .int⟩
private def flag : Declaration := ⟨⟨5⟩, "flag", .state, .bool⟩
private def gate : Declaration := ⟨⟨6⟩, "gate", .input, .bool⟩
private def scratch : Declaration := ⟨⟨7⟩, "scratch", .local, .int⟩

private def entry : SourceScope :=
  { context := ⟨[x, y, counter, bias, flag, gate, scratch]⟩
    visible := [x.id, y.id, counter.id, bias.id, flag.id, gate.id, scratch.id]
    initialized := [x.id, y.id, counter.id, bias.id, flag.id, gate.id] }

private def queryEnv (left right : Int) : Env
  | "i_4", .int => .intValue left
  | "i_5", .int => .intValue right
  | "i_6", .int => .intValue 3
  | "i_9", .int => .intValue 10
  | "i_12", .int => .intValue 2
  | "i_19", .bool => .boolValue true
  | _, .int => .intValue 0
  | _, .bool => .boolValue false

private def program : Program .int :=
  { body := .branch (.lt (.intVar "i_6") (.intLit 0))
      (.assign (.state counter.id) (.add (.intVar "counter") (.intVar "i_6")))
      (.assign (.state counter.id) (.add (.intVar "counter") (.intVar "y")))
    result := .add (.intVar "counter") (.intVar "bias") }

private def stateOnly : Program .int := {program with result := .intLit 0}
private def returnsOnly : ObservationContract := ⟨[]⟩
private def observesCounter : ObservationContract := ⟨[⟨counter.id, .int⟩]⟩

private def boolProgram : Program .bool :=
  { body := .branch (.boolVar "gate") (.assign (.state flag.id) (.boolLit true))
      (.assign (.state flag.id) (.boolLit false))
    result := .boolVar "flag" }

private def evaluate {sort : ExprSort} (program : Program sort) (contract : ObservationContract)
    (factor : VariableId) (valuation : Env) : Option Bool :=
  (compileRelationalQuery program contract entry factor).map
    (fun query => asBool (evalQuery query.formula valuation))

example : evaluate program returnsOnly x.id (queryEnv (-4) 9) = some true := rfl
example : evaluate program returnsOnly x.id (queryEnv 9 (-4)) = some true := rfl
example : evaluate program returnsOnly x.id (queryEnv 4 9) = some false := rfl
example : evaluate program observesCounter x.id (queryEnv (-4) (-4)) = some false := rfl
example : evaluate stateOnly observesCounter x.id (queryEnv (-4) 9) = some true := rfl
example : evaluate stateOnly returnsOnly x.id (queryEnv (-4) 9) = some false := rfl
example : evaluate boolProgram returnsOnly gate.id (queryEnv 0 0) = some true := rfl
example : evaluate {boolProgram with result := .boolLit false} ⟨[⟨flag.id, .bool⟩, ⟨counter.id, .int⟩]⟩
    gate.id (queryEnv 0 0) = some true := rfl

example : (symbolBindings entry x.id).map SymbolBinding.name =
    ["i_4", "i_5", "i_6", "i_9", "i_12", "i_15", "i_18"] := rfl

private def concretePair := do
  let query ← compileRelationalQuery program observesCounter entry x.id
  observeConcretePair program observesCounter (query.inputPair (queryEnv (-4) 9))

example : concretePair =
    some (⟨.intValue 8, .cons (.intValue 6) .nil⟩, ⟨.intValue 15, .cons (.intValue 13) .nil⟩) := rfl

private def sourceEnv (factorValue : Int) : Env
  | "i_6", .int => .intValue factorValue
  | "y", .int => .intValue 3
  | "counter", .int => .intValue 10
  | "bias", .int => .intValue 2
  | _, .int => .intValue 0
  | _, .bool => .boolValue false

private def replay : Option Bool := do
  let pair ← PairedValuations.check entry x.id (sourceEnv (-4)) (sourceEnv 9)
  let query ← compileRelationalQuery program observesCounter entry x.id
  pure (asBool (evalQuery query.formula (valuationForPair pair)))

example : replay = some true := rfl

example : (compileRelationalQuery program observesCounter entry counter.id).isNone = true := rfl
example : (compileRelationalQuery program observesCounter entry bias.id).isNone = true := rfl
example : (compileRelationalQuery program observesCounter entry ⟨99⟩).isNone = true := rfl
example : (compileRelationalQuery program ⟨[⟨counter.id, .bool⟩]⟩ entry x.id).isNone = true := rfl
example : (compileRelationalQuery program ⟨[⟨counter.id, .int⟩, ⟨counter.id, .int⟩]⟩
    entry x.id).isNone = true := rfl

private def scaledProgram : Program .int :=
  { program with result := .mulConst (-3) (.intVar "counter") }

example : ((compileRelationalQuery scaledProgram observesCounter entry x.id).map
    (fun query => (LogosQueryAdapter.toLogosQueryTerm query.formula).isQfLia)) = some true := rfl

private def variableProduct : LogosBinding.QueryTerm .int :=
  .mul (.intSymbol "x") (.intSymbol "y")

example : (LogosBinding.QueryTerm.mul (.intSymbol "x") (.intLit (-2))).isQfLia = true := rfl
example : variableProduct.isQfLia = false := rfl
example : (LogosBinding.QueryTerm.mul (.neg (.intLit 2)) (.intSymbol "x")).isQfLia = false := rfl
example : (LogosBinding.QueryTerm.iteInt (.boolLit true) (.intLit 0)
    (.mul (.intLit 0) variableProduct)).isQfLia = false := rfl
example : (LogosBinding.QueryTerm.and []).isQfLia = false := rfl
example : (LogosBinding.QueryTerm.or [.boolLit false]).isQfLia = false := rfl

end LLMLang.ProgramRelationalQueryTests
