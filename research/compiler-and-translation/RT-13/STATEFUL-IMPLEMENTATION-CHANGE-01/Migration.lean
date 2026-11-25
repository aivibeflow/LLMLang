inductive Command where
  | credit (amount : Nat)
  | debit (amount : Nat)
  | read

inductive Reply where
  | credited (amount : Nat)
  | debited (amount : Nat)
  | refused
  | balance (amount : Nat)
  deriving DecidableEq

structure SplitState where
  credits : Nat
  debits : Nat
  valid : debits ≤ credits

inductive Provider where
  | direct (balance : Nat)
  | split (state : SplitState)

def abstractState : Provider → Nat
  | .direct balance => balance
  | .split state => state.credits - state.debits

def reference (balance : Nat) : Command → Nat × Reply
  | .credit amount => (balance + amount, .credited amount)
  | .debit amount =>
    if amount ≤ balance then (balance - amount, .debited amount) else (balance, .refused)
  | .read => (balance, .balance balance)

def execute : Provider → Command → Provider × Reply
  | .direct balance, command =>
    let result := reference balance command
    (.direct result.1, result.2)
  | .split state, .credit amount =>
    (.split ⟨state.credits + amount, state.debits,
      Nat.le_trans state.valid (Nat.le_add_right _ _)⟩, .credited amount)
  | .split state, .debit amount =>
    if allowed : amount ≤ state.credits - state.debits then
      (.split ⟨state.credits, state.debits + amount, by have valid := state.valid; omega⟩,
        .debited amount)
    else (.split state, .refused)
  | .split state, .read =>
    (.split state, .balance (state.credits - state.debits))

def migrate (state : Provider) (useSplit : Bool) : Provider :=
  let balance := abstractState state
  if useSplit then .split ⟨balance, 0, Nat.zero_le _⟩ else .direct balance

theorem migration_preserves_state (state : Provider) (useSplit : Bool) :
    abstractState (migrate state useSplit) = abstractState state := by
  cases useSplit <;> simp [migrate, abstractState]

theorem execution_refines (state : Provider) (command : Command) :
    let actual := execute state command
    (abstractState actual.1, actual.2) = reference (abstractState state) command := by
  cases state with
  | direct balance => rfl
  | split state =>
    have valid := state.valid
    cases command with
    | credit amount =>
      simp [execute, reference, abstractState]
      omega
    | debit amount =>
      by_cases allowed : amount ≤ state.credits - state.debits
      · simp [execute, reference, abstractState, allowed]
        omega
      · simp [execute, reference, abstractState, allowed]
    | read => rfl

inductive Action where
  | invoke (command : Command)
  | switch (toSplit : Bool)

def concreteTrace : List Action → Provider → List Reply
  | [], _ => []
  | .invoke command :: tail, state =>
    let result := execute state command
    result.2 :: concreteTrace tail result.1
  | .switch useSplit :: tail, state => concreteTrace tail (migrate state useSplit)

def abstractTrace : List Action → Nat → List Reply
  | [], _ => []
  | .invoke command :: tail, balance =>
    let result := reference balance command
    result.2 :: abstractTrace tail result.1
  | .switch _ :: tail, balance => abstractTrace tail balance

theorem complete_trace_refines (actions : List Action) (state : Provider) :
    concreteTrace actions state = abstractTrace actions (abstractState state) := by
  induction actions generalizing state with
  | nil => rfl
  | cons action tail inductionHypothesis =>
    cases action with
    | switch useSplit =>
      simp [concreteTrace, abstractTrace, inductionHypothesis, migration_preserves_state]
    | invoke command =>
      have step := execution_refines state command
      have states : abstractState (execute state command).1 =
          (reference (abstractState state) command).1 := congrArg Prod.fst step
      have replies : (execute state command).2 =
          (reference (abstractState state) command).2 := congrArg Prod.snd step
      simp [concreteTrace, abstractTrace, inductionHypothesis, states, replies]

#print axioms migration_preserves_state
#print axioms execution_refines
#print axioms complete_trace_refines
