#ifdef _WIN32
#include "generated.h"
#define EXPORT __declspec(dllexport)
#else
#include "mock_api.h"
#define EXPORT
#endif

EXPORT HANDLE open_reader(LPCWSTR path, DWORD *error) {
    HANDLE handle = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    *error = handle == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    return handle;
}

EXPORT BOOL close_owned(HANDLE handle, DWORD *error) {
    BOOL closed = CloseHandle(handle);
    *error = closed ? 0 : GetLastError();
    return closed;
}
