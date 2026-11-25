define i32 @guarded_shift(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ult i8 %b, 8
  br i1 %valid, label %compute, label %refused
compute:
  %result = shl i8 %a, %b
  %widened = zext i8 %result to i32
  ret i32 %widened
refused:
  ret i32 256
}

define i32 @masked_shift(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ult i8 %b, 8
  %result = shl i8 %a, %b
  %widened = zext i8 %result to i32
  %selected = select i1 %valid, i32 %widened, i32 256
  ret i32 %selected
}

define i32 @guarded_div(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ne i8 %b, 0
  br i1 %valid, label %compute, label %refused
compute:
  %result = udiv i8 %a, %b
  %widened = zext i8 %result to i32
  ret i32 %widened
refused:
  ret i32 256
}

define i32 @sanitized_div(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ne i8 %b, 0
  %safe = select i1 %valid, i8 %b, i8 1
  %result = udiv i8 %a, %safe
  %widened = zext i8 %result to i32
  %selected = select i1 %valid, i32 %widened, i32 256
  ret i32 %selected
}

define i32 @eager_div(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ne i8 %b, 0
  %result = udiv i8 %a, %b
  %widened = zext i8 %result to i32
  %selected = select i1 %valid, i32 %widened, i32 256
  ret i32 %selected
}

define i32 @eager_frozen_div(i32 %x, i32 %y) {
entry:
  %a = trunc i32 %x to i8
  %b = trunc i32 %y to i8
  %valid = icmp ne i8 %b, 0
  %result = udiv i8 %a, %b
  %frozen = freeze i8 %result
  %widened = zext i8 %frozen to i32
  %selected = select i1 %valid, i32 %widened, i32 256
  ret i32 %selected
}
