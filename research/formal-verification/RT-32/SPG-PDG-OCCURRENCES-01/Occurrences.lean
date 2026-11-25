structure Observation where
  value : Int
  trace : List Nat

def sumCalls (first second : Int → Observation) (input : Int) : Observation :=
  let left := first input
  let right := second input
  ⟨left.value + right.value, left.trace ++ right.trace⟩

theorem preserve_two_call_occurrences (first second : Int → Observation) (input : Int)
    (left right : List Nat) (leftProof : (first input).trace = left)
    (rightProof : (second input).trace = right) :
    (sumCalls first second input).trace = left ++ right :=
  (congrArg (fun trace => trace ++ (second input).trace) leftProof).trans
    (congrArg (fun trace => left ++ trace) rightProof)

theorem repeated_provider_has_repeated_trace (provider : Int → Observation) (input : Int)
    (trace : List Nat) (contract : (provider input).trace = trace) :
    (sumCalls provider provider input).trace = trace ++ trace :=
  preserve_two_call_occurrences provider provider input trace trace contract contract

#print axioms preserve_two_call_occurrences
#print axioms repeated_provider_has_repeated_trace
