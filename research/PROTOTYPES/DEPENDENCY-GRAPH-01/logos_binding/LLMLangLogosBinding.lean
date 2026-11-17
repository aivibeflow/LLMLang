import Cpc.Parser

namespace LLMLang.LogosBinding

inductive ExpectedSort where
  | int
  | bool
  deriving DecidableEq, Repr

structure ExpectedDeclaration where
  name : String
  sort : ExpectedSort
  deriving DecidableEq, Repr

abbrev ParserState := Logos.Parser.State Eo.Term

/--
Run the pinned Logos CPC parser while retaining its final declaration state.
Datatype elaboration is disabled here because this bridge accepts only the
Bool/Int QF_LIA fragment. The ordinary Eo.parseProof result is checked against
the state-preserving path before returning.
-/
def parseProofWithState
    (proof : String) :
    Except String (List Eo.Term × Eo.CCmdList × ParserState) := do
  let sexps ← Logos.Sexp.Parser.manySexps!.run proof
  let cfg : Logos.Parser.Config Eo.Term Eo.CRule Eo.CCmd Eo.CCmdList :=
    { Eo.parserConfig with datatypeTerms := none }
  let initial : ParserState :=
    { Logos.Parser.State.ofOps cfg.ops with macros := .ofList cfg.macros }
  let ((assumptions, commands), finalState) ←
    (Logos.Parser.parseCommands cfg sexps).run initial
  let ordinary ← Eo.parseProof proof
  if assumptions = ordinary.1 then
    pure (assumptions, commands, finalState)
  else
    throw "state-preserving CPC parser disagrees with Eo.parseProof assumptions"

/-- Check that a parsed declared constant has exactly the expected QF_LIA sort. -/
def hasExpectedSort : Eo.Term → ExpectedSort → Bool
  | Eo.Term.UConst _ Eo.Term.Bool, .bool => true
  | Eo.Term.UConst _ (Eo.Term.UOp Eo.UserOp.Int), .int => true
  | _, _ => false

def lookupDeclaration
    (state : ParserState)
    (declaration : ExpectedDeclaration) :
    Except String Eo.Term := do
  match state.terms.getD declaration.name [] with
  | [term@(Eo.Term.UConst _ _)] =>
      if hasExpectedSort term declaration.sort then
        pure term
      else
        throw s!"unexpected sort for CPC declaration: {declaration.name}"
  | [] =>
      throw s!"missing CPC declaration: {declaration.name}"
  | _ =>
      throw s!"ambiguous or repeated CPC declaration: {declaration.name}"

/--
Bind the complete expected declaration set to the exact UConst nodes retained
by the Logos parser. Extra, missing, duplicate, overloaded, or wrong-sort
declarations fail closed.
-/
def bindExpectedDeclarations
    (state : ParserState)
    (expected : List ExpectedDeclaration) :
    Except String (List (String × Eo.Term)) := do
  let names := expected.map ExpectedDeclaration.name
  if names.eraseDups.length != names.length then
    throw "duplicate name in expected CPC declaration set"
  if state.ufCount != expected.length then
    throw "CPC uninterpreted-constant count differs from expected declaration count"
  if state.terms.toList.length != expected.length then
    throw "CPC declaration table contains missing or unexpected names"
  expected.mapM fun declaration => do
    let term ← lookupDeclaration state declaration
    pure (declaration.name, term)

end LLMLang.LogosBinding
