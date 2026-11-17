import LLMLangLogosBinding

open LLMLang.LogosBinding

def expectFailure (result : Except String α) : IO Unit := do
  match result with
  | .error _ => pure ()
  | .ok _ => throw (IO.userError "expected fail-closed rejection")

def main : IO Unit := do
  IO.println "test 1: parse single Int declaration"
  let proof :=
    "(declare-const x Int)\n" ++
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
    "(declare-const x Int)\n" ++
    "(declare-const x Bool)\n" ++
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
    "(declare-const x Int)\n" ++
    "(declare-const y Int)\n" ++
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

  IO.println "CPC parser-state binding and typed query rendering tests passed"
