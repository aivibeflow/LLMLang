import Lean

namespace ScopedConditional

structure Observation where
  value : Int
  trace : List String
  deriving DecidableEq, Repr

inductive Expr where
  | input
  | literal (value : Int)
  | add (left right : Expr)
  | sub (left right : Expr)
  | emit (label : String) (tail : Expr)
  | branch (left right yes no : Expr)
  deriving DecidableEq

def deep : Expr → Int → Observation
  | .input, argument => ⟨argument, []⟩
  | .literal value, _ => ⟨value, []⟩
  | .add left right, argument =>
    let l := deep left argument
    let r := deep right argument
    ⟨l.value + r.value, l.trace ++ r.trace⟩
  | .sub left right, argument =>
    let l := deep left argument
    let r := deep right argument
    ⟨l.value - r.value, l.trace ++ r.trace⟩
  | .emit label tail, argument =>
    let last := deep tail argument
    ⟨last.value, label :: last.trace⟩
  | .branch left right yes no, argument =>
    let l := deep left argument
    let r := deep right argument
    let selected := if l.value = r.value then deep yes argument else deep no argument
    ⟨selected.value, l.trace ++ r.trace ++ selected.trace⟩

abbrev Action := Int → Observation

def input : Action := fun n => ⟨n, []⟩
def constant (value : Int) : Action := fun _ => ⟨value, []⟩

def binary (operator : Int → Int → Int) (left right : Action) : Action :=
  fun n => ⟨operator (left n).value (right n).value, (left n).trace ++ (right n).trace⟩

def mark (label : String) (tail : Action) : Action :=
  fun n => ⟨(tail n).value, label :: (tail n).trace⟩

def choose (left right yes no : Action) : Action :=
  fun n =>
    let selected := if (left n).value = (right n).value then yes n else no n
    ⟨selected.value, (left n).trace ++ (right n).trace ++ selected.trace⟩

def lower : Expr → Action
  | .input => input
  | .literal value => constant value
  | .add left right => binary Int.add (lower left) (lower right)
  | .sub left right => binary Int.sub (lower left) (lower right)
  | .emit label tail => mark label (lower tail)
  | .branch left right yes no => choose (lower left) (lower right) (lower yes) (lower no)

theorem lower_matches_deep (expression : Expr) (n : Int) :
    lower expression n = deep expression n := by
  induction expression with
  | input => rfl
  | literal => rfl
  | add _ _ left right => simp [lower, deep, binary, left, right]
  | sub _ _ left right => simp [lower, deep, binary, left, right] <;> rfl
  | emit _ _ tail => simp [lower, deep, mark, tail]
  | branch _ _ _ _ left right yes no =>
    simp [lower, deep, choose, left, right, yes, no]

open Lean in
def decode : Nat → Json → Option Expr
  | 0, _ => none
  | fuel+1, json => do
    match (← json.getArr?.toOption).toList with
    | [.str "argument", index] =>
      if (← index.getNat?.toOption) = 0 then some .input else none
    | [.str "literal", value] => Expr.literal <$> value.getInt?.toOption
    | [.str "add", left, right] => Expr.add <$> decode fuel left <*> decode fuel right
    | [.str "sub", left, right] => Expr.sub <$> decode fuel left <*> decode fuel right
    | [.str "emit", .str label, tail] => Expr.emit label <$> decode fuel tail
    | [.str "if", condition, yes, no] =>
      match (← condition.getArr?.toOption).toList with
      | [.str "eq", left, right] =>
        Expr.branch <$> decode fuel left <*> decode fuel right <*> decode fuel yes <*> decode fuel no
      | _ => none
    | _ => none

def confirmParsed (text : String) (expected : Lean.Json) : IO Unit :=
  match Lean.Json.parse text with
  | .ok parsed =>
    if parsed.compress == expected.compress then pure ()
    else throw (IO.userError "Parsed SPG term disagrees with the generated JSON value")
  | .error reason => throw (IO.userError reason)

def interpret (source : Lean.Json) (n : Int) : Option Observation :=
  (decode 24 source).map (fun expression => deep expression n)

theorem checked_wire_correspondence (source : Lean.Json) (expression : Expr) (n : Int)
    (decoded : decode 24 source = some expression) :
    interpret source n = some (lower expression n) :=
  calc
    interpret source n = some (deep expression n) := by simp [interpret, decoded]
    _ = some (lower expression n) := congrArg some (lower_matches_deep expression n).symm

#print axioms lower_matches_deep
#print axioms checked_wire_correspondence

end ScopedConditional
