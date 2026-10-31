// SPDX-License-Identifier: GPL-2.0-only
/* Executes production PHY library and its TB-only tests, fake MMIO only. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32; typedef uint32_t __be32;
#define BIT(n) (1U<<(n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define be32_to_cpu(v) __builtin_bswap32(v)
#define cpu_to_be32(v) __builtin_bswap32(v)
struct unit_test_state {int unused;};
#define ut_assert(x) do {if (!(x)) {fprintf(stderr,"assertion failed line %d\n",__LINE__);return 1;}} while(0)
#define ut_asserteq(a,b) ut_assert((a)==(b))
#define ut_assertok(x) ut_asserteq(0,(x))
/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __APPLE_ATC_M1_H
#define __APPLE_ATC_M1_H

enum atc_m1_region { ATC_CORE, ATC_AXI, ATC_USB2, ATC_PIPE, ATC_DP, ATC_REGIONS };
enum atc_m1_mode { ATC_USB4, ATC_TBT };
enum atc_m1_stage { ATC_VALIDATE, ATC_ISOLATE, ATC_SLEEP_BIG, ATC_SLEEP_SMALL,
	ATC_WAKE_SMALL, ATC_WAKE_BIG, ATC_TUNABLES, ATC_LANES,
	ATC_PIPE_CLEAR, ATC_PIPE_LOCK, ATC_PIPE_MUX, ATC_PIPE_UNLOCK, ATC_DONE, ATC_PIPE_BOOTSTRAP, ATC_USB_RELEASE, ATC_USB_REISOLATE, ATC_CORE_READY };

struct atc_m1_tunable { const __be32 *data; size_t bytes; };

struct atc_m1_config {
	enum atc_m1_mode mode;
	bool swapped;
	/* Diagnostic ACIO owner retains halted DWC3 until full reset. */
	bool retain_dwc3;
	/* TB-only diagnostic: keep DWC3 reset asserted throughout ACIO start. */
	bool hold_dwc3_reset;
	/* common-a, axi2af, common-b, lane0-cio, lane1-cio */
	struct atc_m1_tunable tunable[5];
	size_t size[ATC_REGIONS];
};

struct atc_m1_io {
	int (*read)(void *ctx, enum atc_m1_region region, u32 offset, u32 *value);
	int (*write)(void *ctx, enum atc_m1_region region, u32 offset, u32 value);
	void (*delay)(void *ctx, unsigned int us);
	int (*verify_halted)(void *ctx);
};

int atc_m1_validate(const struct atc_m1_config *cfg);
/* Caller must stop and verify the selected DWC3 host and hold its power domains.
 * Failure stops immediately: hardware state is partial and requires reset.
 * Does not start ACIO, NHI, DMA or a PCIe tunnel; never an OS handover API.
 */
int atc_m1_start(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		 void *ctx, bool quiesced, enum atc_m1_stage *stage);
/* Split diagnostic entry points: core must succeed before PIPE can run.
 * A failed PIPE call consumes the state and must never be retried without reset.
 */
int atc_m1_start_core(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		 void *ctx, bool quiesced, enum atc_m1_stage *stage);
int atc_m1_start_pipe(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		 void *ctx, enum atc_m1_stage *stage);
#endif
// SPDX-License-Identifier: GPL-2.0-only
/* M1 USB4/TBT PHY sequence derived from drivers/phy/apple/atc.c.
 * Copyright (C) The Asahi Linux Contributors
 * Original author: Sven Peter <sven@kernel.org>
 * The Linux source is GPL-2.0 OR BSD-2-Clause; this port uses GPL-2.0.
 * Explicit diagnostic only. No device discovery, power ownership or DMA here.
 */

#define POWER_CTRL 0x20000
#define POWER_STAT 0x20004
#define MISC 0x20008
#define SMALL BIT(0)
#define BIG BIT(1)
#define CLAMP BIT(2)
#define APB_RESET_N BIT(3)
#define PHY_RESET_N BIT(4)
#define LANE_SWAP BIT(2)
#define PIPE_REQ 0x10
#define PIPE_ACK 0x14

int atc_m1_validate(const struct atc_m1_config *cfg)
{
	static const size_t minimum[] = { 0x4c000, 0x4000, 0x20, 0x24, 0x4004 };
	int i;
	size_t j, limit;

	if (!cfg || (cfg->mode != ATC_USB4 && cfg->mode != ATC_TBT))
		return -EINVAL;
	if (cfg->hold_dwc3_reset && cfg->mode != ATC_TBT)
		return -EINVAL;
	for (i = 0; i < ATC_REGIONS; i++)
		if (cfg->size[i] < minimum[i])
			return -ERANGE;
	for (i = 0; i < 5; i++) {
		const struct atc_m1_tunable *t = &cfg->tunable[i];

		if (!t->data || !t->bytes || t->bytes % 12 || t->bytes > 65532)
			return -EINVAL;
		limit = cfg->size[i == 1 ? ATC_AXI : ATC_CORE];
		for (j = 0; j < t->bytes / 4; j += 3) {
			u32 offset = be32_to_cpu(t->data[j]);

			if (offset % 4 || offset > limit - 4)
				return -ERANGE;
		}
	}
	return 0;
}

static int update(const struct atc_m1_io *io, void *ctx, enum atc_m1_region r,
		  u32 offset, u32 clear, u32 set)
{
	u32 value;
	int ret = io->read(ctx, r, offset, &value);

	if (ret)
		return ret;
	return io->write(ctx, r, offset, (value & ~clear) | set);
}

