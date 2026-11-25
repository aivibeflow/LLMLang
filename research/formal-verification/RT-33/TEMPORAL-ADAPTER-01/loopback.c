#define _GNU_SOURCE
#include <dlfcn.h>
#include <netinet/in.h>
#include <sys/socket.h>

int bind(int fd, const struct sockaddr *address, socklen_t length)
{
    int (*real_bind)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "bind");
    if (address && address->sa_family == AF_INET && length == sizeof(struct sockaddr_in)) {
        struct sockaddr_in revised = *(const struct sockaddr_in *)address;
        if (revised.sin_addr.s_addr == htonl(INADDR_ANY)) {
            revised.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            return real_bind(fd, (const struct sockaddr *)&revised, length);
        }
    }
    if (address && address->sa_family == AF_INET6 && length == sizeof(struct sockaddr_in6)) {
        struct sockaddr_in6 revised = *(const struct sockaddr_in6 *)address;
        if (IN6_IS_ADDR_UNSPECIFIED(&revised.sin6_addr)) {
            revised.sin6_addr = in6addr_loopback;
            return real_bind(fd, (const struct sockaddr *)&revised, length);
        }
    }
    return real_bind(fd, address, length);
}
