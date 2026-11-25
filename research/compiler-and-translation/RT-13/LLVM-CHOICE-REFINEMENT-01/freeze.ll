define i32 @stable(i32 noundef %r, i32 noundef %unknown) {
  %arg = trunc i32 %r to i1
  %arbitrary = trunc i32 %unknown to i1
  %input = select i1 %arbitrary, i1 poison, i1 %arg
  %bit = freeze i1 %input
  %neg = xor i1 %bit, true
  %wide = zext i1 %bit to i32
  %high = shl i32 %wide, 1
  %low = zext i1 %neg to i32
  %result = or i32 %high, %low
  ret i32 %result
}

define i32 @independent(i32 noundef %r, i32 noundef %unknown) {
  %arg = trunc i32 %r to i1
  %arbitrary = trunc i32 %unknown to i1
  %input = select i1 %arbitrary, i1 poison, i1 %arg
  %left = freeze i1 %input
  %right = freeze i1 %input
  %neg = xor i1 %right, true
  %wide = zext i1 %left to i32
  %high = shl i32 %wide, 1
  %low = zext i1 %neg to i32
  %result = or i32 %high, %low
  ret i32 %result
}

define i32 @pin(i32 noundef %r, i32 noundef %unknown) {
  %arg = trunc i32 %r to i1
  %arbitrary = trunc i32 %unknown to i1
  %bit = select i1 %arbitrary, i1 false, i1 %arg
  %neg = xor i1 %bit, true
  %wide = zext i1 %bit to i32
  %high = shl i32 %wide, 1
  %low = zext i1 %neg to i32
  %result = or i32 %high, %low
  ret i32 %result
}
