namespace ClosedStateResult

inductive Result where
  | unit
  | read (value : Bool)
  | failed
  deriving DecidableEq

inductive Event where
  | read (value : Bool)
  | write (value : Bool)
  deriving DecidableEq

inductive Command where
  | skip
  | fail
  | read
  | write (value : Bool)
  | branch (choose : Bool) (left right : Command)
  | strict (first second : Command)
  | bind (first second : Command)

structure Observation where
  result : Result
  cell : Bool
  events : List Event
  deriving DecidableEq

def followedBy (first second : Observation) : Observation :=
  { second with events := first.events ++ second.events }

def denote : Command → Bool → Observation
  | .skip, cell => ⟨.unit, cell, []⟩
  | .fail, cell => ⟨.failed, cell, []⟩
  | .read, cell => ⟨.read cell, cell, [.read cell]⟩
  | .write value, _ => ⟨.unit, value, [.write value]⟩
  | .branch choose left right, cell => if choose then denote left cell else denote right cell
  | .strict first second, cell =>
    let a := denote first cell
    followedBy a (denote second a.cell)
  | .bind first second, cell =>
    let a := denote first cell
    match a.result with
    | .failed => a
    | _ => followedBy a (denote second a.cell)

abbrev Postcondition := Result → Bool → List Event → Prop

def wp : Command → Postcondition → Bool → List Event → Prop
  | .skip, post, cell, events => post .unit cell events
  | .fail, post, cell, events => post .failed cell events
  | .read, post, cell, events => post (.read cell) cell (events ++ [.read cell])
  | .write value, post, _, events => post .unit value (events ++ [.write value])
  | .branch choose left right, post, cell, events =>
    if choose then wp left post cell events else wp right post cell events
  | .strict first second, post, cell, events =>
    wp first (fun _ state history => wp second post state history) cell events
  | .bind first second, post, cell, events =>
    wp first (fun result state history =>
      match result with
      | .failed => post result state history
      | _ => wp second post state history) cell events

theorem wp_agrees (command : Command) (post : Postcondition) (cell : Bool)
    (prior : List Event) :
    wp command post cell prior ↔
      let observed := denote command cell
      post observed.result observed.cell (prior ++ observed.events) := by
  induction command generalizing post cell prior with
  | skip => simp [wp, denote]
  | fail => simp [wp, denote]
  | read => rfl
  | write value => rfl
  | branch choose left right leftIH rightIH =>
    cases choose <;> simp [wp, denote, leftIH, rightIH]
  | strict first second firstIH secondIH =>
    simp [wp, denote, followedBy, firstIH, secondIH, List.append_assoc]
  | bind first second firstIH secondIH =>
    simp only [wp, denote, firstIH]
    cases h : (denote first cell).result <;>
      simp [h, followedBy, secondIH, List.append_assoc]

def PreservesPosts (old new : Command) : Prop :=
  ∀ post cell prior, wp old post cell prior → wp new post cell prior

def SameObservation (old new : Command) : Prop :=
  ∀ cell, denote old cell = denote new cell

theorem preserves_posts_iff_same_observation (old new : Command) :
    PreservesPosts old new ↔ SameObservation old new := by
  constructor
  · intro preserves cell
    let target := denote old cell
    let post : Postcondition := fun result state events => target = ⟨result, state, events⟩
    have original : wp old post cell [] := (wp_agrees old post cell []).mpr (by
      simp [post, target])
    have replacement := preserves post cell [] original
    have exactPost := (wp_agrees new post cell []).mp replacement
    simpa [post, target] using exactPost
  · intro same post cell prior original
    have exactPost := (wp_agrees old post cell prior).mp original
    rw [same cell] at exactPost
    exact (wp_agrees new post cell prior).mpr exactPost

def restoredCell := Command.strict (.write true) (.write false)

theorem same_final_cell_and_result :
    ((denote .skip false).result, (denote .skip false).cell) =
    ((denote restoredCell false).result, (denote restoredCell false).cell) := by rfl

theorem restore_not_substitutable_for_all_posts :
    ¬ PreservesPosts .skip restoredCell := by
  intro h
  have observation := (preserves_posts_iff_same_observation .skip restoredCell).mp h false
  have impossible := congrArg Observation.events observation
  simp [denote, restoredCell, followedBy] at impossible

#print axioms wp_agrees
#print axioms preserves_posts_iff_same_observation
#print axioms same_final_cell_and_result
#print axioms restore_not_substitutable_for_all_posts

end ClosedStateResult
