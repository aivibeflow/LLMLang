import Lean

namespace LLMLang.GeneratedCall

abbrev Observation := Int × List String
abbrev Function := Int → Observation

def arg (n : Int) : Observation := (n, [])

def emit (label : String) (observation : Observation) : Observation :=
  (observation.1, label :: observation.2)

def add (left right : Observation) : Observation :=
  (left.1 + right.1, left.2 ++ right.2)

def invoke (provider : Function) (argument : Observation) : Observation :=
  let output := provider argument.1
  (output.1, argument.2 ++ output.2)

def conforms (trace : List (List String)) (function : Function) : Prop :=
  ∀ n, (function n).2 ∈ trace

end LLMLang.GeneratedCall