static int poll(const struct atc_m1_io *io, void *ctx, enum atc_m1_region r,
		u32 offset, u32 mask, u32 wanted, unsigned int timeout)
{
	unsigned int elapsed;
	u32 value;
	int ret;

	for (elapsed = 0; elapsed <= timeout; elapsed += 10) {
		ret = io->read(ctx, r, offset, &value);
		if (ret)
			return ret;
		if ((value & mask) == wanted)
			return 0;
		if (elapsed < timeout)
			io->delay(ctx, 10);
	}
	return -ETIMEDOUT;
}

/* Every operation returns before the next write if it fails. */
#define DO(op) do { ret = (op); if (ret) return ret; } while (0)
#define UP(r, off, clear, set) DO(update(io, ctx, r, off, clear, set))
#define DELAY() io->delay(ctx, 10)
#define POLL(r, off, mask, wanted, us) DO(poll(io, ctx, r, off, mask, wanted, us))

int atc_m1_start_core(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		 void *ctx, bool quiesced, enum atc_m1_stage *stage)
{
	int ret, i, group;
	size_t j;

	if (!stage)
		return -EINVAL;
	*stage = ATC_VALIDATE;
	DO(atc_m1_validate(cfg));
	if (!io || !io->read || !io->write || !io->delay || !io->verify_halted)
		return -EINVAL;
	if (!quiesced)
		return -EBUSY;

	*stage = ATC_ISOLATE;
	/* Isolate DWC3 while rebuilding the PHY. */
	UP(ATC_PIPE, 0x1c, BIT(0), 0);
	UP(ATC_PIPE, 0x1c, 0, BIT(4));
	/* Disable USB2 before cycling the shared PHY, as in Linux probe. */
	UP(ATC_USB2, 0, 7, 4); DELAY();
	UP(ATC_USB2, 4, 0, BIT(3)); DELAY();
	UP(ATC_USB2, 4, 0, BIT(1)); DELAY();
	UP(ATC_USB2, 4, 0, BIT(0)); DELAY();
	UP(ATC_USB2, 4, BIT(2), 0); DELAY();
	UP(ATC_USB2, 0x1c, 0, BIT(29));
	UP(ATC_USB2, 0x1c, 0, BIT(30));
	/* Disable DP AUX; neither DP altmode nor a display tunnel is requested. */
	UP(ATC_DP, 0x4000, 0, BIT(4));
	UP(ATC_DP, 0, 0, BIT(4));
	UP(ATC_DP, 0x4000, 0, BIT(2));
	UP(ATC_DP, 0x4000, BIT(0), 0); DELAY();
	UP(ATC_DP, 0x4000, BIT(1), 0); DELAY();
	UP(ATC_CORE, 0x7000, BIT(2), 0);
	UP(ATC_CORE, 0x7000, BIT(15), 0);
	UP(ATC_CORE, 0x7000, BIT(13), 0);
	UP(ATC_CORE, 0x7000, BIT(14), 0);
	UP(ATC_CORE, POWER_CTRL, PHY_RESET_N, 0);
	UP(ATC_CORE, POWER_CTRL, 0, CLAMP);
	UP(ATC_CORE, MISC, BIT(0) | LANE_SWAP, 0);
	UP(ATC_CORE, POWER_CTRL, APB_RESET_N, 0);
	*stage = ATC_SLEEP_BIG;
	UP(ATC_CORE, POWER_CTRL, BIG, 0);
	POLL(ATC_CORE, POWER_STAT, BIG, 0, 1000);
	*stage = ATC_SLEEP_SMALL;
	UP(ATC_CORE, POWER_CTRL, SMALL, 0);
	POLL(ATC_CORE, POWER_STAT, SMALL, 0, 1000);

	/* Linux probe_finalize establishes a clocked dummy mux while DWC3 and
	 * the PHY are reset. Do not retain an inherited, now stopped PHY clock.
	 */
	*stage = ATC_PIPE_BOOTSTRAP;
	UP(ATC_PIPE, 0xc, 0x38, 0); DELAY();
	UP(ATC_PIPE, 0xc, 7, 2); DELAY();
	UP(ATC_PIPE, 0xc, 0x38, 0x20); DELAY();

	/* Linux dwc3_apple_init()/atcphy_usb2_set_mode(): select host role
	 * while USB2 is still off, before releasing resets and enabling RUN.
	 * This diagnostic supports only host USB4/TBT operation.
	 */
	if (!cfg->hold_dwc3_reset)
		UP(ATC_USB2, 8, 0, 7 << 12);
	UP(ATC_USB2, 8, 0, 0xf); DELAY();
	UP(ATC_USB2, 4, BIT(3), 0); DELAY();
	UP(ATC_USB2, 4, BIT(0), 0); DELAY();
	UP(ATC_USB2, 4, BIT(1), 0); DELAY();
	UP(ATC_USB2, 4, 0, BIT(2)); DELAY();
	UP(ATC_USB2, 0x1c, BIT(29), 0);
	UP(ATC_USB2, 0x1c, BIT(30), 0);
	DO(io->write(ctx, ATC_USB2, 0, 2));
	UP(ATC_CORE, MISC, 0, BIT(0));
	*stage = ATC_WAKE_SMALL;
	UP(ATC_CORE, POWER_CTRL, 0, SMALL);
	POLL(ATC_CORE, POWER_STAT, SMALL, SMALL, 100000);
	*stage = ATC_WAKE_BIG;
	UP(ATC_CORE, POWER_CTRL, 0, BIG);
	POLL(ATC_CORE, POWER_STAT, BIG, BIG, 100000);
	UP(ATC_CORE, POWER_CTRL, CLAMP, 0);
	UP(ATC_CORE, POWER_CTRL, 0, APB_RESET_N);

	*stage = ATC_TUNABLES;
	for (i = 0; i < 5; i++) {
		const struct atc_m1_tunable *t;
		enum atc_m1_region r = i == 1 ? ATC_AXI : ATC_CORE;

		group = i;
		if (cfg->swapped && i >= 3)
			group = 7 - i;
		t = &cfg->tunable[group];
		/* Match Linux apple_tunable_apply(): redundant calibration writes
		 * are skipped. Explicit power/reset/control updates above and below
		 * deliberately retain their unconditional write semantics.
		 */
		for (j = 0; j < t->bytes / 4; j += 3) {
			u32 off = be32_to_cpu(t->data[j]), old, value;

			DO(io->read(ctx, r, off, &old));
			value = (old & ~be32_to_cpu(t->data[j + 1])) |
				be32_to_cpu(t->data[j + 2]);
			if (value != old)
				DO(io->write(ctx, r, off, value));
		}
	}
	/* M1 post-tunable sequence, preserving the Linux 10 us gaps. */
	UP(ATC_CORE, 0x1014, 0, 0x1fe000);
	UP(ATC_CORE, 0x2000, 0, BIT(28));
	UP(ATC_CORE, 8, 0, BIT(3)); DELAY();
	UP(ATC_CORE, 8, 0, BIT(1)); DELAY();
	UP(ATC_CORE, 8, 0, BIT(5)); DELAY();
	UP(ATC_CORE, 0x1b0, 0xc0, 0xc0); DELAY();
	UP(ATC_CORE, 0x1b0, 0x0c, 0x0c); DELAY();
	UP(ATC_CORE, 0x1b0, 0xc00, 0xc00); DELAY();
	UP(ATC_CORE, 8, 0x3000, 0x3000); DELAY();
	UP(ATC_CORE, 8, 0x300, 0x300); DELAY();
	UP(ATC_CORE, 8, 0x30000, 0x30000); DELAY();

	*stage = ATC_LANES;
	UP(ATC_CORE, 0x2a00, 0, BIT(1));
	UP(ATC_CORE, 0x2a00, 0, BIT(5));
	UP(ATC_CORE, 0x48, 7, 0);
	UP(ATC_CORE, 0x48, 0x38, 0);
	UP(ATC_CORE, 0x48, 0x1c0, 0);
	UP(ATC_CORE, 0x48, 0xe00, 0);
	UP(ATC_CORE, 0x4c, 0x1f, cfg->swapped ? 1 : 0);
	/* USB4/TBT intentionally never set the independent lane-swap bit. */
	UP(ATC_CORE, MISC, LANE_SWAP, 0);
	UP(ATC_CORE, 0x4c, 0x1ffe0, 0);
	UP(ATC_CORE, 0x4c, BIT(17), 0);
	UP(ATC_CORE, 0x9010, BIT(0), 0); DELAY();
	UP(ATC_CORE, 0x10010, BIT(0), 0); DELAY();
	UP(ATC_CORE, POWER_CTRL, 0, PHY_RESET_N);

	/* With no native USB role, Linux leaves DWC3 isolated while TB trains. */
	if (cfg->hold_dwc3_reset) {
		*stage = ATC_CORE_READY;
		return 0;
	}

	/* Linux deasserts DWC3 reset before its PHY set_mode/PIPE handshake.
	 * Do not start xHCI: verify it remains halted before proceeding.
	 */
	*stage = ATC_USB_RELEASE;
	UP(ATC_PIPE, 0x1c, BIT(4), 0);
	UP(ATC_PIPE, 0x1c, 0, BIT(0)); DELAY();
	DO(io->verify_halted(ctx));

	*stage = ATC_CORE_READY;
	return 0;
}

