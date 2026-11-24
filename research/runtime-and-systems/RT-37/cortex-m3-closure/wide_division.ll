target triple = "thumbv7m-none-eabi"

define i32 @step(i32 %previous, i32 %sample, i32 %valid) nounwind {
entry:
  %p = zext i32 %previous to i64
  %numerator = shl i64 %p, 32
  %s = zext i32 %sample to i64
  %denominator = add i64 %s, 1
  %quotient = udiv i64 %numerator, %denominator
  %result = trunc i64 %quotient to i32
  ret i32 %result
}
