import Cpc.Api

open Eo Logos

def proofSexps (text : String) : Except String (List Sexp) :=
  Sexp.Parser.manySexps!.run text

def declarationName : Sexp → Option String
  | .expr [.atom "declare-const", .atom name, .expr [.atom "_", .atom "BitVec", .atom "32"]] => some name
  | _ => none

def checkedDeclarations (declarations : List Sexp) : Bool :=
  let names := declarations.filterMap declarationName
  names.length == 3 && ["a", "b", "enabled"].all names.contains

def commandAdmitted : Sexp → Bool
  | .expr [.atom "define", .atom name, .expr [], _] =>
    name.startsWith "@t" && !(name.drop 2).isEmpty && (name.drop 2).toString.toList.all Char.isDigit
  | .expr (.atom command :: _) => command == "assume" || command == "step"
  | _ => false

/-- Render only the bit-vector forms used by the exact mismatch formulas. -/
partial def cpcExpression : Sexp → Except String Sexp
  | .atom name =>
    if ["a", "b", "enabled", "true", "false"].contains name then pure (.atom name)
    else throw "unsupported-source-atom"
  | .expr [.atom "_", .atom bits, .atom widthText] => do
    if !bits.startsWith "bv" then throw "unsupported-source-constant"
    let some number := (bits.drop 2).toString.toNat? | throw "invalid-source-bits"
    let some width := widthText.toNat? | throw "invalid-source-width"
    if !(width == 32 || width == 33) || number ≥ 2 ^ width then throw "invalid-source-bit-vector"
    let digits := Nat.toDigits 2 number
    return .atom ("#b" ++ String.ofList (List.replicate (width - digits.length) '0' ++ digits))
  | .expr [.expr [.atom "_", .atom "sign_extend", .atom "1"], operand] => do
    return .expr [.atom "sign_extend", .atom "1", ← cpcExpression operand]
  | .expr [.expr [.atom "_", .atom "extract", .atom high, .atom low], operand] => do
    if high != "31" || !(low == "0" || low == "31") then throw "unsupported-source-extract"
    return .expr [.atom "extract", .atom high, .atom low, ← cpcExpression operand]
  | .expr (.atom operator :: operands) => do
    if !["=", "distinct", "not", "or", "and", "ite", "bvadd", "bvslt", "bvsgt"].contains operator then
      throw "unsupported-source-operator"
    return .expr (.atom operator :: (← operands.mapM cpcExpression))
  | _ => throw "unsupported-source-expression"

def sourceAssumption (query : String) : Except String Sexp := do
  let [.expr [.atom "set-logic", .atom "QF_BV"], first, second, third,
       .expr [.atom "assert", assertion], .expr [.atom "check-sat"]] ← proofSexps query
    | throw "invalid-source-query"
  if !checkedDeclarations [first, second, third] then throw "invalid-source-declarations"
  return .expr [.atom "assume", .atom "@expected", ← cpcExpression assertion]

def checkBinding (query proof : String) : Except String Eo.Verdict := do
  let assumption ← sourceAssumption query
  let document ← proofSexps proof
  let declarationOrder := document.takeWhile (fun command => (declarationName command).isSome)
  if !checkedDeclarations declarationOrder then throw "declarations-mismatch"
  if !(document.drop declarationOrder.length).all commandAdmitted then throw "unsupported-proof-command"
  -- The ordinary parser allocates numeric constant IDs in declaration order.
  -- Keep the source expression and replay it under this checked permutation.
  let expectedReindexed := Sexp.serializeMany (declarationOrder ++ [assumption])
  let (expected, _) ← parseProof expectedReindexed
  let (actual, commands) ← parseProof proof
  if expected ≠ actual then throw "assumptions-mismatch"
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