int atc_m1_start_pipe(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		    void *ctx, enum atc_m1_stage *stage)
{
	int ret;

	if (!stage || *stage != ATC_CORE_READY)
		return -EINVAL;
	DO(atc_m1_validate(cfg));
	if (cfg->hold_dwc3_reset)
		return -EPERM;
	if (!io || !io->read || !io->write || !io->delay || !io->verify_halted)
		return -EINVAL;

	/* A stale lock must be released before taking ownership. */
	*stage = ATC_PIPE_CLEAR;
	UP(ATC_PIPE, PIPE_REQ, BIT(0), 0);
	POLL(ATC_PIPE, PIPE_ACK, BIT(0), 0, 1000);
	UP(ATC_PIPE, 4, BIT(1) | BIT(2), 0);
	UP(ATC_PIPE, 0, 0, BIT(0));
	UP(ATC_PIPE, 0, 0, BIT(2));
	*stage = ATC_PIPE_LOCK;
	UP(ATC_PIPE, PIPE_REQ, 0, BIT(0));
	POLL(ATC_PIPE, PIPE_ACK, BIT(0), BIT(0), 1000);
	*stage = ATC_PIPE_MUX;
	UP(ATC_PIPE, 0xc, 0x38, 0); DELAY();
	UP(ATC_PIPE, 0xc, 7, cfg->mode == ATC_USB4 ? 1 : 2); DELAY();
	UP(ATC_PIPE, 0xc, 0x38, cfg->mode == ATC_USB4 ? 0x10 : 0x20); DELAY();
	if (cfg->mode == ATC_USB4) {
		UP(ATC_PIPE, 0, BIT(0), 0);
		UP(ATC_PIPE, 0, BIT(2), 0);
	}
	*stage = ATC_PIPE_UNLOCK;
	UP(ATC_PIPE, PIPE_REQ, BIT(0), 0);
	POLL(ATC_PIPE, PIPE_ACK, BIT(0), 0, 1000);
	if (cfg->mode == ATC_TBT) {
		UP(ATC_PIPE, 0x20, 0xf, 2);
		UP(ATC_PIPE, 0x20, 0, BIT(12));
	}
	if (!cfg->retain_dwc3) {
		*stage = ATC_USB_REISOLATE;
		UP(ATC_PIPE, 0x1c, BIT(0), 0);
		UP(ATC_PIPE, 0x1c, 0, BIT(4));
	}
	*stage = ATC_DONE;
	return 0;
}

