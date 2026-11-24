import Cpc.SmtSyntax

namespace LLMLang.LogosScalarDenotation

open Smtm (SmtTerm SmtType)

inductive Scalar where
  | int (value : Int)
  | bool (value : Bool)
  deriving Repr, BEq

def Scalar.sort : Scalar → SmtType
  | .int _ => .Int
  | .bool _ => .Bool

def needInt : Scalar → Except String Int
  | .int value => .ok value
  | _ => .error "integer expected"

def needBool : Scalar → Except String Bool
  | .bool value => .ok value
  | _ => .error "Boolean expected"

abbrev Valuation := List (SmtEval.native_String × Scalar)

/-- Executable semantics for only the translated integer and Boolean constructors. -/
def evalSmt (env : Valuation) : SmtTerm → Except String Scalar
  | .Numeral n => .ok (.int n)
  | .Boolean b => .ok (.bool b)
  | .UConst key sort => do
      let some (_, value) := env.find? (fun entry => entry.1 == key)
        | throw "unbound SMT constant"
      if value.sort == sort then pure value else throw "wrong SMT constant sort"
  | .plus a b => do
      pure (.int ((← needInt (← evalSmt env a)) + (← needInt (← evalSmt env b))))
  | .neg a b => do
      pure (.int ((← needInt (← evalSmt env a)) - (← needInt (← evalSmt env b))))
  | .uneg a => do
      pure (.int (-(← needInt (← evalSmt env a))))
  | .mult a b => do
      pure (.int ((← needInt (← evalSmt env a)) * (← needInt (← evalSmt env b))))
  | .lt a b => do
      pure (.bool (decide ((← needInt (← evalSmt env a)) < (← needInt (← evalSmt env b)))))
  | .leq a b => do
      pure (.bool (decide ((← needInt (← evalSmt env a)) ≤ (← needInt (← evalSmt env b)))))
  | .eq a b => do
      let left ← evalSmt env a
      let right ← evalSmt env b
      if left.sort == right.sort then pure (.bool (left == right)) else throw "mixed equality"
  | .not a => do
      pure (.bool (!(← needBool (← evalSmt env a))))
  | .and a b => do
      let left ← needBool (← evalSmt env a)
      let right ← needBool (← evalSmt env b)
      pure (.bool (left && right))
  | .or a b => do
      let left ← needBool (← evalSmt env a)
      let right ← needBool (← evalSmt env b)
      pure (.bool (left || right))
  | .ite cond yes no => do
      let chosen ← needBool (← evalSmt env cond)
      let left ← evalSmt env yes
      let right ← evalSmt env no
      if left.sort != right.sort then throw "mixed conditional arms"
      pure (if chosen then left else right)
  | _ => .error "unsupported translated SMT constructor"

end LLMLang.LogosScalarDenotation
