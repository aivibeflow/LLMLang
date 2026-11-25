#ifndef MOCK_API_H
#define MOCK_API_H
#include <stdint.h>

typedef uint32_t DWORD;
typedef int BOOL;
typedef void *HANDLE;
typedef const uint16_t *LPCWSTR;
#define GENERIC_READ UINT32_C(0x80000000)
#define FILE_SHARE_READ 1
#define OPEN_EXISTING 3
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)

HANDLE CreateFileW(LPCWSTR path, DWORD access, DWORD sharing, void *security,
                   DWORD disposition, DWORD flags, HANDLE template_file);
DWORD GetLastError(void);
BOOL CloseHandle(HANDLE handle);

#endif