/* Compatibility entry point for earlier staged diagnostics. */
int atc_m1_start(const struct atc_m1_config *cfg, const struct atc_m1_io *io,
		 void *ctx, bool quiesced, enum atc_m1_stage *stage)
{
	int ret = atc_m1_start_core(cfg, io, ctx, quiesced, stage);

	return ret ? ret : atc_m1_start_pipe(cfg, io, ctx, stage);
}
/* SPDX-License-Identifier: GPL-2.0-only */
/* Real m1n1-exported M1 port1 calibration from probe5, 2026-10-31. */
static const __be32 calibration_0[] = {
	cpu_to_be32(0x00002a38), cpu_to_be32(0x0000007f), cpu_to_be32(0x00000024),
	cpu_to_be32(0x00002a38), cpu_to_be32(0x00fe0000), cpu_to_be32(0x00540000),
	cpu_to_be32(0x00002aa4), cpu_to_be32(0x00060000), cpu_to_be32(0x00020000),
	cpu_to_be32(0x00000a04), cpu_to_be32(0x0000007c), cpu_to_be32(0x0000002c),
	cpu_to_be32(0x00002aa4), cpu_to_be32(0x00060000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00002a20), cpu_to_be32(0x0001c000), cpu_to_be32(0x00014000),
	cpu_to_be32(0x0000222c), cpu_to_be32(0x00000600), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0000222c), cpu_to_be32(0x00007000), cpu_to_be32(0x00004000),
	cpu_to_be32(0x000022a4), cpu_to_be32(0x00060000), cpu_to_be32(0x00040000),
	cpu_to_be32(0x00002220), cpu_to_be32(0x0001c000), cpu_to_be32(0x00008000),
	cpu_to_be32(0x00000a04), cpu_to_be32(0x0000007c), cpu_to_be32(0x0000002c),
};

static const __be32 calibration_1[] = {
	cpu_to_be32(0x00000000), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00000030), cpu_to_be32(0xffffffff), cpu_to_be32(0x0000ffff),
	cpu_to_be32(0x00000034), cpu_to_be32(0xffffffff), cpu_to_be32(0x0000ffff),
	cpu_to_be32(0x00000400), cpu_to_be32(0x400103ff), cpu_to_be32(0x40010001),
	cpu_to_be32(0x00000600), cpu_to_be32(0x01ffffff), cpu_to_be32(0x01ffffff),
	cpu_to_be32(0x00000738), cpu_to_be32(0x01ff01ff), cpu_to_be32(0x00400040),
	cpu_to_be32(0x00000798), cpu_to_be32(0x01ff01ff), cpu_to_be32(0x00600020),
	cpu_to_be32(0x00000800), cpu_to_be32(0x00000100), cpu_to_be32(0x00000100),
	cpu_to_be32(0x00000900), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00000920), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
};

