from pathlib import Path
import sys
import subprocess as sp
p=Path(__file__).parent;(Path(sys.argv[2])/'events-tests').mkdir(parents=True,exist_ok=True);t=(Path(sys.argv[1])/'cmd/apple_nhi_m1_ring.c').read_text();f=t[t.index('static bool diagnostic_event_allowed('):t.index('static int diagnostic_ack_events')]
c='''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
typedef uint64_t u64;
#define APPLE_NHI_ROUTER_MAX_PORT 63U
struct diagnostic_ring{unsigned remote_max_port;u64 child_route;unsigned child_max_port;};
'''+f+r'''
int main(void){unsigned cases=0;struct diagnostic_ring r={19,0,0};for(unsigned p=0;p<=64;p++){assert(diagnostic_ring_event_allowed(&r,0,p)==(p>0&&p<=7));assert(diagnostic_ring_event_allowed(&r,1,p)==(p>0&&p<=19));assert(!diagnostic_ring_event_allowed(&r,0x301,p));cases+=3;}
for(unsigned lane=1;lane<=63;lane++)for(unsigned max=1;max<=63;max++){r.child_route=1ULL|((u64)lane<<8);r.child_max_port=max;for(unsigned p=0;p<=64;p++){assert(diagnostic_ring_event_allowed(&r,r.child_route,p)==(p>0&&p<=max));assert(!diagnostic_ring_event_allowed(&r,r.child_route+0x10000,p));cases+=2;}}
r.child_route=0x301;r.child_max_port=64;assert(!diagnostic_ring_event_allowed(&r,0x301,1));cases++;printf("PASS %u bounded event-source cases\n",cases);}
'''
(Path(sys.argv[2])/'events-tests/events.c').write_text(c);sp.run(['cc','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',str(Path(sys.argv[2])/'events-tests/events.c'),'-o',str(Path(sys.argv[2])/'events-tests/events-test')],check=True);r=sp.run([str(Path(sys.argv[2])/'events-tests/events-test')],capture_output=True,text=True);(Path(sys.argv[2])/'events-tests/events.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);r.check_returncode()
