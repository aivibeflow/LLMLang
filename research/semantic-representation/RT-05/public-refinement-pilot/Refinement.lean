namespace ProviderPilot

inductive Verdict where
  | admit
  | reject
  | unknown
  deriving Repr, DecidableEq, BEq

abbrev Contract := List (Nat × List Nat)
abbrev Body := List (Nat × Option Nat)

structure Case where
  signatureMatches : Bool
  publicContract : Contract
  providedContract : Contract
  body : Body

def realizable (contract : Contract) : Bool :=
  !contract.isEmpty && contract.all (fun row => !row.2.isEmpty)

def refines (publicContract providedContract : Contract) : Bool :=
  realizable publicContract && realizable providedContract &&
    publicContract.all fun (input, allowed) =>
      match providedContract.find? (fun row => row.1 == input) with
      | none => false
      | some (_, provided) => provided.all fun observation => allowed.contains observation

def observe (body : Body) (input : Nat) : Option Nat :=
  (body.find? (fun row => row.1 == input)).bind Prod.snd

def checks (contract : Contract) (body : Body) : Verdict :=
  if !realizable contract then .reject
  else
    let rows := contract.map fun (input, allowed) =>
      match observe body input with
      | none => Verdict.unknown
      | some actual => if allowed.contains actual then Verdict.admit else Verdict.reject
    if rows.contains .reject then .reject
    else if rows.contains .unknown then .unknown
    else .admit

def decisions (c : Case) : List Verdict :=
  if !c.signatureMatches then [.reject, .reject, .reject]
  else
    [.admit, checks c.publicContract c.body,
      if refines c.publicContract c.providedContract then checks c.providedContract c.body
      else .reject]

end ProviderPilot
