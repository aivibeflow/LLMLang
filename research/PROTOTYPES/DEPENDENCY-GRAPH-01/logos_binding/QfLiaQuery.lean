import SourceQuerySemantics

namespace LLMLang.LogosBinding

/-- Sorts used by the strict relational QF_LIA term profile. -/
abbrev QuerySort := SourceQuerySemantics.ExprSort

/--
Typed solver terms shared by the decoder, adapter and renderer. The indices
rule out sort mismatches. Multiplication and Boolean operand lists still
need the strict profile's literal and arity checks.
-/
inductive QueryTerm : QuerySort → Type where
  | intLit : Int → QueryTerm .int
  | boolLit : Bool → QueryTerm .bool
  | intSymbol : String → QueryTerm .int
  | boolSymbol : String → QueryTerm .bool
  | not : QueryTerm .bool → QueryTerm .bool
  | neg : QueryTerm .int → QueryTerm .int
  | add : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | sub : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | mul : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | eqInt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | eqBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool
  | lt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | le : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | and : List (QueryTerm .bool) → QueryTerm .bool
  | or : List (QueryTerm .bool) → QueryTerm .bool
  | iteInt : QueryTerm .bool → QueryTerm .int → QueryTerm .int → QueryTerm .int
  | iteBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool → QueryTerm .bool

def QueryTerm.isIntLiteral : QueryTerm .int → Bool
  | .intLit _ => true
  | _ => false

mutual
  /-- Check the strict QF_LIA operator profile recursively on the typed solver AST. -/
  def QueryTerm.isQfLia : {sort : QuerySort} → QueryTerm sort → Bool
    | _, .intLit _ | _, .boolLit _ | _, .intSymbol _ | _, .boolSymbol _ => true
    | _, .not term | _, .neg term => term.isQfLia
    | _, .add left right | _, .sub left right | _, .eqInt left right
    | _, .eqBool left right | _, .lt left right | _, .le left right =>
      left.isQfLia && right.isQfLia
    | _, .mul left right =>
      (left.isIntLiteral || right.isIntLiteral) && left.isQfLia && right.isQfLia
    | _, .and terms | _, .or terms => decide (2 ≤ terms.length) && QueryTerm.allQfLia terms
    | _, .iteInt condition yes no | _, .iteBool condition yes no =>
      condition.isQfLia && yes.isQfLia && no.isQfLia

  def QueryTerm.allQfLia : List (QueryTerm .bool) → Bool
    | [] => true
    | term :: rest => term.isQfLia && QueryTerm.allQfLia rest
end

end LLMLang.LogosBinding
