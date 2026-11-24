target triple = "thumbv7m-none-eabi"

define i32 @sample_pair(ptr %csr) nounwind {
entry:
  %first = load volatile i32, ptr %csr, align 4
  %second = load volatile i32, ptr %csr, align 4
  %first_bit = lshr i32 %first, 16
  %second_bit = lshr i32 %second, 16
  %upper = shl i32 %first_bit, 1
  %packed_first = and i32 %upper, 2
  %packed_second = and i32 %second_bit, 1
  %pair = or i32 %packed_first, %packed_second
  ret i32 %pair
}
