#ifndef EVIDENCE_API_H
#define EVIDENCE_API_H

typedef unsigned int u32;
typedef unsigned long long u64;

struct record {
    u64 sequence;
    u32 state;
    u32 status;
};

_Static_assert(sizeof(long) == 4 && sizeof(void *) == 8, "Windows LLP64");
_Static_assert(sizeof(struct record) == 16 && _Alignof(struct record) == 8, "record geometry");
_Static_assert(__builtin_offsetof(struct record, status) == 12, "field geometry");

#if defined(WRONG_EXPORT)
#define record_step renamed_step
#endif
#if defined(EXPORT_DLL)
#define API __declspec(dllexport)
#elif defined(IMPORT_DLL)
#define API __declspec(dllimport)
#else
#define API
#endif

API struct record record_step(struct record current, u32 delta);
#endif
