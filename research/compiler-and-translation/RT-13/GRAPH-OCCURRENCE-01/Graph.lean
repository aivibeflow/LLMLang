inductive Atom where
  | skip | read | write (value : Bool) | fail

inductive Mode where
  | strict | bind | left | right

inductive Result where
  | unit | read (value : Bool) | error

structure Observation where
  result : Result
  cell : Bool
  trace : List Nat

def atomMeaning (op : Atom) (initial : Bool) : Observation :=
  match op with
  | .skip => ⟨.unit, initial, []⟩
  | .read => ⟨.read initial, initial, [if initial then 1 else 0]⟩
  | .write value => ⟨.unit, value, [if value then 3 else 2]⟩
  | .fail => ⟨.error, initial, []⟩

def combine (mode : Mode) (left right : Bool → Observation) (initial : Bool) :
    Observation :=
  match mode with
  | .left => left initial
  | .right => right initial
  | .strict | .bind =>
    let first := left initial
    let short := match mode, first.result with | .bind, .error => true | _, _ => false
    if short then first else
      let last := right first.cell
      ⟨last.result, last.cell, first.trace ++ last.trace⟩

inductive Tree where
  | atom (op : Atom)
  | pair (mode : Mode) (left right : Tree)

def denote : Tree → Bool → Observation
  | .atom op => atomMeaning op
  | .pair mode left right => combine mode (denote left) (denote right)

inductive Node where
  | atom (op : Atom)
  | pair (mode : Mode) (left right : Nat)

def unfoldGraph (table : Nat → Node) : Nat → Nat → Option Tree
  | 0, _ => none
  | fuel + 1, root =>
    match table root with
    | .atom op => some (.atom op)
    | .pair mode left right =>
      (unfoldGraph table fuel left).bind fun l =>
        (unfoldGraph table fuel right).map fun r => .pair mode l r

def graphMeaning (table : Nat → Node) : Nat → Nat → Option (Bool → Observation)
  | 0, _ => none
  | fuel + 1, root =>
    match table root with
    | .atom op => some (atomMeaning op)
    | .pair mode left right =>
      (graphMeaning table fuel left).bind fun l =>
        (graphMeaning table fuel right).map fun r => combine mode l r

theorem occurrence_graph_matches_unfolding (table : Nat → Node) (fuel root : Nat) :
    graphMeaning table fuel root = (unfoldGraph table fuel root).map denote := by
  induction fuel generalizing root with
  | zero => rfl
  | succ fuel ih =>
    cases equation : table root with
    | atom op => simp [graphMeaning, unfoldGraph, equation, denote]
    | pair mode left right =>
      simp only [graphMeaning, unfoldGraph, equation, ih]
      cases unfoldGraph table fuel left <;> cases unfoldGraph table fuel right <;> rfl

def sharedRead (index : Nat) : Node :=
  if index = 0 then .atom .read else .pair .strict 0 0

theorem identical_edges_produce_two_events :
    ((graphMeaning sharedRead 2 1).map fun call => (call true).trace) = some [1, 1] := rfl

#print axioms occurrence_graph_matches_unfolding
#print axioms identical_edges_produce_two_events
