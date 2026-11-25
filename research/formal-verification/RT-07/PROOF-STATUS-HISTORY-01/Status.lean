namespace ProofStatusHistory

structure Evidence where
  checkedProof : Bool
  checkedCounterexample : Bool
  incompleteAttempt : Bool
  deriving DecidableEq

def merge (left right : Evidence) : Evidence :=
  ⟨left.checkedProof || right.checkedProof,
   left.checkedCounterexample || right.checkedCounterexample,
   left.incompleteAttempt || right.incompleteAttempt⟩

theorem mergeComm (left right : Evidence) : merge left right = merge right left := by
  cases left
  cases right
  simp [merge, Bool.or_comm]

theorem mergeAssoc (a b c : Evidence) : merge (merge a b) c = merge a (merge b c) := by
  cases a
  cases b
  cases c
  simp [merge, Bool.or_assoc]

theorem mergeIdempotent (value : Evidence) : merge value value = value := by
  cases value
  simp [merge]

inductive Status
  | candidate | unknown | checked | proven | refuted | conflict
  deriving DecidableEq

def project (openPremise : Bool) (evidence : Evidence) : Status :=
  if evidence.checkedCounterexample then
    if evidence.checkedProof && !openPremise then .conflict else .refuted
  else if evidence.checkedProof then
    if openPremise then .checked else .proven
  else if evidence.incompleteAttempt then .unknown else .candidate

theorem cannotProveWithOpenPremise (evidence : Evidence) :
    project true evidence ≠ .proven := by
  obtain ⟨proof, witness, incomplete⟩ := evidence
  cases proof <;> cases witness <;> cases incomplete <;> decide

theorem rejectedReceiptIsNotACounterexample (openPremise : Bool) :
    project openPremise ⟨false, false, true⟩ = .unknown := rfl

theorem incompleteDoesNotOverwriteProof (openPremise : Bool) :
    project openPremise (merge ⟨true, false, false⟩ ⟨false, false, true⟩) =
    project openPremise ⟨true, false, false⟩ := rfl

#print axioms mergeComm
#print axioms mergeAssoc
#print axioms mergeIdempotent
#print axioms cannotProveWithOpenPremise
#print axioms rejectedReceiptIsNotACounterexample
#print axioms incompleteDoesNotOverwriteProof

end ProofStatusHistory
