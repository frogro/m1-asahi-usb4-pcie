#include <stdint.h>
static inline uint32_t get_unaligned_be32(const void*p){const uint8_t*b=p;return (uint32_t)b[0]<<24|(uint32_t)b[1]<<16|(uint32_t)b[2]<<8|b[3];}
static inline void put_unaligned_be32(uint32_t x,void*p){uint8_t*b=p;b[0]=x>>24;b[1]=x>>16;b[2]=x>>8;b[3]=x;}
