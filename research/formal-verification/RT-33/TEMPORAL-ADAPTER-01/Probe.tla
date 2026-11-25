---- MODULE Probe ----
EXTENDS Integers
VARIABLE
  \* @type: Int;
  x
Init == x = 0
Next == x' = IF x < 4 THEN x + 1 ELSE x
Safe == x >= 0 /\ x <= 4
TooLow == x <= 2
Eventually == <>(x = 4)
Spec == Init /\ [][Next]_x /\ WF_x(Next)
====
