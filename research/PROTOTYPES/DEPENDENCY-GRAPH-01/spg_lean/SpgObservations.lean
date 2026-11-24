import ObservableRewrite
import Lean.Data.Json

namespace SpgObservations

open ObservableRewrite

abbrev Shallow (s : ScalarSort) := Int → Run s.value

def literal (value : s.value) : Shallow s := fun _ => (.ok value, [])

def argument : Shallow .int := fun input => (.ok input, [])

def pairwise (op : Int → Int → s.value) (left right : Shallow .int) : Shallow s :=
  fun input => sequence (left input) fun l =>
    sequence (right input) fun r => (.ok (op l r), [])

def add (left right : Shallow .int) : Shallow .int := pairwise Int.add left right

def equal (left right : Shallow .int) : Shallow .bool := pairwise (· == ·) left right

def branch (test : Shallow .bool) (yes no : Shallow s) : Shallow s :=
  fun input => sequence (test input) fun bit => if bit then yes input else no input

def emit (event : Nat) (tail : Shallow s) : Shallow s :=
  fun input => let (result, trace) := tail input; (result, event :: trace)

def lower : Expr s → Shallow s
  | .integer value => literal value
  | .boolean value => literal value
  | .input => argument
  | .add left right => add (lower left) (lower right)
  | .equal left right => equal (lower left) (lower right)
  | .choose test yes no => branch (lower test) (lower yes) (lower no)
  | .emit event tail => emit event (lower tail)
  | .fail code => fun _ => (.error code, [])

theorem lower_preserves (expr : Expr s) (input : Int) :
    lower expr input = evaluate input expr := by
  induction expr with
  | integer | boolean | input | fail => rfl
  | add left right ihLeft ihRight => simp [lower, evaluate, add, pairwise, ihLeft, ihRight]
  | equal left right ihLeft ihRight => simp [lower, evaluate, equal, pairwise, ihLeft, ihRight]
  | choose test yes no ihTest ihYes ihNo => simp [lower, evaluate, branch, ihTest, ihYes, ihNo]
  | emit event tail ih => simp [lower, evaluate, emit, ih]

private def quote (label : String) : String := "\"" ++ label ++ "\""

private def arrayBytes (args : List String) : String := "[" ++ String.intercalate "," args ++ "]"

private def tagged (name : String) (args : List String) : String :=
  arrayBytes (quote name :: args)

def contractBytes (traces : List (List String)) : String :=
  arrayBytes (traces.map (fun trace => arrayBytes (trace.map quote)))

private def decimal (value : Int) : Option String :=
  if -2147483648 ≤ value ∧ value ≤ 2147483647 then some (toString value) else none

/-- Reconstruct the canonical SPG body from a typed witness. Events use their original labels. -/
def bodyBytes (labels : List String) : Expr s → Option String
  | .integer value => (decimal value).map (fun repr => tagged "literal" [repr])
  | .boolean value => some (tagged "literal" [if value then "true" else "false"])
  | .input => some (tagged "argument" ["0"])
  | .add left right => do
      return tagged "add" [← bodyBytes labels left, ← bodyBytes labels right]
  | .equal left right => do
      return tagged "eq" [← bodyBytes labels left, ← bodyBytes labels right]
  | .choose test yes no => do
      return tagged "if" [← bodyBytes labels test, ← bodyBytes labels yes, ← bodyBytes labels no]
  | .emit event tail => do
      return tagged "emit" [quote (← labels[event]?), ← bodyBytes labels tail]
  | .fail _ => none

def traceLabels (labels : List String) (trace : List Nat) : Option (List String) :=
  trace.mapM (fun index => labels[index]?)

def observation (labels : List String) (execution : Run Int) : Option (Int × List String) := do
  let value ← execution.1.toOption
  let trace ← traceLabels labels execution.2
  return (value, trace)

def traceAllowed (labels : List String) (contract : List (List String)) (run : Run Int) : Bool :=
  (traceLabels labels run.2).any contract.contains

#print axioms lower_preserves

end SpgObservations
