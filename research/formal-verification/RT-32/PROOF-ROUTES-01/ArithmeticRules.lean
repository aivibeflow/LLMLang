set_option linter.unusedVariables false

theorem decreases (before stride : Int) (positive : 0 < stride) :
    before - stride < before := by omega

theorem staysNonnegative (before stride : Int) (enough : stride ≤ before) :
    0 ≤ before - stride := by omega

theorem transferConserves (first second total stride : Int) (invariant : first + second = total) :
    (first - stride) + (second + stride) = total := by omega

theorem initializes (first second total : Int) (input : first = total) (zero : second = 0) :
    first + second = total := by omega

theorem exits (first second total : Int) (invariant : first + second = total) (zero : first = 0) :
    second = total := by omega
