---- MODULE Counter ----
EXTENDS Integers

VARIABLE
  \* @type: Int;
  x

Limit == 4
Init == x = 0
Next == /\ x < Limit
        /\ x' = x + 1
Spec == Init /\ [][Next]_x /\ WF_x(Next)
Safe == x \in 0..Limit
EventuallyBound == <>(x = Limit)

====
