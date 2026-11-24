target triple = "thumbv7m-none-eabi"

define i32 @reserve_fixed(ptr %cursor, i32 %size, i32 %alignment) nounwind section ".text.reserve_fixed" {
entry:
  %nonempty = icmp ne i32 %size, 0
  %fits_slot = icmp ule i32 %size, 16
  %size_ok = and i1 %nonempty, %fits_slot
  %mask = sub i32 %alignment, 1
  %low_bits = and i32 %alignment, %mask
  %power_of_two = icmp eq i32 %low_bits, 0
  %mask_ok = icmp ult i32 %mask, 16
  %alignment_ok = and i1 %power_of_two, %mask_ok
  %shape_ok = and i1 %size_ok, %alignment_ok
  br i1 %shape_ok, label %check_slot, label %fail
check_slot:
  %current = load i32, ptr %cursor, align 4
  %located = icmp ult i32 %current, 64
  %low = and i32 %current, 15
  %exact_slot = icmp eq i32 %low, 0
  %available = and i1 %located, %exact_slot
  br i1 %available, label %reserve, label %fail
reserve:
  %end = add i32 %current, 16
  store i32 %end, ptr %cursor, align 4
  ret i32 %current
fail:
  ret i32 -1
}

define i32 @reserve_bump(ptr %cursor, i32 %size, i32 %alignment) nounwind section ".text.reserve_bump" {
entry:
  %nonempty = icmp ne i32 %size, 0
  %within_capacity = icmp ule i32 %size, 64
  %size_ok = and i1 %nonempty, %within_capacity
  %mask = sub i32 %alignment, 1
  %low_bits = and i32 %alignment, %mask
  %power_of_two = icmp eq i32 %low_bits, 0
  %mask_ok = icmp ult i32 %mask, 16
  %alignment_ok = and i1 %power_of_two, %mask_ok
  %shape_ok = and i1 %size_ok, %alignment_ok
  br i1 %shape_ok, label %check_cursor, label %fail
check_cursor:
  %current = load i32, ptr %cursor, align 4
  %located = icmp ule i32 %current, 64
  br i1 %located, label %round_up, label %fail
round_up:
  %rounded = add i32 %current, %mask
  %inverse = xor i32 %mask, -1
  %start = and i32 %rounded, %inverse
  %end = add i32 %start, %size
  %available = icmp ule i32 %end, 64
  br i1 %available, label %reserve, label %fail
reserve:
  store i32 %end, ptr %cursor, align 4
  ret i32 %start
fail:
  ret i32 -1
}
