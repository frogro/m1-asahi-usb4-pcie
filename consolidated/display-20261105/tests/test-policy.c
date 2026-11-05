/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include "dcp-route-policy.h"

static struct apple_dp_command next(struct apple_dp_policy *p,
					  enum apple_dp_action action,
					  unsigned int route)
{
	struct apple_dp_command c;

	assert(apple_dp_policy_next(p, &c) == 1);
	assert(c.action == action && c.route == route);
	return c;
}

static void acquire(struct apple_dp_policy *p, unsigned int route)
{
	struct apple_dp_command c = next(p, APPLE_DP_ACQUIRE, route);

	assert(!apple_dp_policy_complete(p, &c, 0));
}

static void cases(void)
{
	struct apple_dp_policy p, saved;
	struct apple_dp_command c, stale, ignored;

	/* Existing dock wins, new native request cannot steal it. */
	apple_dp_policy_init(&p);
	assert(!apple_dp_policy_request(&p, 0, 1, true));
	acquire(&p, 0);
	assert(!apple_dp_policy_request(&p, 2, 1, true));
	assert(!apple_dp_policy_next(&p, &ignored));
	assert(!apple_dp_policy_request(&p, 0, 2, false));
	c = next(&p, APPLE_DP_RELEASE, 0);
	assert(apple_dp_policy_next(&p, &ignored) == -EINPROGRESS);
	assert(p.owner == 0);
	assert(!apple_dp_policy_complete(&p, &c, 0));
	acquire(&p, 2);
	assert(p.owner == 2);
	/* A late completion of the previous release cannot free the new owner. */
	saved = p;
	assert(apple_dp_policy_complete(&p, &c, 0) == -ESTALE);
	assert(!memcmp(&p, &saved, sizeof(p)));
	assert(apple_dp_policy_request(&p, 0, 1, true) == -ESTALE);

	/* Native on the other port first: dock must wait until native unplug. */
	apple_dp_policy_init(&p);
	assert(!apple_dp_policy_request(&p, 3, 1, true));
	acquire(&p, 3);
	assert(!apple_dp_policy_request(&p, 1, 1, true));
	assert(!apple_dp_policy_next(&p, &ignored));
	assert(!apple_dp_policy_request(&p, 3, 2, false));
	c = next(&p, APPLE_DP_RELEASE, 3);
	assert(!apple_dp_policy_complete(&p, &c, 0));
	acquire(&p, 1);

	/* Cable change while acquire is in flight requires a real withdrawal. */
	apple_dp_policy_init(&p);
	assert(!apple_dp_policy_request(&p, 2, 1, true));
	c = next(&p, APPLE_DP_ACQUIRE, 2);
	assert(!apple_dp_policy_request(&p, 2, 2, false));
	assert(!apple_dp_policy_request(&p, 2, 3, true));
	assert(!apple_dp_policy_complete(&p, &c, 0));
	c = next(&p, APPLE_DP_RELEASE, 2);
	assert(c.generation == 1);
	assert(!apple_dp_policy_complete(&p, &c, 0));
	c = next(&p, APPLE_DP_ACQUIRE, 2);
	assert(c.generation == 3);
	stale = c;
	stale.generation--;
	assert(apple_dp_policy_complete(&p, &stale, 0) == -ESTALE);
	stale = c;
	stale.route = 3;
	assert(apple_dp_policy_complete(&p, &stale, 0) == -ESTALE);
	assert(!apple_dp_policy_complete(&p, &c, 0));

	/* Every firmware failure is sticky, including failed withdrawal. */
	for (int release = 0; release < 2; release++) {
		apple_dp_policy_init(&p);
		assert(!apple_dp_policy_request(&p, 0, 1, true));
		c = next(&p, APPLE_DP_ACQUIRE, 0);
		if (release) {
			assert(!apple_dp_policy_complete(&p, &c, 0));
			assert(!apple_dp_policy_request(&p, 0, 2, false));
			c = next(&p, APPLE_DP_RELEASE, 0);
		}
		assert(apple_dp_policy_complete(&p, &c, -ETIMEDOUT) == -ETIMEDOUT);
		assert(!apple_dp_policy_request(&p, 1, 1, true));
		assert(apple_dp_policy_next(&p, &ignored) == -EUCLEAN);
		assert(apple_dp_policy_complete(&p, &c, 0) == -ESTALE);
		assert(p.phase == APPLE_DP_FAULT);
	}

	/* Stop during acquire still waits for completion, then withdraws once. */
	apple_dp_policy_init(&p);
	assert(!apple_dp_policy_request(&p, 3, 1, true));
	c = next(&p, APPLE_DP_ACQUIRE, 3);
	apple_dp_policy_stop(&p);
	assert(apple_dp_policy_request(&p, 0, 1, true) == -ESHUTDOWN);
	assert(apple_dp_policy_next(&p, &ignored) == -EINPROGRESS);
	assert(!apple_dp_policy_complete(&p, &c, 0));
	c = next(&p, APPLE_DP_RELEASE, 3);
	assert(!apple_dp_policy_complete(&p, &c, 0));
	assert(!apple_dp_policy_next(&p, &ignored));

	apple_dp_policy_init(&p);
	assert(apple_dp_policy_request(&p, APPLE_DP_ROUTES, 1, true) == -EINVAL);
	assert(apple_dp_policy_request(&p, 0, 0, true) == -EINVAL);
	p.sequence = ~(u64)0;
	assert(!apple_dp_policy_request(&p, 0, 1, true));
	assert(apple_dp_policy_next(&p, &ignored) == -EOVERFLOW);
	assert(p.phase == APPLE_DP_FAULT);
}

/* Deterministic scheduler: requests arrive during firmware transactions. */
static void interleavings(void)
{
	struct apple_dp_policy p;
	struct apple_dp_command pending = {0}, c;
	unsigned int rng = 0x81c9a7, pending_count = 0;
	u64 gen[APPLE_DP_ROUTES] = {0};
	int hardware_owner = APPLE_DP_NO_OWNER;

	apple_dp_policy_init(&p);
	for (unsigned int i = 0; i < 200000; i++) {
		rng = rng * 1664525u + 1013904223u;
		unsigned int route = (rng >> 16) % APPLE_DP_ROUTES;
		if ((rng >> 24) % 3 == 0) {
			assert(!apple_dp_policy_request(&p, route, ++gen[route],
							(rng >> 20) & 1));
		} else if (pending_count) {
			assert(apple_dp_policy_next(&p, &c) == -EINPROGRESS);
			if (pending.action == APPLE_DP_ACQUIRE) {
				assert(hardware_owner == APPLE_DP_NO_OWNER);
				hardware_owner = pending.route;
			} else {
				assert(hardware_owner == (int)pending.route);
				hardware_owner = APPLE_DP_NO_OWNER;
			}
			assert(!apple_dp_policy_complete(&p, &pending, 0));
			assert(p.owner == hardware_owner);
			pending_count = 0;
		} else {
			int ret = apple_dp_policy_next(&p, &pending);

			assert(ret >= 0);
			pending_count = ret;
		}
	}
}

int main(void)
{
	cases();
	interleavings();
	puts("PASS: ownership, port selection, stale generations, failures, stop; 200000 interleaved events");
	return 0;
}
