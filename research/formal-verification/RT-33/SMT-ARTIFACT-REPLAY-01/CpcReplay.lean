import CpcNullaryAliases
import Cpc.Api

open LLMLang.LogosBinding
open LLMLang.CpcNullaryAliases

private def expectedDeclarations : List ExpectedDeclaration :=
  [⟨"x", .int⟩]

private def exactAssumptions (query : String) : Except String (List Eo.Term) := do
  let [
    .expr [.atom "set-logic", .atom "QF_LIA"],
    decl@(.expr [.atom "declare-const", .atom "x", .atom "Int"]),
    .expr [.atom "assert", left],
    .expr [.atom "assert", right],
    .expr [.atom "check-sat"],
    .expr [.atom "exit"]
  ] ← Logos.Sexp.Parser.manySexps!.run query
    | throw "unsupported-query"
  let checked ← parseAndBind (Logos.Sexp.serializeMany [
    decl, .expr [.atom "assume", .atom "@source-left", left],
    .expr [.atom "assume", .atom "@source-right", right]
  ]) expectedDeclarations
  pure checked.1

private def replay (query output : String) : Except String String := do
  let expected ← exactAssumptions query
  let [.atom "unsat", .expr commands] ← Logos.Sexp.Parser.manySexps!.run output
    | throw "missing-cpc-certificate"
  let proof := Logos.Sexp.serializeMany commands
  let (assumptions, commands, _) ← parseAndBind proof expectedDeclarations
  if expected != assumptions then
    throw "assumptions-mismatch"
  match Eo.logos_verdict assumptions commands with
  | .correct => pure "checked"
  | .incorrect => throw "incorrect"
  | .incomplete => throw "incomplete"

def main : List String → IO Unit
  | [query, output] => do
      let query ← IO.FS.readFile query
      let output ← IO.FS.readFile output
      match replay query output with
      | .ok result => IO.println result
      | .error reason => IO.println ("refused: " ++ reason)
  | _ => throw (IO.userError "expected exact query and CPC output")
