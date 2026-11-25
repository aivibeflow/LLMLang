target triple = "riscv64-unknown-none-elf"

declare i64 @llvm.read_register.i64(metadata)

define i64 @read_sp() nounwind {
  %sp = call i64 @llvm.read_register.i64(metadata !0)
  ret i64 %sp
}

define void @memory_barrier() nounwind {
  fence seq_cst
  ret void
}

define void @translation_barrier() nounwind {
  call void asm sideeffect "sfence.vma", "~{memory}"()
  ret void
}

!0 = !{!"sp"}
