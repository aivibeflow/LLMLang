import CpcNullaryAliases

open LLMLang.LogosBinding
open LLMLang.CpcNullaryAliases

private def expected : List ExpectedDeclaration := [⟨"x", .int⟩]
private def start := "(declare-const x Int)\n"
private def flat := start ++ "(assume @p1 (= (+ x 1) (+ x 1)))\n"
private def aliased := start ++ "(define @t1 () (+ x 1))\n(assume @p1 (= @t1 @t1))\n"

private def requireFailure (label : String) (proof : String) : Except String Unit :=
  if (parseAndBind proof expected).isOk then .error s!"accepted: {label}" else .ok ()

private def check : Except String Unit := do
  let (a, _, direct) ← parseAndBind flat expected
  let (b, _, withAlias) ← parseAndBind aliased expected
  if a != b || direct != withAlias then
    throw "expanded alias must retain the exact assumptions and bindings"
  let (_, _, oldState) ← parseProofWithState aliased
  if (bindExpectedDeclarations oldState expected).isOk then
    throw "strict baseline unexpectedly accepts an extra alias entry"

  let renamed := "(declare-const z Int) (define x () z) (assume @p1 (= x x))"
  let (_, _, renamedState) ← parseProofWithState renamed
  let _ ← lookupDeclaration renamedState ⟨"x", .int⟩
  if renamedState.ufCount != 1 then
    throw "the alias-as-declaration control did not preserve the constant count"
  requireFailure "alias masquerading as the expected constant" renamed
  requireFailure "extra constant" (start ++ "(declare-const y Int) (assume @p1 (= x x))")
  requireFailure "overloaded alias" (start ++ "(define x () 0) (assume @p1 (= x x))")
  requireFailure "duplicate proof alias" (start ++ "(define t () 0) (define t () 1)")
  requireFailure "parameterized macro" (start ++ "(define t (n) n)")
  requireFailure "wrong sort" "(declare-const x Bool) (assume @p1 (= x x))"
  requireFailure "alternate declaration form" "(declare-fun x () Int)"

def main : IO Unit :=
  match check with
  | .ok () => IO.println "Closed CPC nullary alias controls passed"
  | .error reason => throw (IO.userError reason)
