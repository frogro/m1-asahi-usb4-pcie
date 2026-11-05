/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef APPLE_DCP_ROUTE_POLICY_H
#define APPLE_DCP_ROUTE_POLICY_H

#include <linux/errno.h>
#include <linux/types.h>

/*
 * Experimental arbitration core for the opt-in DCP route manager.
 *
 * One caller-owned mutex protects every operation. The caller drops that
 * mutex for firmware calls and passes the exact command back to complete().
 * Neither a new cable event nor a stale completion can retire a newer owner.
 * Route indices are supplied by topology, not hardware product identifiers.
 * At idle, the lowest requested index wins; an active owner is not preempted.
 */
#define APPLE_DP_ROUTES 4
#define APPLE_DP_NO_OWNER (-1)

enum apple_dp_phase {
	APPLE_DP_IDLE,
	APPLE_DP_ACQUIRING,
	APPLE_DP_ACTIVE,
	APPLE_DP_RELEASING,
	APPLE_DP_FAULT,
};

enum apple_dp_action {
	APPLE_DP_ACQUIRE,
	APPLE_DP_RELEASE,
};

struct apple_dp_request {
	u64 generation;
	bool present;
};

struct apple_dp_command {
	u64 cookie;
	u64 generation;
	unsigned int route;
	enum apple_dp_action action;
};

struct apple_dp_policy {
	struct apple_dp_request request[APPLE_DP_ROUTES];
	struct apple_dp_command pending;
	u64 sequence;
	u64 owner_generation;
	int owner;
	enum apple_dp_phase phase;
	bool stopping;
};

static inline void apple_dp_policy_init(struct apple_dp_policy *p)
{
	*p = (struct apple_dp_policy) { .owner = APPLE_DP_NO_OWNER };
}

/* Generations advance on level/route transitions, not on HPD IRQ pulses. */
static inline int apple_dp_policy_request(struct apple_dp_policy *p,
					  unsigned int route, u64 generation,
					  bool present)
{
	if (route >= APPLE_DP_ROUTES || !generation)
		return -EINVAL;
	if (generation <= p->request[route].generation)
		return -ESTALE;
	if (p->stopping && present)
		return -ESHUTDOWN;
	p->request[route].generation = generation;
	p->request[route].present = present;
	return 0;
}

static inline void apple_dp_policy_stop(struct apple_dp_policy *p)
{
	p->stopping = true;
}

/* Return 1 for a command, 0 for idle/unchanged, or a negative status. */
static inline int apple_dp_policy_next(struct apple_dp_policy *p,
				       struct apple_dp_command *cmd)
{
	unsigned int route;

	if (p->phase == APPLE_DP_FAULT)
		return -EUCLEAN;
	if (p->phase == APPLE_DP_ACQUIRING || p->phase == APPLE_DP_RELEASING)
		return -EINPROGRESS;
	if (p->phase == APPLE_DP_ACTIVE) {
		route = p->owner;
		if (!p->stopping && p->request[route].present &&
		    p->request[route].generation == p->owner_generation)
			return 0;
		p->pending.action = APPLE_DP_RELEASE;
		p->pending.generation = p->owner_generation;
	} else {
		if (p->stopping)
			return 0;
		for (route = 0; route < APPLE_DP_ROUTES; route++) {
			if (p->request[route].present)
				break;
		}
		if (route == APPLE_DP_ROUTES)
			return 0;
		p->pending.action = APPLE_DP_ACQUIRE;
		p->pending.generation = p->request[route].generation;
	}
	if (p->sequence == ~(u64)0) {
		p->phase = APPLE_DP_FAULT;
		return -EOVERFLOW;
	}
	p->pending.cookie = ++p->sequence;
	p->pending.route = route;
	p->phase = p->pending.action == APPLE_DP_ACQUIRE ?
		   APPLE_DP_ACQUIRING : APPLE_DP_RELEASING;
	*cmd = p->pending;
	return 1;
}

/*
 * Release success means firmware withdrawal AND provider token retirement
 * AND crossbar release have all been acknowledged. Do not translate an
 * expired token, a timeout or an unacknowledged command to success here.
 * Any failed transaction quarantines the shared controller until teardown.
 */
static inline int apple_dp_policy_complete(struct apple_dp_policy *p,
					   const struct apple_dp_command *cmd,
					   int result)
{
	if ((p->phase != APPLE_DP_ACQUIRING && p->phase != APPLE_DP_RELEASING) ||
	    cmd->cookie != p->pending.cookie ||
	    cmd->route != p->pending.route ||
	    cmd->generation != p->pending.generation ||
	    cmd->action != p->pending.action)
		return -ESTALE;
	if (result) {
		p->phase = APPLE_DP_FAULT;
		return result;
	}
	if (cmd->action == APPLE_DP_ACQUIRE) {
		p->owner = cmd->route;
		p->owner_generation = cmd->generation;
		p->phase = APPLE_DP_ACTIVE;
	} else {
		p->owner = APPLE_DP_NO_OWNER;
		p->owner_generation = 0;
		p->phase = APPLE_DP_IDLE;
	}
	return 0;
}

#endif