static const __be32 calibration_2[] = {
	cpu_to_be32(0x00045004), cpu_to_be32(0x003f003f), cpu_to_be32(0x00200020),
	cpu_to_be32(0x0004500c), cpu_to_be32(0x000000f1), cpu_to_be32(0x000000a1),
	cpu_to_be32(0x00045010), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045018), cpu_to_be32(0x003f003f), cpu_to_be32(0x00200020),
	cpu_to_be32(0x00045020), cpu_to_be32(0x000000f1), cpu_to_be32(0x000000a1),
	cpu_to_be32(0x00045024), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004502c), cpu_to_be32(0x007f007f), cpu_to_be32(0x00520052),
	cpu_to_be32(0x00045034), cpu_to_be32(0x000000f1), cpu_to_be32(0x00000071),
	cpu_to_be32(0x00045038), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x0004503c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045040), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045048), cpu_to_be32(0x0000001f), cpu_to_be32(0x00000010),
	cpu_to_be32(0x00045050), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045058), cpu_to_be32(0x007f007f), cpu_to_be32(0x00450045),
	cpu_to_be32(0x00045060), cpu_to_be32(0x000000f1), cpu_to_be32(0x00000051),
	cpu_to_be32(0x00045064), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004506c), cpu_to_be32(0x0000003f), cpu_to_be32(0x00000020),
	cpu_to_be32(0x00045074), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004507c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045080), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045088), cpu_to_be32(0x001f001f), cpu_to_be32(0x00100010),
	cpu_to_be32(0x0004508c), cpu_to_be32(0x000000f1), cpu_to_be32(0x00000011),
	cpu_to_be32(0x00045090), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045094), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045098), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450a0), cpu_to_be32(0x00ff00ff), cpu_to_be32(0x00c000c0),
	cpu_to_be32(0x000450a4), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450ac), cpu_to_be32(0x0000003f), cpu_to_be32(0x00000020),
	cpu_to_be32(0x000450b4), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450bc), cpu_to_be32(0x0000003f), cpu_to_be32(0x00000020),
	cpu_to_be32(0x000450c4), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450cc), cpu_to_be32(0x001f001f), cpu_to_be32(0x00100010),
	cpu_to_be32(0x000450d4), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x000450d8), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x000450dc), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450e4), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x000450e8), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x000450ec), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x000450f4), cpu_to_be32(0xffffffff), cpu_to_be32(0x01010101),
	cpu_to_be32(0x000450f8), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000101),
	cpu_to_be32(0x000450fc), cpu_to_be32(0xffffffff), cpu_to_be32(0x01010101),
	cpu_to_be32(0x00045100), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000101),
	cpu_to_be32(0x00045104), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004510c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045110), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045114), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004511c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045120), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045124), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004512c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045130), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045134), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x0004513c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045140), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045148), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x0004514c), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045150), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045158), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045160), cpu_to_be32(0xffffffff), cpu_to_be32(0x01010101),
	cpu_to_be32(0x00045164), cpu_to_be32(0xffffffff), cpu_to_be32(0x01010101),
	cpu_to_be32(0x00045168), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000101),
	cpu_to_be32(0x0004516c), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045174), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045178), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x0004517c), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00045184), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00045188), cpu_to_be32(0x0000801f), cpu_to_be32(0x00000004),
	cpu_to_be32(0x00000118), cpu_to_be32(0xffffffff), cpu_to_be32(0x8446abe6),
	cpu_to_be32(0x0000011c), cpu_to_be32(0xffffffff), cpu_to_be32(0x18080887),
	cpu_to_be32(0x00000124), cpu_to_be32(0xffffffff), cpu_to_be32(0x0000640a),
	cpu_to_be32(0x00000118), cpu_to_be32(0xffffffff), cpu_to_be32(0x8446abe6),
	cpu_to_be32(0x0000011c), cpu_to_be32(0xffffffff), cpu_to_be32(0x18080887),
	cpu_to_be32(0x00000124), cpu_to_be32(0xffffffff), cpu_to_be32(0x0000640a),
	cpu_to_be32(0x00000a00), cpu_to_be32(0x0003fc00), cpu_to_be32(0x0003c000),
	cpu_to_be32(0x00000808), cpu_to_be32(0x0fff0ff0), cpu_to_be32(0x02220220),
	cpu_to_be32(0x0000222c), cpu_to_be32(0x00000900), cpu_to_be32(0x00000900),
	cpu_to_be32(0x00002278), cpu_to_be32(0x08000000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x000022a4), cpu_to_be32(0x00000001), cpu_to_be32(0x00000001),
	cpu_to_be32(0x00002088), cpu_to_be32(0x000f0000), cpu_to_be32(0x00060000),
	cpu_to_be32(0x00002094), cpu_to_be32(0x000f0000), cpu_to_be32(0x00060000),
	cpu_to_be32(0x000020a0), cpu_to_be32(0x000f0000), cpu_to_be32(0x00050000),
	cpu_to_be32(0x000020ac), cpu_to_be32(0x000f0000), cpu_to_be32(0x00050000),
	cpu_to_be32(0x000020b8), cpu_to_be32(0x000f0000), cpu_to_be32(0x00050000),
	cpu_to_be32(0x00002a00), cpu_to_be32(0x00000022), cpu_to_be32(0x00000022),
	cpu_to_be32(0x00002a1c), cpu_to_be32(0x00007000), cpu_to_be32(0x00002000),
	cpu_to_be32(0x00002a20), cpu_to_be32(0x00020007), cpu_to_be32(0x00020003),
	cpu_to_be32(0x00002a28), cpu_to_be32(0x00000010), cpu_to_be32(0x00000010),
	cpu_to_be32(0x00002a9c), cpu_to_be32(0x00020000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00002810), cpu_to_be32(0xffffffff), cpu_to_be32(0x0a0a0a04),
	cpu_to_be32(0x00002888), cpu_to_be32(0x000001ff), cpu_to_be32(0x00000127),
	cpu_to_be32(0x00002894), cpu_to_be32(0x000001ff), cpu_to_be32(0x00000115),
};

