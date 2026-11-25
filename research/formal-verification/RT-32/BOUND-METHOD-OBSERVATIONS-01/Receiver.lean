import Lean

namespace BoundMethod

inductive Side where
  | left
  | right

inductive Storage where
  | shared (value : Int)
  | separate (left right : Int)
  deriving DecidableEq

structure Context where
  leftBias : Int
  rightBias : Int
  storage : Storage
  deriving DecidableEq

inductive Action where
  | read (side : Side)
  | add (side : Side) (input : Int)
  | replace (side : Side) (value : Int)

abbrev Reply := Int × Int

def Storage.read : Storage → Side → Int
  | .shared value, _ => value
  | .separate left _, .left => left
  | .separate _ right, .right => right

def Storage.put : Storage → Side → Int → Storage
  | .shared _, _, value => .shared value
  | .separate _ right, .left, value => .separate value right
  | .separate left _, .right, value => .separate left value

def Context.bias (context : Context) : Side → Int
  | .left => context.leftBias
  | .right => context.rightBias

def step (context : Context) : Action → Reply × Context
  | .read side =>
    let prior := context.storage.read side
    ((prior, prior), context)
  | .add side input =>
    let prior := context.storage.read side
    let wanted := prior + context.bias side + input
    ((prior, wanted), { context with storage := context.storage.put side wanted })
  | .replace side value =>
    ((context.storage.read side, value), { context with storage := context.storage.put side value })

def trace (context : Context) : List Action → List Reply
  | [] => []
  | action :: remaining =>
    let (reply, next) := step context action
    reply :: trace next remaining

def probes : List (List Action) :=
  [[.read .left], [.read .right], [.add .left 0], [.add .right 0],
   [.replace .left 0, .read .right], [.replace .left 1, .read .right]]

def signature (context : Context) : List (List Reply) :=
  probes.map (trace context)

theorem completeProbes {left right : Context} (equal : signature left = signature right) : left = right := by
  rcases left with ⟨leftBiasL, leftBiasR, leftCells⟩
  rcases right with ⟨rightBiasL, rightBiasR, rightCells⟩
  cases leftCells <;> cases rightCells <;>
    simp [signature, probes, trace, step, Context.bias, Storage.read, Storage.put] at equal ⊢ <;>
    omega

theorem probe_equivalence (left right : Context) :
    signature left = signature right ↔ left = right :=
  ⟨completeProbes, congrArg signature⟩

theorem trace_equivalence (left right : Context) :
    (∀ actions : List Action, trace left actions = trace right actions) ↔ left = right := by
  constructor
  · intro equal
    apply completeProbes
    simp [signature, probes, equal]
  · intro equal actions
    rw [equal]

theorem probe_implies_every_trace {left right : Context} (equal : signature left = signature right)
    (actions : List Action) : trace left actions = trace right actions :=
  congrArg (fun context => trace context actions) (completeProbes equal)

theorem split_receiver_changes_trace :
    trace ⟨0, 0, .shared 0⟩ [.replace .left 1, .read .right] = [(0, 1), (1, 1)] ∧
      trace ⟨0, 0, .separate 0 0⟩ [.replace .left 1, .read .right] = [(0, 1), (0, 0)] :=
  ⟨rfl, rfl⟩

theorem changed_bias_changes_trace :
    trace ⟨0, 0, .shared 0⟩ [.add .right 0] = [(0, 0)] ∧
      trace ⟨0, 1, .shared 0⟩ [.add .right 0] = [(0, 1)] :=
  ⟨rfl, rfl⟩

theorem five_probes_miss_alias :
    (probes.take 5).map (trace ⟨0, 0, .shared 0⟩) =
      (probes.take 5).map (trace ⟨0, 0, .separate 0 0⟩) ∧
    signature ⟨0, 0, .shared 0⟩ ≠ signature ⟨0, 0, .separate 0 0⟩ := by
  refine ⟨rfl, ?_⟩
  intro equal
  cases completeProbes equal

#print axioms completeProbes
#print axioms probe_equivalence
#print axioms trace_equivalence
#print axioms probe_implies_every_trace
#print axioms split_receiver_changes_trace
#print axioms changed_bias_changes_trace
#print axioms five_probes_miss_alias

end BoundMethod
