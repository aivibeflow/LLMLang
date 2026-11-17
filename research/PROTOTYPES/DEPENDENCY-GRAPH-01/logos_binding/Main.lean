import LLMLangLogosBinding

open LLMLang.LogosBinding

def expectFailure (result : Except String α) : IO Unit := do
  match result with
  | .error _ => pure ()
  | .ok _ => throw (IO.userError "expected fail-closed rejection")

def main : IO Unit := do
  let proof :=
    "(declare-const x Int)\n" ++
    "(assume a (= x x))\n"
  let (assumptions, _commands, state) ←
    match parseProofWithState proof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if assumptions.length != 1 then
    throw (IO.userError "expected exactly one parsed assumption")
  let bindings ←
    match bindExpectedDeclarations state [{ name := "x", sort := .int }] with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  if bindings.length != 1 then
    throw (IO.userError "expected exactly one bound declaration")

  let duplicateProof :=
    "(declare-const x Int)\n" ++
    "(declare-const x Bool)\n" ++
    "(assume a (= x true))\n"
  let (_, _, duplicateState) ←
    match parseProofWithState duplicateProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  expectFailure (bindExpectedDeclarations duplicateState [{ name := "x", sort := .bool }])

  let extraProof :=
    "(declare-const x Int)\n" ++
    "(declare-const y Int)\n" ++
    "(assume a (= x y))\n"
  let (_, _, extraState) ←
    match parseProofWithState extraProof with
    | .ok result => pure result
    | .error error => throw (IO.userError error)
  expectFailure (bindExpectedDeclarations extraState [{ name := "x", sort := .int }])

  IO.println "CPC parser-state binding tests passed"
