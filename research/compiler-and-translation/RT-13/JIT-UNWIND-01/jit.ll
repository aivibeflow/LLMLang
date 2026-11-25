source_filename = "source.c"
target triple = "x86_64-unknown-linux-gnu"

define i32 @jit_step(i32 %input, ptr %callback) #0 !dbg !4 {
  %observed = call i32 %callback(i32 %input), !dbg !11
  %result = add i32 %observed, 1, !dbg !12
  ret i32 %result, !dbg !12
}

attributes #0 = { noinline nounwind uwtable "frame-pointer"="all" }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!7, !8}
!0 = distinct !DICompileUnit(language: DW_LANG_C11, file: !1, producer: "LLMLang RT-13 fixture", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug)
!1 = !DIFile(filename: "source.c", directory: "/llmlang/rt13")
!2 = !DIBasicType(name: "u32", size: 32, encoding: DW_ATE_unsigned)
!3 = !DISubroutineType(types: !{!2, !2, !10})
!4 = distinct !DISubprogram(name: "jit_step", scope: !1, file: !1, line: 3, type: !3, scopeLine: 3, spFlags: DISPFlagDefinition, unit: !0)
!5 = !DISubroutineType(types: !{!2, !2})
!7 = !{i32 2, !"Dwarf Version", i32 4}
!8 = !{i32 2, !"Debug Info Version", i32 3}
!10 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !5, size: 64)
!11 = !DILocation(line: 4, column: 20, scope: !4)
!12 = !DILocation(line: 5, column: 5, scope: !4)