static const __be32 calibration_3[] = {
	cpu_to_be32(0x0000c008), cpu_to_be32(0x0000fc00), cpu_to_be32(0x00006c00),
	cpu_to_be32(0x0000c030), cpu_to_be32(0x00003fc0), cpu_to_be32(0x00002a00),
	cpu_to_be32(0x0000c080), cpu_to_be32(0x00f80000), cpu_to_be32(0x00180000),
	cpu_to_be32(0x0000c08c), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x0000c008), cpu_to_be32(0x0000fc00), cpu_to_be32(0x00006c00),
	cpu_to_be32(0x0000c030), cpu_to_be32(0x00003fc0), cpu_to_be32(0x00002a00),
	cpu_to_be32(0x0000c080), cpu_to_be32(0x00f80000), cpu_to_be32(0x00180000),
	cpu_to_be32(0x0000c08c), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00009000), cpu_to_be32(0x7e000000), cpu_to_be32(0x1e000000),
	cpu_to_be32(0x00009014), cpu_to_be32(0x00008000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0000902c), cpu_to_be32(0x4ff6ff3f), cpu_to_be32(0x4aa0ff3f),
	cpu_to_be32(0x00009030), cpu_to_be32(0x11fff00c), cpu_to_be32(0x11000004),
	cpu_to_be32(0x00009040), cpu_to_be32(0x00030000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00009068), cpu_to_be32(0x00000038), cpu_to_be32(0x00000018),
	cpu_to_be32(0x00009074), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003e),
	cpu_to_be32(0x00009084), cpu_to_be32(0x001fff0e), cpu_to_be32(0x0000400a),
	cpu_to_be32(0x00009088), cpu_to_be32(0x00003fff), cpu_to_be32(0x00001224),
	cpu_to_be32(0x000090ac), cpu_to_be32(0x001f8000), cpu_to_be32(0x00040000),
	cpu_to_be32(0x000090ec), cpu_to_be32(0xfffffffc), cpu_to_be32(0x00080000),
	cpu_to_be32(0x00009104), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000202),
	cpu_to_be32(0x00009108), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00009110), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00009118), cpu_to_be32(0x00000002), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00009000), cpu_to_be32(0x7e000000), cpu_to_be32(0x1e000000),
	cpu_to_be32(0x00009014), cpu_to_be32(0x00008000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0000902c), cpu_to_be32(0x4ff6ff3f), cpu_to_be32(0x4aa0ff3f),
	cpu_to_be32(0x00009030), cpu_to_be32(0x11fff00c), cpu_to_be32(0x11000004),
	cpu_to_be32(0x00009040), cpu_to_be32(0x00030000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00009068), cpu_to_be32(0x00000038), cpu_to_be32(0x00000018),
	cpu_to_be32(0x00009074), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003e),
	cpu_to_be32(0x00009084), cpu_to_be32(0x001fff0e), cpu_to_be32(0x0000400a),
	cpu_to_be32(0x00009088), cpu_to_be32(0x00003fff), cpu_to_be32(0x00001224),
	cpu_to_be32(0x000090ac), cpu_to_be32(0x001f8000), cpu_to_be32(0x00040000),
	cpu_to_be32(0x000090e4), cpu_to_be32(0x0fffffff), cpu_to_be32(0x01a50694),
	cpu_to_be32(0x000090ec), cpu_to_be32(0xfffffffc), cpu_to_be32(0x00080000),
	cpu_to_be32(0x00009104), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000202),
	cpu_to_be32(0x00009108), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00009110), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00009118), cpu_to_be32(0x00000002), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0000b01c), cpu_to_be32(0x07fc0fff), cpu_to_be32(0x01c00c21),
	cpu_to_be32(0x0000b024), cpu_to_be32(0x0000c000), cpu_to_be32(0x0000c000),
	cpu_to_be32(0x0000b028), cpu_to_be32(0x00000600), cpu_to_be32(0x00000600),
	cpu_to_be32(0x0000b02c), cpu_to_be32(0x00000070), cpu_to_be32(0x00000050),
	cpu_to_be32(0x0000b038), cpu_to_be32(0x1f800000), cpu_to_be32(0x13000000),
	cpu_to_be32(0x0000b03c), cpu_to_be32(0x07000000), cpu_to_be32(0x07000000),
	cpu_to_be32(0x0000b05c), cpu_to_be32(0x00000400), cpu_to_be32(0x00000400),
	cpu_to_be32(0x0000b084), cpu_to_be32(0x00007c1f), cpu_to_be32(0x00006011),
	cpu_to_be32(0x0000b08c), cpu_to_be32(0x001c0000), cpu_to_be32(0x00100000),
	cpu_to_be32(0x0000b01c), cpu_to_be32(0x07fc0fff), cpu_to_be32(0x01c00c21),
	cpu_to_be32(0x0000b024), cpu_to_be32(0x0000c000), cpu_to_be32(0x0000c000),
	cpu_to_be32(0x0000b028), cpu_to_be32(0x00000600), cpu_to_be32(0x00000600),
	cpu_to_be32(0x0000b02c), cpu_to_be32(0x00000070), cpu_to_be32(0x00000050),
	cpu_to_be32(0x0000b038), cpu_to_be32(0x1f800000), cpu_to_be32(0x13000000),
	cpu_to_be32(0x0000b03c), cpu_to_be32(0x07000000), cpu_to_be32(0x07000000),
	cpu_to_be32(0x0000b05c), cpu_to_be32(0x00000400), cpu_to_be32(0x00000400),
	cpu_to_be32(0x0000b084), cpu_to_be32(0x000f83e0), cpu_to_be32(0x000c0220),
	cpu_to_be32(0x0000b08c), cpu_to_be32(0x001c0000), cpu_to_be32(0x00100000),
	cpu_to_be32(0x0000a048), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0000a050), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0000a054), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0000a05c), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0000a07c), cpu_to_be32(0x00000fff), cpu_to_be32(0x000007ff),
	cpu_to_be32(0x0000a098), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003f),
	cpu_to_be32(0x0000a0bc), cpu_to_be32(0x7fc00000), cpu_to_be32(0x03000000),
	cpu_to_be32(0x0000a048), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0000a050), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0000a054), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0000a05c), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0000a07c), cpu_to_be32(0x00000fff), cpu_to_be32(0x000007ff),
	cpu_to_be32(0x0000a098), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003f),
	cpu_to_be32(0x0000a0bc), cpu_to_be32(0x7fc00000), cpu_to_be32(0x03000000),
};

