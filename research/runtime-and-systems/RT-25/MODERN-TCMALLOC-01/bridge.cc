#include "tcmalloc/malloc_extension.h"

extern "C" int llmlang_tcmalloc_per_cpu_caches() {
  return tcmalloc::MallocExtension::PerCpuCachesActive() ? 1 : 0;
}
