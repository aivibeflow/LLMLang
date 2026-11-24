module

public meta import Lean

public meta section

open Lean Elab Command

private def fixtureConstants (names : NameSet) : List String :=
  (names.toList.map Name.toString |>.filter fun name =>
    name.startsWith "ReceiptFixture." || (name.splitOn ".ReceiptFixture.").length > 1).mergeSort

elab "#inspect_receipt " subject:ident : command => do
  let env ← getEnv
  let name ← liftCoreM <| resolveGlobalConstNoOverloadCore subject.getId
  let some decl := env.find? name
    | throwError "Expected one declaration in the current environment"
  let body := decl.value? (allowOpaque := true)
  let standardAxioms ← Lean.collectAxioms name
  let data := Json.mkObj [
    ("subject", toJson name.toString),
    ("has_value", toJson body.isSome),
    ("type_constants", toJson (fixtureConstants decl.type.getUsedConstantsAsSet)),
    ("value_constants", toJson (fixtureConstants (body.map Expr.getUsedConstantsAsSet |>.getD {}))),
    ("transitive_axioms", toJson (standardAxioms.toList.map Name.toString |>.mergeSort))]
  logInfo s!"RECEIPT {data.compress}"

end
