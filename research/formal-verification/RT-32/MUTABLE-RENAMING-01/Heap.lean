import Lean

namespace MutableRenaming

structure Renaming (Source Target : Type) where
  forward : Source → Target
  backward : Target → Source
  left : ∀ location, backward (forward location) = location
  right : ∀ location, forward (backward location) = location

@[simp] theorem Renaming.same (r : Renaming Source Target) {a b : Source} :
    r.forward a = r.forward b ↔ a = b := by
  constructor
  · intro equal
    simpa only [r.left] using congrArg r.backward equal
  · intro equal
    exact congrArg r.forward equal

structure Cell (Location : Type) where
  value : Int
  next : Option Location

abbrev Heap (Location : Type) := Location → Cell Location
abbrev Roots (Location : Type) := Fin 3 → Location
abbrev Path := Fin 3 × Nat

def renameCell (r : Renaming Source Target) (cell : Cell Source) : Cell Target :=
  ⟨cell.value, cell.next.map r.forward⟩

def renameHeap (r : Renaming Source Target) (heap : Heap Source) : Heap Target :=
  fun location => renameCell r (heap (r.backward location))

def renameRoots (r : Renaming Source Target) (roots : Roots Source) : Roots Target :=
  fun index => r.forward (roots index)

@[simp] theorem lookup_forward (r : Renaming Source Target) (heap : Heap Source) (location : Source) :
    renameHeap r heap (r.forward location) = renameCell r (heap location) := by
  simp [renameHeap, r.left]

def update [DecidableEq Location] (heap : Heap Location) (location : Location)
    (cell : Cell Location) : Heap Location :=
  fun address => if address = location then cell else heap address

@[simp] theorem rename_update [DecidableEq Source] [DecidableEq Target] (r : Renaming Source Target)
    (heap : Heap Source) (location : Source) (cell : Cell Source) :
    renameHeap r (update heap location cell) =
      update (renameHeap r heap) (r.forward location) (renameCell r cell) := by
  funext address
  have eq_iff : r.backward address = location ↔ address = r.forward location := by
    constructor
    · intro equal
      simpa only [r.right] using congrArg r.forward equal
    · intro equal
      simpa only [r.left] using congrArg r.backward equal
  by_cases equal : address = r.forward location
  · simp [renameHeap, update, equal, r.left]
  · simp [renameHeap, update, equal, mt eq_iff.mp equal]

def follow (heap : Heap Location) : Nat → Option Location → Option Location
  | 0, location => location
  | depth + 1, location => follow heap depth (location.bind fun item => (heap item).next)

def resolve (heap : Heap Location) (roots : Roots Location) (path : Path) : Option Location :=
  follow heap path.2 (some (roots path.1))

@[simp] theorem rename_follow (r : Renaming Source Target) (heap : Heap Source)
    (depth : Nat) (address : Option Source) :
    follow (renameHeap r heap) depth (address.map r.forward) = (follow heap depth address).map r.forward := by
  induction depth generalizing address with
  | zero => rfl
  | succ depth ih =>
    cases address with
    | none => exact ih none
    | some address => simp [follow, ih, renameCell]

@[simp] theorem rename_resolve (r : Renaming Source Target) (heap : Heap Source)
    (roots : Roots Source) (path : Path) :
    resolve (renameHeap r heap) (renameRoots r roots) path = (resolve heap roots path).map r.forward := by
  exact rename_follow r heap path.2 (some (roots path.1))

inductive Action where
  | read (path : Path)
  | add (path : Path) (delta : Int)
  | same (left right : Path)
  | link (owner target : Path)

inductive Reply where
  | missing
  | value (value : Int)
  | boolean (value : Bool)
  deriving DecidableEq, Repr

def same [DecidableEq Location] : Option Location → Option Location → Bool
  | some left, some right => decide (left = right)
  | _, _ => false

@[simp] theorem rename_same [DecidableEq Source] [DecidableEq Target]
    (r : Renaming Source Target) (left right : Option Source) :
    same (left.map r.forward) (right.map r.forward) = same left right := by
  cases left <;> cases right <;> simp [same]

