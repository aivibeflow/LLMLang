/-
A first kernel-checked source-to-query correspondence slice.

This module is deliberately independent of Logos and cvc5. It defines a tiny
typed pure expression language, its mathematical semantics, a separate typed
query-term language, and a structural translation. The theorem below proves
expression-level semantic preservation only; it says nothing yet about
commands, program execution, paired runs, or SMT/CPC encodings.
-/

namespace LLMLang.SourceQuerySemantics

inductive ExprSort where
  | int
  | bool
  deriving DecidableEq, Repr

def Value : ExprSort → Type
  | .int => Int
  | .bool => Bool

abbrev Env := (name : String) → (sort : ExprSort) → Value sort

/-- Typed source expressions for the pure mathematical-Int/Bool fragment. -/
inductive Expr : ExprSort → Type where
  | intLit : Int → Expr .int
  | boolLit : Bool → Expr .bool
  | intVar : String → Expr .int
  | boolVar : String → Expr .bool
  | neg : Expr .int → Expr .int
  | add : Expr .int → Expr .int → Expr .int
  | sub : Expr .int → Expr .int → Expr .int
  | mulConst : Int → Expr .int → Expr .int
  | not : Expr .bool → Expr .bool
  | eqInt : Expr .int → Expr .int → Expr .bool
  | eqBool : Expr .bool → Expr .bool → Expr .bool
  | lt : Expr .int → Expr .int → Expr .bool
  | le : Expr .int → Expr .int → Expr .bool
  | and : Expr .bool → Expr .bool → Expr .bool
  | or : Expr .bool → Expr .bool → Expr .bool
  | iteInt : Expr .bool → Expr .int → Expr .int → Expr .int
  | iteBool : Expr .bool → Expr .bool → Expr .bool → Expr .bool

/-- Independent typed query syntax; no source AST constructors are reused. -/
inductive QueryTerm : ExprSort → Type where
  | intLit : Int → QueryTerm .int
  | boolLit : Bool → QueryTerm .bool
  | symbolInt : String → QueryTerm .int
  | symbolBool : String → QueryTerm .bool
  | neg : QueryTerm .int → QueryTerm .int
  | add : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | sub : QueryTerm .int → QueryTerm .int → QueryTerm .int
  | mulConst : Int → QueryTerm .int → QueryTerm .int
  | not : QueryTerm .bool → QueryTerm .bool
  | eqInt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | eqBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool
  | lt : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | le : QueryTerm .int → QueryTerm .int → QueryTerm .bool
  | and : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool
  | or : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool
  | iteInt : QueryTerm .bool → QueryTerm .int → QueryTerm .int → QueryTerm .int
  | iteBool : QueryTerm .bool → QueryTerm .bool → QueryTerm .bool → QueryTerm .bool

/-- Source expression evaluation over mathematical integers and Booleans. -/
def evalExpr : {s : ExprSort} → Expr s → Env → Value s
  | .int, .intLit n, _ => n
  | .bool, .boolLit b, _ => b
  | .int, .intVar name, env => env name .int
  | .bool, .boolVar name, env => env name .bool
  | .int, .neg e, env => -(evalExpr e env)
  | .int, .add a b, env => evalExpr a env + evalExpr b env
  | .int, .sub a b, env => evalExpr a env - evalExpr b env
  | .int, .mulConst k e, env => k * evalExpr e env
  | .bool, .not e, env => !(evalExpr e env)
  | .bool, .eqInt a b, env => evalExpr a env == evalExpr b env
  | .bool, .eqBool a b, env => evalExpr a env == evalExpr b env
  | .bool, .lt a b, env => evalExpr a env < evalExpr b env
  | .bool, .le a b, env => evalExpr a env <= evalExpr b env
  | .bool, .and a b, env => evalExpr a env && evalExpr b env
  | .bool, .or a b, env => evalExpr a env || evalExpr b env
  | .int, .iteInt c a b, env => if evalExpr c env then evalExpr a env else evalExpr b env
  | .bool, .iteBool c a b, env => if evalExpr c env then evalExpr a env else evalExpr b env

/-- Structural translation from the typed source AST to the typed query AST. -/
def translateExpr : {s : ExprSort} → Expr s → QueryTerm s
  | .int, .intLit n => .intLit n
  | .bool, .boolLit b => .boolLit b
  | .int, .intVar name => .symbolInt name
  | .bool, .boolVar name => .symbolBool name
  | .int, .neg e => .neg (translateExpr e)
  | .int, .add a b => .add (translateExpr a) (translateExpr b)
  | .int, .sub a b => .sub (translateExpr a) (translateExpr b)
  | .int, .mulConst k e => .mulConst k (translateExpr e)
  | .bool, .not e => .not (translateExpr e)
  | .bool, .eqInt a b => .eqInt (translateExpr a) (translateExpr b)
  | .bool, .eqBool a b => .eqBool (translateExpr a) (translateExpr b)
  | .bool, .lt a b => .lt (translateExpr a) (translateExpr b)
  | .bool, .le a b => .le (translateExpr a) (translateExpr b)
  | .bool, .and a b => .and (translateExpr a) (translateExpr b)
  | .bool, .or a b => .or (translateExpr a) (translateExpr b)
  | .int, .iteInt c a b => .iteInt (translateExpr c) (translateExpr a) (translateExpr b)
  | .bool, .iteBool c a b => .iteBool (translateExpr c) (translateExpr a) (translateExpr b)

/-- Query-term evaluation, defined independently from source evaluation. -/
def evalQuery : {s : ExprSort} → QueryTerm s → Env → Value s
  | .int, .intLit n, _ => n
  | .bool, .boolLit b, _ => b
  | .int, .symbolInt name, env => env name .int
  | .bool, .symbolBool name, env => env name .bool
  | .int, .neg e, env => -(evalQuery e env)
  | .int, .add a b, env => evalQuery a env + evalQuery b env
  | .int, .sub a b, env => evalQuery a env - evalQuery b env
  | .int, .mulConst k e, env => k * evalQuery e env
  | .bool, .not e, env => !(evalQuery e env)
  | .bool, .eqInt a b, env => evalQuery a env == evalQuery b env
  | .bool, .eqBool a b, env => evalQuery a env == evalQuery b env
  | .bool, .lt a b, env => evalQuery a env < evalQuery b env
  | .bool, .le a b, env => evalQuery a env <= evalQuery b env
  | .bool, .and a b, env => evalQuery a env && evalQuery b env
  | .bool, .or a b, env => evalQuery a env || evalQuery b env
  | .int, .iteInt c a b, env => if evalQuery c env then evalQuery a env else evalQuery b env
  | .bool, .iteBool c a b, env => if evalQuery c env then evalQuery a env else evalQuery b env

/--
SC-1/SC-2 expression slice: the translation preserves the result sort by
construction and preserves the mathematical value for every environment.
This is a kernel-checked theorem, not a test or solver result.
-/
theorem translateExpr_preserves_eval {s : ExprSort} (e : Expr s) (env : Env) :
    evalQuery (translateExpr e) env = evalExpr e env := by
  induction e <;> simp [translateExpr, evalQuery, evalExpr, *]

end LLMLang.SourceQuerySemantics
