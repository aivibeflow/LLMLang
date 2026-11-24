import CpcNullaryAliases
import Cpc.Api

namespace LLMLang.SymbolicCpcCertificate

open LLMLang.LogosBinding
open LLMLang.CpcNullaryAliases

private def declarations : List ExpectedDeclaration := [⟨"v0", .int⟩]

private def mentionsSecondInput : Logos.Sexp → Bool
  | .atom name => name == "v1" || name == "|v1|"
  | .expr args => args.any mentionsSecondInput

/-- The two archived SMT queries both declare v1 and leave it unused in the assertion. -/
def sourceAssumptions (query : String) : Except String (List Eo.Term) := do
  let [
    .expr [.atom "set-logic", .atom "QF_LIA"],
    declared@(.expr [.atom "declare-const", .atom "v0", .atom "Int"]),
    .expr [.atom "declare-const", .atom "v1", .atom "Int"],
    .expr [.atom "assert", assertion],
    .expr [.atom "check-sat"],
    .expr [.atom "exit"]
  ] ← Logos.Sexp.Parser.manySexps!.run query
    | throw "unsupported symbolic query shape"
  if mentionsSecondInput assertion then
    throw "the second declared input occurs in the source assertion"
  let source := Logos.Sexp.serializeMany [declared, .expr [.atom "assume", .atom "@source", assertion]]
  let (assumptions, _, _) ← parseAndBind source declarations
  pure assumptions

/-- Read the solver's UNSAT result and unwrap exactly one command list. -/
def certificateFile (output : String) : Except String String := do
  let [.atom "unsat", .expr commands] ← Logos.Sexp.Parser.manySexps!.run output
    | throw "expected exactly one UNSAT result and one CPC command list"
  pure (Logos.Sexp.serializeMany commands)

structure CheckedCertificate (expected : List Eo.Term) (proof : String) where
  commands : Eo.CCmdList
  parsed : Eo.parseProof proof = .ok (expected, commands)
  accepted : Eo.logos_verdict expected commands = .correct

def checkParsed (expected : List Eo.Term) (proof : String) :
    Except String (CheckedCertificate expected proof) := do
  let _ ← parseAndBind proof declarations
  match parsed : Eo.parseProof proof with
  | .error reason => .error reason
  | .ok (assumptions, commands) =>
      if same : assumptions = expected then
        match verdict : Eo.logos_verdict assumptions commands with
        | .correct => pure ⟨commands, by simpa only [same] using parsed,
            by simpa only [same] using verdict⟩
        | .incomplete => throw "Logos returned incomplete"
        | .incorrect => throw "Logos returned incorrect"
      else
        throw "CPC assumptions differ from the exact source assertion"

structure BoundCertificate (query output : String) where
  expected : List Eo.Term
  proof : String
  source : sourceAssumptions query = .ok expected
  wrapped : certificateFile output = .ok proof
  checked : CheckedCertificate expected proof

def check (query output : String) : Except String (BoundCertificate query output) :=
  match source : sourceAssumptions query with
  | .error reason => .error reason
  | .ok expected =>
      match wrapped : certificateFile output with
      | .error reason => .error reason
      | .ok proof =>
          (checkParsed expected proof).map fun checked => ⟨expected, proof, source, wrapped, checked⟩

theorem BoundCertificate.ordinary_correct {query output : String}
    (bound : BoundCertificate query output) :
    Eo.logos_check_proof bound.proof = .ok .correct := by
  unfold Eo.logos_check_proof
  rw [bound.checked.parsed]
  change Except.ok (Eo.logos_verdict bound.expected bound.checked.commands) = .ok .correct
  rw [bound.checked.accepted]

def run : List String → IO Unit
  | [queryPath, outputPath] => do
      let query ← IO.FS.readFile queryPath
      let output ← IO.FS.readFile outputPath
      match check query output with
      | .ok _ => IO.println "source-bound Logos verdict: correct"
      | .error reason => throw (IO.userError reason)
  | _ => throw (IO.userError "expected an SMT-LIB query and raw CPC output file")

end LLMLang.SymbolicCpcCertificate

def main := LLMLang.SymbolicCpcCertificate.run