static const __be32 calibration_4[] = {
	cpu_to_be32(0x00013008), cpu_to_be32(0x0000fc00), cpu_to_be32(0x00006c00),
	cpu_to_be32(0x00013030), cpu_to_be32(0x00003fc0), cpu_to_be32(0x00002a00),
	cpu_to_be32(0x00013080), cpu_to_be32(0x00f80000), cpu_to_be32(0x00180000),
	cpu_to_be32(0x0001308c), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00013008), cpu_to_be32(0x0000fc00), cpu_to_be32(0x00006c00),
	cpu_to_be32(0x00013030), cpu_to_be32(0x00003fc0), cpu_to_be32(0x00002a00),
	cpu_to_be32(0x00013080), cpu_to_be32(0x00f80000), cpu_to_be32(0x00180000),
	cpu_to_be32(0x0001308c), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00010000), cpu_to_be32(0x7e000000), cpu_to_be32(0x1e000000),
	cpu_to_be32(0x00010014), cpu_to_be32(0x00008000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0001002c), cpu_to_be32(0x4ff6ff3f), cpu_to_be32(0x4aa0ff3f),
	cpu_to_be32(0x00010030), cpu_to_be32(0x11fff00c), cpu_to_be32(0x11000004),
	cpu_to_be32(0x00010040), cpu_to_be32(0x00030000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00010068), cpu_to_be32(0x00000038), cpu_to_be32(0x00000018),
	cpu_to_be32(0x00010074), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003e),
	cpu_to_be32(0x00010084), cpu_to_be32(0x001fff0e), cpu_to_be32(0x0000400a),
	cpu_to_be32(0x00010088), cpu_to_be32(0x00003fff), cpu_to_be32(0x00001224),
	cpu_to_be32(0x000100ac), cpu_to_be32(0x001f8000), cpu_to_be32(0x00040000),
	cpu_to_be32(0x000100ec), cpu_to_be32(0xfffffffc), cpu_to_be32(0x00080000),
	cpu_to_be32(0x00010104), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000202),
	cpu_to_be32(0x00010108), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00010110), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00010118), cpu_to_be32(0x00000002), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00010000), cpu_to_be32(0x7e000000), cpu_to_be32(0x1e000000),
	cpu_to_be32(0x00010014), cpu_to_be32(0x00008000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0001002c), cpu_to_be32(0x4ff6ff3f), cpu_to_be32(0x4aa0ff3f),
	cpu_to_be32(0x00010030), cpu_to_be32(0x11fff00c), cpu_to_be32(0x11000004),
	cpu_to_be32(0x00010040), cpu_to_be32(0x00030000), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00010068), cpu_to_be32(0x00000038), cpu_to_be32(0x00000018),
	cpu_to_be32(0x00010074), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003e),
	cpu_to_be32(0x00010084), cpu_to_be32(0x001fff0e), cpu_to_be32(0x0000400a),
	cpu_to_be32(0x00010088), cpu_to_be32(0x00003fff), cpu_to_be32(0x00001224),
	cpu_to_be32(0x000100ac), cpu_to_be32(0x001f8000), cpu_to_be32(0x00040000),
	cpu_to_be32(0x000100e4), cpu_to_be32(0x0fffffff), cpu_to_be32(0x01a50694),
	cpu_to_be32(0x000100ec), cpu_to_be32(0xfffffffc), cpu_to_be32(0x00080000),
	cpu_to_be32(0x00010104), cpu_to_be32(0x0000ffff), cpu_to_be32(0x00000202),
	cpu_to_be32(0x00010108), cpu_to_be32(0x00000003), cpu_to_be32(0x00000000),
	cpu_to_be32(0x00010110), cpu_to_be32(0x0ffffff0), cpu_to_be32(0x02222220),
	cpu_to_be32(0x00010118), cpu_to_be32(0x00000002), cpu_to_be32(0x00000000),
	cpu_to_be32(0x0001201c), cpu_to_be32(0x07fc0fff), cpu_to_be32(0x01c00c21),
	cpu_to_be32(0x00012024), cpu_to_be32(0x0000c000), cpu_to_be32(0x0000c000),
	cpu_to_be32(0x00012028), cpu_to_be32(0x00000600), cpu_to_be32(0x00000600),
	cpu_to_be32(0x0001202c), cpu_to_be32(0x00000070), cpu_to_be32(0x00000050),
	cpu_to_be32(0x00012038), cpu_to_be32(0x1f800000), cpu_to_be32(0x13000000),
	cpu_to_be32(0x0001203c), cpu_to_be32(0x07000000), cpu_to_be32(0x07000000),
	cpu_to_be32(0x0001205c), cpu_to_be32(0x00000400), cpu_to_be32(0x00000400),
	cpu_to_be32(0x00012084), cpu_to_be32(0x00007c1f), cpu_to_be32(0x00006011),
	cpu_to_be32(0x0001208c), cpu_to_be32(0x001c0000), cpu_to_be32(0x00100000),
	cpu_to_be32(0x0001201c), cpu_to_be32(0x07fc0fff), cpu_to_be32(0x01c00c21),
	cpu_to_be32(0x00012024), cpu_to_be32(0x0000c000), cpu_to_be32(0x0000c000),
	cpu_to_be32(0x00012028), cpu_to_be32(0x00000600), cpu_to_be32(0x00000600),
	cpu_to_be32(0x0001202c), cpu_to_be32(0x00000070), cpu_to_be32(0x00000050),
	cpu_to_be32(0x00012038), cpu_to_be32(0x1f800000), cpu_to_be32(0x13000000),
	cpu_to_be32(0x0001203c), cpu_to_be32(0x07000000), cpu_to_be32(0x07000000),
	cpu_to_be32(0x0001205c), cpu_to_be32(0x00000400), cpu_to_be32(0x00000400),
	cpu_to_be32(0x00012084), cpu_to_be32(0x000f83e0), cpu_to_be32(0x000c0220),
	cpu_to_be32(0x0001208c), cpu_to_be32(0x001c0000), cpu_to_be32(0x00100000),
	cpu_to_be32(0x00011048), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x00011050), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x00011054), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0001105c), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0001107c), cpu_to_be32(0x00000fff), cpu_to_be32(0x000007ff),
	cpu_to_be32(0x00011098), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003f),
	cpu_to_be32(0x000110bc), cpu_to_be32(0x7fc00000), cpu_to_be32(0x03000000),
	cpu_to_be32(0x00011048), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x00011050), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x00011054), cpu_to_be32(0x0000000f), cpu_to_be32(0x00000002),
	cpu_to_be32(0x0001105c), cpu_to_be32(0x00000fff), cpu_to_be32(0x00000fff),
	cpu_to_be32(0x0001107c), cpu_to_be32(0x00000fff), cpu_to_be32(0x000007ff),
	cpu_to_be32(0x00011098), cpu_to_be32(0x0000003f), cpu_to_be32(0x0000003f),
	cpu_to_be32(0x000110bc), cpu_to_be32(0x7fc00000), cpu_to_be32(0x03000000),
};
// SPDX-License-Identifier: GPL-2.0-only

struct atc_trace { int region; u32 offset, value; };
struct atc_fake {
	u32 reg[ATC_REGIONS][0x4c000 / 4];
	struct atc_trace trace[1024];
	int calls, fault_call, writes, stall;
	unsigned int elapsed;
	enum atc_m1_stage stage;
};

static struct atc_fake fake;

