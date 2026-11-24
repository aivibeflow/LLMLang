/- Deep embedding of the register-state projection of finite transition fixtures. -/
namespace TransitionState

abbrev Registers := List Int

inductive IntExpr where
  | literal (value : Int)
  | register (index : Nat)
  | add (left right : IntExpr)
  | sub (left right : IntExpr)

def evalInt (state : Registers) : IntExpr → Int
  | .literal value => value
  | .register index => state[index]?.getD 0
  | .add left right => evalInt state left + evalInt state right
  | .sub left right => evalInt state left - evalInt state right

inductive BoolExpr where
  | eq (left right : IntExpr)
  | le (left right : IntExpr)
  | and (left right : BoolExpr)
  | or (left right : BoolExpr)
  | not (value : BoolExpr)

def evalBool (state : Registers) : BoolExpr → Bool
  | .eq left right => evalInt state left == evalInt state right
  | .le left right => decide (evalInt state left ≤ evalInt state right)
  | .and left right => evalBool state left && evalBool state right
  | .or left right => evalBool state left || evalBool state right
  | .not value => !evalBool state value

inductive Program where
  | done
  | assign (index : Nat) (value : IntExpr) (rest : Program)
  | branch (guard : BoolExpr) (yes no rest : Program)

def run (state : Registers) : Program → Registers
  | .done => state
  | .assign index value rest => run (state.set index (evalInt state value)) rest
  | .branch guard yes no rest =>
      run (if evalBool state guard then run state yes else run state no) rest

def observe (state : Registers) : List Program → List Registers
  | [] => []
  | action :: rest =>
      let next := run state action
      next :: observe next rest

end TransitionState
