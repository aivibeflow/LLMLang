.text
.global local_leaf
.type local_leaf,@function
local_leaf:
  addi a2, a2, 1
  ret
.size local_leaf, .-local_leaf