static int fake_read(void *ctx, enum atc_m1_region r, u32 off, u32 *value)
{
	struct atc_fake *f = ctx;

	if (++f->calls == f->fault_call)
		return -EIO;
	if (r >= ATC_REGIONS || off >= 0x4c000 || off % 4)
		return -ERANGE;
	*value = f->reg[r][off / 4];
	if (r == ATC_CORE && off == 0x20004) {
		*value = f->reg[ATC_CORE][0x20000 / 4] & 3;
		if (f->stage == f->stall)
			*value ^= f->stage == ATC_WAKE_BIG ||
				  f->stage == ATC_SLEEP_BIG ? 2 : 1;
	}
	if (r == ATC_PIPE && off == 0x14) {
		*value = f->reg[ATC_PIPE][0x10 / 4] & 1;
		if (f->stage == f->stall)
			*value ^= 1;
	}
	return 0;
}

static int fake_write(void *ctx, enum atc_m1_region r, u32 off, u32 value)
{
	struct atc_fake *f = ctx;

	if (++f->calls == f->fault_call)
		return -EIO;
	if (r >= ATC_REGIONS || off >= 0x4c000 || off % 4 ||
	    f->writes >= ARRAY_SIZE(f->trace))
		return -ERANGE;
	f->reg[r][off / 4] = value;
	f->trace[f->writes++] = (struct atc_trace){ r, off, value };
	return 0;
}

static void fake_delay(void *ctx, unsigned int us)
{
	struct atc_fake *f = ctx;

	f->elapsed += us;
}

static int fake_verify_halted(void *ctx)
{
	struct atc_fake *f = ctx;

	if (++f->calls == f->fault_call)
		return -EIO;
	if (f->stall == ATC_USB_RELEASE ||
	    (f->reg[ATC_PIPE][0x1c / 4] & 0x11) != 1)
		return -EBUSY;
	return 0;
}

static const struct atc_m1_io fake_io = {
	.read = fake_read, .write = fake_write, .delay = fake_delay,
	.verify_halted = fake_verify_halted,
};

static struct atc_m1_config setup(void)
{
	struct atc_m1_config c = {
		.mode = ATC_USB4,
		.size = { 0x4c000, 0x4000, 0x4000, 0x4000, 0x8000 },
		.tunable = {
			{ calibration_0, sizeof(calibration_0) },
			{ calibration_1, sizeof(calibration_1) },
			{ calibration_2, sizeof(calibration_2) },
			{ calibration_3, sizeof(calibration_3) },
			{ calibration_4, sizeof(calibration_4) },
		},
	};

	memset(&fake, 0, sizeof(fake));
	memset(fake.reg, 0xa5, sizeof(fake.reg));
	fake.stall = -1;
	return c;
}

/* TB-only keeps the native USB controller isolated for the whole sequence. */
static int dm_test_atc_m1_tb_only(struct unit_test_state *uts)
{
 struct atc_m1_config c;
 u32 initial[] = { 0, 0xffffffff, 0xa5a5a5a5 };
 int swap, pattern, i, calls;
 for (swap = 0; swap < 2; swap++) {
  for (pattern = 0; pattern < ARRAY_SIZE(initial); pattern++) {
   c = setup(); c.mode = ATC_TBT; c.swapped = swap;
   c.hold_dwc3_reset = true;
   fake.reg[ATC_PIPE][0x1c / 4] = initial[pattern];
   fake.reg[ATC_USB2][8 / 4] = initial[pattern];
   ut_assertok(atc_m1_start_core(&c, &fake_io, &fake, true, &fake.stage));
   ut_asserteq(ATC_CORE_READY, fake.stage);
   ut_asserteq(0x10, fake.reg[ATC_PIPE][0x1c / 4] & 0x11);
   ut_asserteq(initial[pattern] & 0x7000, fake.reg[ATC_USB2][8 / 4] & 0x7000);
   ut_asserteq(0x1b, fake.reg[ATC_CORE][0x20000 / 4] & 0x1f);
   for (i = 0; i < fake.writes; i++) {
    struct atc_trace *w = &fake.trace[i];
    if (w->region != ATC_PIPE) continue;
    if (w->offset == 0x1c) ut_asserteq(0, w->value & 1);
    ut_assert(w->offset == 0x1c || w->offset == 0xc);
   }
   calls = fake.calls;
   ut_asserteq(-EPERM, atc_m1_start_pipe(&c, &fake_io, &fake, &fake.stage));
   ut_asserteq(calls, fake.calls);
  }
 }
 c = setup(); c.hold_dwc3_reset = true;
 ut_asserteq(-EINVAL, atc_m1_start_core(&c, &fake_io, &fake, true, &fake.stage));
 ut_asserteq(0, fake.calls);
 return 0;
}

static int dm_test_atc_m1_tb_only_faults(struct unit_test_state *uts)
{
 struct atc_m1_config c = setup();
 int calls, fault, i;
 c.mode = ATC_TBT; c.hold_dwc3_reset = true;
 ut_assertok(atc_m1_start_core(&c, &fake_io, &fake, true, &fake.stage));
 calls = fake.calls;
 for (fault = 1; fault <= calls; fault++) {
  c = setup(); c.mode = ATC_TBT; c.hold_dwc3_reset = true;
  fake.fault_call = fault;
  ut_asserteq(-EIO, atc_m1_start_core(&c, &fake_io, &fake, true, &fake.stage));
  ut_asserteq(fault, fake.calls);
  for (i = 0; i < fake.writes; i++)
   if (fake.trace[i].region == ATC_PIPE && fake.trace[i].offset == 0x1c)
    ut_asserteq(0, fake.trace[i].value & 1);
 }
 printf("TB-only fault injection: %d IO failure positions checked\n", calls);
 return 0;
}

int main(void) { struct unit_test_state u={0}; if(dm_test_atc_m1_tb_only(&u)||dm_test_atc_m1_tb_only_faults(&u))return 1; puts("TB-only sanitizer tests PASS"); return 0;}
