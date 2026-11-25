import Init

namespace ResourceSchedule

inductive Command where
  | target | peer | cancel
  deriving DecidableEq

inductive Order where
  | tpc | tcp | ptc | pct | ctp | cpt
  deriving DecidableEq

def Order.commands : Order → List Command
  | .tpc => [.target, .peer, .cancel]
  | .tcp => [.target, .cancel, .peer]
  | .ptc => [.peer, .target, .cancel]
  | .pct => [.peer, .cancel, .target]
  | .ctp => [.cancel, .target, .peer]
  | .cpt => [.cancel, .peer, .target]

structure State (α : Type) where
  value : α
  targetDone : Bool
  cancelled : Bool
  terminalOrder : List Command

def initial (value : α) : State α := ⟨value, false, false, []⟩

def step (target peer : α → α) (state : State α) : Command → State α
  | .target => { state with
      value := if state.cancelled then state.value else target state.value
      targetDone := true
      terminalOrder := state.terminalOrder ++ [.target] }
  | .peer => { state with
      value := peer state.value
      terminalOrder := state.terminalOrder ++ [.peer] }
  | .cancel => { state with
      cancelled := !state.targetDone
      terminalOrder := state.terminalOrder ++ [.cancel] }

def run (target peer : α → α) (value : α) (order : Order) : State α :=
  order.commands.foldl (step target peer) (initial value)

def baseline (target peer : α → α) (value : α) : α := peer (target value)

def scalar (target peer : α → α) (value : α) (order : Order) : α :=
  (run target peer value order).value

def normalForm (target peer : α → α) (value : α) : Order → α
  | .tpc | .tcp => peer (target value)
  | .ptc => target (peer value)
  | .pct | .ctp | .cpt => peer value

theorem scalar_normal_form (target peer : α → α) (value : α) (order : Order) :
    scalar target peer value order = normalForm target peer value order := by
  cases order <;> rfl

theorem invariant_scalar_iff (target peer : α → α) (value : α) :
    (∀ order, scalar target peer value order = baseline target peer value) ↔
    (target (peer value) = peer (target value) ∧ peer value = peer (target value)) := by
  constructor
  · intro invariant
    exact ⟨invariant .ptc, invariant .ctp⟩
  · intro conditions order
    rcases conditions with ⟨commutes, noCancellationDifference⟩
    cases order
    · rfl
    · rfl
    · exact commutes
    · exact noCancellationDifference
    · exact noCancellationDifference
    · exact noCancellationDifference

theorem terminal_order_projection (target peer : α → α) (value : α) (order : Order) :
    (run target peer value order).terminalOrder = order.commands := by
  cases order <;> rfl

theorem terminal_order_injective (target peer : α → α) (value : α) (a b : Order)
    (equal : (run target peer value a).terminalOrder = (run target peer value b).terminalOrder) :
    a = b := by
  rw [terminal_order_projection, terminal_order_projection] at equal
  cases a <;> cases b <;> first | rfl | cases equal

#print axioms scalar_normal_form
#print axioms invariant_scalar_iff
#print axioms terminal_order_projection
#print axioms terminal_order_injective

end ResourceSchedule

private def update (change : Int) (granted : Bool) (value : Int) : Int :=
  if granted && decide (0 ≤ value + change) then value + change else value

private def replayLine (line : String) : IO Unit := do
  let values := (line.splitOn ",").map String.toInt?
  match values with
  | [some initial, some t, some p, some grantT, some grantP] =>
    let orders : List ResourceSchedule.Order := [.tpc, .tcp, .ptc, .pct, .ctp, .cpt]
    let outcomes := orders.map (ResourceSchedule.scalar (update t (grantT == 1))
      (update p (grantP == 1)) initial)
    IO.println (String.intercalate "," (outcomes.map toString))
  | _ => throw (IO.userError s!"Invalid scope row: {line}")

def main (args : List String) : IO Unit := do
  match args with
  | [path] =>
    let body ← IO.FS.readFile path
    for line in body.splitOn "\n" do
      unless line.isEmpty do
        replayLine line
  | _ => throw (IO.userError "Expected one input matrix path")
