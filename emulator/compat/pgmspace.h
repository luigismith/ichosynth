// pgmspace.h — desktop shim. On AVR/Teensy this provides flash-memory access;
// on desktop, PROGMEM data is just normal memory, so the pgm_read_* helpers are
// plain dereferences.
#ifndef NI404_COMPAT_PGMSPACE_H
#define NI404_COMPAT_PGMSPACE_H

#include <cstdint>
#include <cstring>

#ifndef PROGMEM
#define PROGMEM
#endif
#ifndef PGM_P
#define PGM_P const char *
#endif
#ifndef PSTR
#define PSTR(s) (s)
#endif

#define pgm_read_byte(addr)      (*(const uint8_t  *)(addr))
#define pgm_read_byte_near(addr) (*(const uint8_t  *)(addr))
#define pgm_read_word(addr)      (*(const uint16_t *)(addr))
#define pgm_read_word_near(addr) (*(const uint16_t *)(addr))
#define pgm_read_dword(addr)     (*(const uint32_t *)(addr))
#define pgm_read_float(addr)     (*(const float    *)(addr))
#define pgm_read_ptr(addr)       (*(void * const  *)(addr))

#define memcpy_P  memcpy
#define strcpy_P  strcpy
#define strncpy_P strncpy
#define strlen_P  strlen
#define strcmp_P  strcmp

#endif // NI404_COMPAT_PGMSPACE_H
