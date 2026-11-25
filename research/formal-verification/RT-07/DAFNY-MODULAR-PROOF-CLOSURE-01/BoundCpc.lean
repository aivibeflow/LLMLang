import Cpc.Api

open Eo Logos

def atoms : List String := ["base", "last", "ordinal"]

def declarationName : Sexp → Option String
  | .expr [.atom "declare-const", .atom name, .atom "Int"] => some name
  | _ => none

def declarationsMatch (declarations : List Sexp) : Bool :=
  let names := declarations.filterMap declarationName
  names.length == declarations.length && names.length == atoms.length && atoms.all names.contains

def commandAdmitted : Sexp → Bool
  | .expr [.atom "define", .atom name, .expr [], _] =>
    let number := (name.drop 2).toString
    name.startsWith "@t" && !number.isEmpty && number.toList.all Char.isDigit
  | .expr (.atom command :: _) => ["assume", "assume-push", "step", "step-pop"].contains command
  | _ => false

partial def expressionAdmitted : Sexp → Bool
  | .atom word => atoms.contains word || word.toNat?.isSome
  | .expr (.atom operator :: args) =>
    ["and", "<=", "<", "+", "*", "distinct"].contains operator &&
      !args.isEmpty && args.all expressionAdmitted
  | _ => false

def sourceFormula (query : String) : Except String Sexp := do
  let [.expr [.atom "set-logic", .atom "QF_LIA"], first, second, third,
       .expr [.atom "assert", formula], .expr [.atom "check-sat"]] ← Sexp.Parser.manySexps!.run query
    | throw "invalid-source-query"
  if !declarationsMatch [first, second, third] then throw "invalid-source-declarations"
  if !expressionAdmitted formula then throw "unsupported-source-expression"
  return formula

def checkBinding (query proof : String) : Except String Eo.Verdict := do
  let formula ← sourceFormula query
  let document ← Sexp.Parser.manySexps!.run proof
  let declarations := document.takeWhile (fun command => (declarationName command).isSome)
  if !declarationsMatch declarations then throw "declarations-mismatch"
  if !(document.drop declarations.length).all commandAdmitted then throw "unsupported-proof-command"
  let assumed := .expr [.atom "assume", .atom "@expected", formula]
  let (expected, _) ← parseProof (Sexp.serializeMany (declarations ++ [assumed]))
  let (actual, commands) ← parseProof proof
  if actual ≠ expected then throw "assumptions-mismatch"
  return logos_verdict actual commands

def main (args : List String) : IO UInt32 := do
  let [queryPath, proofPath] := args | return 64
  let query ← IO.FS.readFile queryPath
  let proof ← IO.FS.readFile proofPath
  match checkBinding query proof with
  | .error reason => IO.println reason; return 3
  | .ok .correct => IO.println "correct"; return 0
  | .ok .incorrect => IO.println "incorrect"; return 1
  | .ok .incomplete => IO.println "incomplete"; return 2
