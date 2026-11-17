import LLMLangLogosBinding

open LLMLang.LogosBinding

def expectFailure (result : Except String α) : IO Unit := do
  match result with
  | .error _ => pure ()
  | .ok _ => throw (IO.userError "expected fail-closed rejection")

def main : IO Unit := do
  IO.println "test 1: parse single Int declaration"
  let proof :=
    "(declare-const x Int) " ++
    "(assume a (= x x))\n"
  IO.println "test 1a: parsing and comparing ordinary parser"
  let (assumptions, _commands, state) ←
    match parseProofWithState proof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  IO.println "test 1b: parser returned"
  if assumptions.length != 1 then
    throw (IO.userError "expected exactly one parsed assumption")
  let bindings ←
    match bindExpectedDeclarations state [{ name := "x", sort := .int }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  IO.println "test 1c: declaration bound"
  if bindings.length != 1 then
    throw (IO.userError "expected exactly one bound declaration")

  IO.println "test 2: reject repeated/overloaded declaration"
  let duplicateProof :=
    "(declare-const x Int) " ++
    "(declare-const x Bool) " ++
    "(assume a (= x true))\n"
  IO.println "test 2a: parsing duplicate declaration"
  let (_, _, duplicateState) ←
    match parseProofWithState duplicateProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  IO.println "test 2b: duplicate parsed; checking rejection"
  expectFailure (bindExpectedDeclarations duplicateState [{ name := "x", sort := .bool }])

  IO.println "test 3: reject unexpected declaration"
  let extraProof :=
    "(declare-const x Int) " ++
    "(declare-const y Int) " ++
    "(assume a (= x y))\n"
  IO.println "test 3a: parsing extra declaration"
  let (_, _, extraState) ←
    match parseProofWithState extraProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  IO.println "test 3b: extra declaration parsed; checking rejection"
  expectFailure (bindExpectedDeclarations extraState [{ name := "x", sort := .int }])


  IO.println "test 4: independently render typed query term"
  let xBinding ←
    match bindExpectedDeclarations state [{ name := "x", sort := .int }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let expected ←
    match renderQueryTerm xBinding
      (QueryTerm.eqInt (.intSymbol "x") (.intSymbol "x")) with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if assumptions != [expected] then
    throw (IO.userError "typed query renderer differs from parsed CPC assumption")

  IO.println "test 5: reject wrong-sort query symbol"
  expectFailure (renderQueryTerm xBinding (QueryTerm.eqBool (.boolSymbol "x") (.boolLit true)))

  IO.println "test 6: render compound QF_LIA expression"
  let compound ←
    match renderQueryTerm xBinding
      (QueryTerm.le
        (QueryTerm.add (.intSymbol "x") (.intLit 2))
        (QueryTerm.mul (.intSymbol "x") (.intLit 3))) with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if compound == expected then
    throw (IO.userError "compound expression unexpectedly equals reflexive equality")

  IO.println "test 7: exact arithmetic AST equivalence"
  let arithmeticProof :=
    "(declare-const x Int) " ++
    "(assume a (<= (+ x 2) (* x 3)))\n"
  let (arithmeticAssumptions, _, arithmeticState) ←
    match parseProofWithState arithmeticProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let arithmeticBindings ←
    match bindExpectedDeclarations arithmeticState [{ name := "x", sort := .int }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let arithmeticExpected ←
    match renderQueryTerm arithmeticBindings
      (QueryTerm.le
        (QueryTerm.add (.intSymbol "x") (.intLit 2))
        (QueryTerm.mul (.intSymbol "x") (.intLit 3))) with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if arithmeticAssumptions != [arithmeticExpected] then
    throw (IO.userError "arithmetic renderer does not exactly match parsed CPC AST")

  IO.println "test 8: exact Boolean and AST equivalence"
  let booleanProof :=
    "(declare-const p Bool) " ++
    "(declare-const q Bool) " ++
    "(assume a (and p (not q)))\n"
  let (booleanAssumptions, _, booleanState) ←
    match parseProofWithState booleanProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let booleanBindings ←
    match bindExpectedDeclarations booleanState
      [{ name := "p", sort := .bool }, { name := "q", sort := .bool }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let booleanExpected ←
    match renderQueryTerm booleanBindings
      (QueryTerm.and [.boolSymbol "p", QueryTerm.not (.boolSymbol "q")]) with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if booleanAssumptions != [booleanExpected] then
    throw (IO.userError "Boolean renderer does not exactly match parsed CPC AST")

  IO.println "test 9: exact AST equivalence for remaining query constructors"
  let extendedProof :=
    "(declare-const x Int) " ++
    "(declare-const y Int) " ++
    "(declare-const p Bool) " ++
    "(declare-const q Bool) " ++
    "(assume a (and (< x y) (= p q) (or p q) (= (ite p x y) x) (= (ite p true false) p) (= (- x) y) (= (- x y) y)))\n"
  let (extendedAssumptions, _, extendedState) ←
    match parseProofWithState extendedProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let extendedBindings ←
    match bindExpectedDeclarations extendedState
      [{ name := "x", sort := .int }, { name := "y", sort := .int },
       { name := "p", sort := .bool }, { name := "q", sort := .bool }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  let extendedTerms : List (QueryTerm .bool) := [
    QueryTerm.lt (.intSymbol "x") (.intSymbol "y"),
    QueryTerm.eqBool (.boolSymbol "p") (.boolSymbol "q"),
    QueryTerm.or [.boolSymbol "p", .boolSymbol "q"],
    QueryTerm.eqInt
      (.iteInt (.boolSymbol "p") (.intSymbol "x") (.intSymbol "y"))
      (.intSymbol "x"),
    QueryTerm.eqBool
      (.iteBool (.boolSymbol "p") (.boolLit true) (.boolLit false))
      (.boolSymbol "p"),
    QueryTerm.eqInt (.neg (.intSymbol "x")) (.intSymbol "y"),
    QueryTerm.eqInt
      (.sub (.intSymbol "x") (.intSymbol "y"))
      (.intSymbol "y")
  ]
  let extendedExpected ←
    match renderQueryTerm extendedBindings (.and extendedTerms) with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if extendedAssumptions != [extendedExpected] then
    throw (IO.userError "extended query constructors do not exactly match parsed CPC AST")

  IO.println "CPC parser-state binding and typed query rendering tests passed"


  IO.println "test 10: decode and bind canonical version-1 JSON query"
  let canonicalProof :=
    "(declare-const x Int) " ++
    "(assume a (not (= x x))) " ++
    "(assume b (<= (+ x 2) (* x 3)))\n"
  let canonicalJson :=
    "{\"schema\":\"llmlang.qf_lia.relational-query/1\",\"factor\":\"input\",\"declarations\":[{\"name\":\"x\",\"sort\":\"Int\"}]," ++
    "\"factor_difference\":{\"op\":\"not\",\"sort\":\"Bool\",\"args\":[{\"op\":\"eq\",\"sort\":\"Bool\",\"args\":[{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"},{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"}],\"atom\":null}],\"atom\":null}," ++
    "\"observations_differ\":{\"op\":\"le\",\"sort\":\"Bool\",\"args\":[{\"op\":\"add\",\"sort\":\"Int\",\"args\":[{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"},{\"op\":\"int\",\"sort\":\"Int\",\"args\":[],\"atom\":2}],\"atom\":null},{\"op\":\"mul\",\"sort\":\"Int\",\"args\":[{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"},{\"op\":\"int\",\"sort\":\"Int\",\"args\":[],\"atom\":3}],\"atom\":null}],\"atom\":null}," ++
    "\"observation_contract\":\"return-and-selected-state/1\"}"
  match checkCanonicalQueryAssumptions canonicalProof canonicalJson with
  | .ok _ => pure ()
  | .error error => throw (IO.userError error)

  IO.println "test 11: reject unknown JSON fields and nonlinear multiplication"
  expectFailure (decodeCanonicalRelationalQuery
    "{\"schema\":\"llmlang.qf_lia.relational-query/1\",\"factor\":\"x\",\"declarations\":[],\"factor_difference\":{},\"observations_differ\":{},\"observation_contract\":\"x\",\"extra\":true}")
  let nonlinearJson :=
    "{\"schema\":\"llmlang.qf_lia.relational-query/1\",\"factor\":\"x\",\"declarations\":[{\"name\":\"x\",\"sort\":\"Int\"}],"
    ++ "\"factor_difference\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":true},"
    ++ "\"observations_differ\":{\"op\":\"eq\",\"sort\":\"Bool\",\"args\":[{\"op\":\"mul\",\"sort\":\"Int\",\"args\":[{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"},{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"x\"}],\"atom\":null},{\"op\":\"int\",\"sort\":\"Int\",\"args\":[],\"atom\":0}],\"atom\":null},"
    ++ "\"observation_contract\":\"return-and-selected-state/1\"}"
  expectFailure (decodeCanonicalRelationalQuery nonlinearJson)


  IO.println "test 12: reject malformed leaf atoms and empty identifiers"
  let badIntAtom ←
    match Lean.Json.parse "{\"op\":\"int\",\"sort\":\"Int\",\"args\":[],\"atom\":true}" with
    | .ok value => pure value
    | .error error => throw (IO.userError error)
  expectFailure (decodeQueryTerm .int badIntAtom)
  let emptySymbol ←
    match Lean.Json.parse "{\"op\":\"symbol\",\"sort\":\"Int\",\"args\":[],\"atom\":\"\"}" with
    | .ok value => pure value
    | .error error => throw (IO.userError error)
  expectFailure (decodeQueryTerm .int emptySymbol)
  let operatorWithAtom ←
    match Lean.Json.parse "{\"op\":\"not\",\"sort\":\"Bool\",\"args\":[{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":true}],\"atom\":false}" with
    | .ok value => pure value
    | .error error => throw (IO.userError error)
  expectFailure (decodeQueryTerm .bool operatorWithAtom)

  IO.println "test 13: reject invalid factor/declaration identifiers and schema"
  expectFailure (decodeCanonicalRelationalQuery
    "{\"schema\":\"llmlang.qf_lia.relational-query/1\",\"factor\":\"bad-name\",\"declarations\":[],\"factor_difference\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":true},\"observations_differ\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":false},\"observation_contract\":\"contract/1\"}")
  expectFailure (decodeCanonicalRelationalQuery
    "{\"schema\":\"llmlang.qf_lia.relational-query/1\",\"factor\":\"f\",\"declarations\":[{\"name\":\"bad-name\",\"sort\":\"Int\"}],\"factor_difference\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":true},\"observations_differ\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":false},\"observation_contract\":\"contract/1\"}")
  expectFailure (decodeCanonicalRelationalQuery
    "{\"schema\":\"llmlang.qf_lia.relational-query/2\",\"factor\":\"f\",\"declarations\":[],\"factor_difference\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":true},\"observations_differ\":{\"op\":\"bool\",\"sort\":\"Bool\",\"args\":[],\"atom\":false},\"observation_contract\":\"contract/1\"}")

  IO.println "Lean decoder adversarial tests passed"
