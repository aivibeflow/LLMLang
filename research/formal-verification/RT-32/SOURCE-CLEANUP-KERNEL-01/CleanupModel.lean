namespace Cleanup

structure Span where
  startLine : Nat
  endLine : Nat
  startByte : Nat
  endByte : Nat
  deriving Repr, DecidableEq

inductive Slot where
  | inner | outer
  deriving Repr, DecidableEq

inductive SlotState where
  | unopened | live | released | debt
  deriving Repr, DecidableEq

inductive Handle where
  | absent | caller | pending
  deriving Repr, DecidableEq

inductive Test where
  | x | y | constant (value : Bool)
  deriving Repr, DecidableEq

inductive Event where
  | openSlot (position : Span) (slot : Slot)
  | closeSlot (position : Span) (slot : Slot) (succeeded : Bool)
  | probe (position : Span) (tag : String) (value : Bool)
  | emit (position : Span) (tag : String)
  | stage (position : Span) (tag : String)
  | fail (position : Span) (tag : String)
  deriving Repr, DecidableEq

inductive Instruction where
  | openSlot (position : Span) (slot : Slot) (next : Nat)
  | closeSlot (position : Span) (slot : Slot) (ok error : Nat)
  | test (condition : Test) (yes no : Nat)
  | probe (position : Span) (tag : String) (condition : Test) (yes no : Nat)
  | emit (position : Span) (tag : String) (next : Nat)
  | stage (position : Span) (tag : String) (next : Nat)
  | fail (position : Span) (tag : String) (error : Nat)
  | returned | error | fallthrough
  deriving Repr, DecidableEq

structure Input where
  x : Bool
  y : Bool
  innerError : Bool
  outerError : Bool
  deriving Repr, DecidableEq

structure Frame where
  trace : List Event := []
  staged : Option String := none
  causes : List String := []
  inner : SlotState := .unopened
  outer : SlotState := .unopened
  deriving Repr

structure Observation where
  trace : List Event
  returned : Option String
  causes : List String
  inner : SlotState
  outer : SlotState
  handle : Handle
  deriving Repr, DecidableEq

structure Program where
  entry : Nat
  instructions : List Instruction
  deriving Repr

def truth (input : Input) : Test → Bool
  | .x => input.x
  | .y => input.y
  | .constant value => value

def setSlot (state : Frame) (value : SlotState) : Slot → Frame
  | .inner => {state with inner := value}
  | .outer => {state with outer := value}

def slotState (state : Frame) : Slot → SlotState
  | .inner => state.inner
  | .outer => state.outer

def closeFails (input : Input) : Slot → Bool
  | .inner => input.innerError
  | .outer => input.outerError

def slotName : Slot → String
  | .inner => "inner"
  | .outer => "outer"

def observe (state : Frame) (event : Event) : Frame :=
  {state with trace := event :: state.trace}

def terminal (state : Frame) (returned : Bool) : Observation :=
  let owner := match state.staged, returned with
    | none, _ => Handle.absent
    | some _, true => Handle.caller
    | some _, false => Handle.pending
  ⟨state.trace.reverse, (if returned then state.staged else none), state.causes,
    state.inner, state.outer, owner⟩

def evaluate (instructions : List Instruction) (input : Input) :
    Nat → Nat → Frame → Option Observation
  | 0, _, _ => none
  | fuel + 1, pc, state =>
    let run := evaluate instructions input fuel
    match instructions[pc]? with
    | none | some .fallthrough => none
    | some .returned => some (terminal state true)
    | some .error => some (terminal state false)
    | some (.test condition yes no) =>
      run (if truth input condition then yes else no) state
    | some (.probe span tag condition yes no) =>
      let value := truth input condition
      run (if value then yes else no) (observe state (.probe span tag value))
    | some (.openSlot span slot next) =>
      if slotState state slot == .unopened then
        run next (setSlot (observe state (.openSlot span slot)) .live slot)
      else none
    | some (.closeSlot span slot ok error) =>
      if slotState state slot == .live then
        let failed := closeFails input slot
        let updated := observe state (.closeSlot span slot (!failed))
        if failed then
          run error (setSlot {updated with causes := updated.causes ++ ["close:" ++ slotName slot]} .debt slot)
        else run ok (setSlot updated .released slot)
      else none
    | some (.emit span tag next) => run next (observe state (.emit span tag))
    | some (.stage span tag next) =>
      if state.staged.isNone then run next {observe state (.stage span tag) with staged := some tag}
      else none
    | some (.fail span tag error) =>
      run error {observe state (.fail span tag) with causes := [tag]}

def run (program : Program) (input : Input) : Option Observation :=
  evaluate program.instructions input (program.instructions.length + 1) program.entry {}

def resultSettled (input : Input) (observation : Observation) : Bool :=
  let expected (failed : Bool) := if failed then SlotState.debt else SlotState.released
  observation.inner == expected input.innerError &&
  observation.outer == expected input.outerError &&
  (observation.returned.isSome == (observation.handle == .caller)) &&
  ((observation.handle != .caller) || (!input.innerError && !input.outerError))

end Cleanup