def step [DecidableEq Location] (roots : Roots Location) (heap : Heap Location) :
    Action → Reply × Heap Location
  | .read path =>
    match resolve heap roots path with
    | none => (.missing, heap)
    | some cell => (.value (heap cell).value, heap)
  | .add path delta =>
    match resolve heap roots path with
    | none => (.missing, heap)
    | some location =>
      let nextValue := (heap location).value + delta
      (.value nextValue, update heap location ⟨nextValue, (heap location).next⟩)
  | .same left right => (.boolean (same (resolve heap roots left) (resolve heap roots right)), heap)
  | .link owner target =>
    match resolve heap roots owner with
    | none => (.missing, heap)
    | some location =>
      let nextLocation := resolve heap roots target
      (.boolean nextLocation.isSome, update heap location ⟨(heap location).value, nextLocation⟩)

@[simp] theorem rename_step [DecidableEq Source] [DecidableEq Target] (r : Renaming Source Target)
    (heap : Heap Source) (roots : Roots Source) (action : Action) :
    step (renameRoots r roots) (renameHeap r heap) action =
      let result := step roots heap action
      (result.1, renameHeap r result.2) := by
  cases action with
  | read path =>
    cases found : resolve heap roots path <;> simp [step, found, renameCell]
  | add path delta =>
    cases found : resolve heap roots path <;> simp [step, found, renameCell]
  | same left right => simp [step]
  | link owner target =>
    cases found : resolve heap roots owner <;> simp [step, found, renameCell]

def run [DecidableEq Location] (roots : Roots Location) (heap : Heap Location) :
    List Action → List Reply × Heap Location
  | [] => ([], heap)
  | action :: actions =>
    let (reply, nextHeap) := step roots heap action
    let (replies, finalHeap) := run roots nextHeap actions
    (reply :: replies, finalHeap)

theorem rename_run [DecidableEq Source] [DecidableEq Target] (r : Renaming Source Target)
    (heap : Heap Source) (roots : Roots Source) (actions : List Action) :
    run (renameRoots r roots) (renameHeap r heap) actions =
      let result := run roots heap actions
      (result.1, renameHeap r result.2) := by
  induction actions generalizing heap with
  | nil => rfl
  | cons action rest ih => simp [run, ih]

theorem same_observations [DecidableEq Source] [DecidableEq Target] (r : Renaming Source Target)
    (heap : Heap Source) (roots : Roots Source) (actions : List Action) :
    (run (renameRoots r roots) (renameHeap r heap) actions).1 = (run roots heap actions).1 :=
  congrArg Prod.fst (rename_run r heap roots actions)

def runArchive (rootIds : Fin 3 → Nat) (cells : List (Nat × Int × Option Nat))
    (actions : List Action) : List Reply :=
  let heap := fun location =>
    match cells.find? (fun row => row.1 == location) with
    | none => ⟨0, none⟩
    | some (_, value, next) => ⟨value, next⟩
  (run rootIds heap actions).1

def splitControl : List Action := [.add (0, 0) 1, .read (1, 0), .same (0, 0) (1, 0)]
def oneCell : List (Nat × Int × Option Nat) := [(0, 10, some 0)]
def splitCells : List (Nat × Int × Option Nat) := [(0, 10, some 0), (1, 10, some 1), (2, 10, some 2)]

theorem splitting_changes_trace :
    runArchive (fun _ => 0) oneCell splitControl = [.value 11, .value 11, .boolean true] ∧
    runArchive Fin.val splitCells splitControl = [.value 11, .value 10, .boolean false] := ⟨rfl, rfl⟩

#print axioms Renaming.same
#print axioms lookup_forward
#print axioms rename_update
#print axioms rename_follow
#print axioms rename_resolve
#print axioms rename_same
#print axioms rename_step
#print axioms rename_run
#print axioms same_observations
#print axioms splitting_changes_trace

end MutableRenaming
