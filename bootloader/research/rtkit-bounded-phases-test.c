/* Host harness: complete RTKit implementation, mocked mailbox/time. */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
typedef unsigned long ulong;
#define BIT(n) (1ULL << (n))
#define GENMASK(h,l) ((~0ULL >> (63-(h))) & (~0ULL << (l)))
#define GENMASK_ULL(h,l) GENMASK(h,l)
#define FIELD_GET(mask,x) (((x)&(mask)) >> __builtin_ctzll(mask))
#define FIELD_PREP(mask,x) (((u64)(x) << __builtin_ctzll(mask)) & (mask))
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define min(a,b) ((a)<(b)?(a):(b))
#define SZ_16K 16384
#define ENOTSUPP 524
struct udevice;
struct mbox_chan {int unused;};
struct apple_mbox_msg { u64 msg0, msg1; };
static struct apple_mbox_msg queue[64];
static unsigned qlen, qpos, recv_count, send_count, starts;
static ulong clock_ms;
static int recv_error, send_error;
static ulong start_delay;
static ulong get_timer(ulong base) { return clock_ms-base; }
static int mbox_send(struct mbox_chan *c, struct apple_mbox_msg *m) {
 send_count++; if (((m->msg0 >> 52)&255)==5) { starts++; clock_ms += start_delay; }
 return send_error;
}
static int mbox_recv(struct mbox_chan *c, struct apple_mbox_msg *m, ulong timeout) {
 if (++recv_count>64) return -ECANCELED; /* host guard exposes old infinite loop */
 if (recv_error) return recv_error;
 clock_ms += min(timeout,1000000UL)/1000;
 if (qpos<qlen) *m=queue[qpos++]; else *m=(struct apple_mbox_msg){.msg0=0,.msg1=8};
 return 0;
}
// SPDX-License-Identifier: GPL-2.0+
/*
 * (C) Copyright 2021 Mark Kettenis <kettenis@openbsd.org>
 */

#define APPLE_RTKIT_PWR_STATE_SLEEP	0x01
#define APPLE_RTKIT_PWR_STATE_QUIESCED	0x10
#define APPLE_RTKIT_PWR_STATE_ON	0x20

struct apple_rtkit_buffer {
	void *buffer;
	u64 dva;
	size_t size;
	bool is_mapped;
	int endpoint;
};

typedef int (*apple_rtkit_shmem_setup)(void *cookie,
				       struct apple_rtkit_buffer *buf);
typedef void (*apple_rtkit_shmem_destroy)(void *cookie,
					  struct apple_rtkit_buffer *buf);

struct apple_rtkit;

struct apple_rtkit *apple_rtkit_init(struct mbox_chan *chan, void *cookie,
				     apple_rtkit_shmem_setup shmem_setup,
				     apple_rtkit_shmem_destroy shmem_destroy);
void apple_rtkit_free(struct apple_rtkit *rtk);
int apple_rtkit_boot(struct apple_rtkit *rtk);
int apple_rtkit_set_ap_power(struct apple_rtkit *rtk, int pwrstate);
int apple_rtkit_poll(struct apple_rtkit *rtk, ulong timeout);
int apple_rtkit_shutdown(struct apple_rtkit *rtk, int pwrstate);

int apple_rtkit_helper_poll(struct udevice *dev, ulong timeout);
// SPDX-License-Identifier: GPL-2.0+
/*
 * (C) Copyright 2021 Mark Kettenis <kettenis@openbsd.org>
 * (C) Copyright 2021 Copyright The Asahi Linux Contributors
 */



#define APPLE_RTKIT_EP_MGMT 0
#define APPLE_RTKIT_EP_CRASHLOG	1
#define APPLE_RTKIT_EP_SYSLOG 2
#define APPLE_RTKIT_EP_DEBUG 3
#define APPLE_RTKIT_EP_IOREPORT 4
#define APPLE_RTKIT_EP_OSLOG 8
#define APPLE_RTKIT_EP_TRACEKIT 10

/* Messages for management endpoint. */
#define APPLE_RTKIT_MGMT_TYPE GENMASK(59, 52)

#define APPLE_RTKIT_MGMT_PWR_STATE GENMASK(15, 0)

#define APPLE_RTKIT_MGMT_HELLO 1
#define APPLE_RTKIT_MGMT_HELLO_REPLY 2
#define APPLE_RTKIT_MGMT_HELLO_MINVER GENMASK(15, 0)
#define APPLE_RTKIT_MGMT_HELLO_MAXVER GENMASK(31, 16)

#define APPLE_RTKIT_MGMT_STARTEP 5
#define APPLE_RTKIT_MGMT_STARTEP_EP GENMASK(39, 32)
#define APPLE_RTKIT_MGMT_STARTEP_FLAG BIT(1)

#define APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE 6
#define APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE_ACK 7
#define APPLE_RTKIT_MGMT_SET_AP_PWR_STATE 11

#define APPLE_RTKIT_MGMT_EPMAP 8
#define APPLE_RTKIT_MGMT_EPMAP_LAST BIT(51)
#define APPLE_RTKIT_MGMT_EPMAP_BASE GENMASK(34, 32)
#define APPLE_RTKIT_MGMT_EPMAP_BITMAP GENMASK(31, 0)

#define APPLE_RTKIT_MGMT_EPMAP_REPLY 8
#define APPLE_RTKIT_MGMT_EPMAP_REPLY_MORE BIT(0)

#define APPLE_RTKIT_OSLOG_TYPE GENMASK_ULL(63, 56)
#define APPLE_RTKIT_OSLOG_BUFFER_REQUEST 1
#define APPLE_RTKIT_OSLOG_SIZE GENMASK_ULL(55, 36)
#define APPLE_RTKIT_OSLOG_IOVA GENMASK_ULL(35, 0)

#define APPLE_RTKIT_MIN_SUPPORTED_VERSION 11
#define APPLE_RTKIT_MAX_SUPPORTED_VERSION 12

/* Messages for internal endpoints. */
#define APPLE_RTKIT_BUFFER_REQUEST 1
#define APPLE_RTKIT_BUFFER_REQUEST_SIZE GENMASK(51, 44)
#define APPLE_RTKIT_BUFFER_REQUEST_IOVA GENMASK(41, 0)

#define TIMEOUT_1SEC_US 1000000
#define RTKIT_PHASE_TIMEOUT_MS 10000

struct apple_rtkit {
	struct mbox_chan *chan;
	void *cookie;
	apple_rtkit_shmem_setup shmem_setup;
	apple_rtkit_shmem_destroy shmem_destroy;

	struct apple_rtkit_buffer syslog_buffer;
	struct apple_rtkit_buffer crashlog_buffer;
	struct apple_rtkit_buffer ioreport_buffer;
	struct apple_rtkit_buffer oslog_buffer;

	int iop_pwr;
	int ap_pwr;
};

struct apple_rtkit *apple_rtkit_init(struct mbox_chan *chan, void *cookie,
				     apple_rtkit_shmem_setup shmem_setup,
				     apple_rtkit_shmem_destroy shmem_destroy)
{
	struct apple_rtkit *rtk;

	rtk = calloc(sizeof(*rtk), 1);
	if (!rtk)
		return NULL;

	rtk->chan = chan;
	rtk->cookie = cookie;
	rtk->shmem_setup = shmem_setup;
	rtk->shmem_destroy = shmem_destroy;

	return rtk;
}

void apple_rtkit_free(struct apple_rtkit *rtk)
{
	if (rtk->shmem_destroy) {
		if (rtk->syslog_buffer.buffer)
			rtk->shmem_destroy(rtk->cookie, &rtk->syslog_buffer);
		if (rtk->crashlog_buffer.buffer)
			rtk->shmem_destroy(rtk->cookie, &rtk->crashlog_buffer);
		if (rtk->ioreport_buffer.buffer)
			rtk->shmem_destroy(rtk->cookie, &rtk->ioreport_buffer);
		if (rtk->oslog_buffer.buffer)
			rtk->shmem_destroy(rtk->cookie, &rtk->oslog_buffer);
	} else {
		if (rtk->syslog_buffer.buffer)
			free(rtk->syslog_buffer.buffer);
		if (rtk->crashlog_buffer.buffer)
			free(rtk->crashlog_buffer.buffer);
		if (rtk->ioreport_buffer.buffer)
			free(rtk->ioreport_buffer.buffer);
		if (rtk->oslog_buffer.buffer)
			free(rtk->oslog_buffer.buffer);
	}
	free(rtk);
}

static int rtkit_handle_buf_req(struct apple_rtkit *rtk, int endpoint, struct apple_mbox_msg *msg)
{
	struct apple_rtkit_buffer *buf;
	int ret;

	switch (endpoint) {
	case APPLE_RTKIT_EP_CRASHLOG:
		buf = &rtk->crashlog_buffer;
		break;
	case APPLE_RTKIT_EP_SYSLOG:
		buf = &rtk->syslog_buffer;
		break;
	case APPLE_RTKIT_EP_IOREPORT:
		buf = &rtk->ioreport_buffer;
		break;
	case APPLE_RTKIT_EP_OSLOG:
		buf = &rtk->oslog_buffer;
		break;
	default:
		printf("%s: unexpected endpoint %d\n", __func__, endpoint);
		return -1;
	}

	switch (endpoint) {
	case APPLE_RTKIT_EP_OSLOG:
		buf->size = FIELD_GET(APPLE_RTKIT_OSLOG_SIZE, msg->msg0);
		buf->dva = FIELD_GET(APPLE_RTKIT_OSLOG_IOVA, msg->msg0) << 12;
		break;
	default:
		buf->size = FIELD_GET(APPLE_RTKIT_BUFFER_REQUEST_SIZE, msg->msg0) << 12;
		buf->dva = FIELD_GET(APPLE_RTKIT_BUFFER_REQUEST_IOVA, msg->msg0);
		break;
	}

	if (buf->size == 0) {
		printf("%s: unexpected request for buffer without size\n", __func__);
		return -1;
	}

	buf->is_mapped = !!buf->dva;
	buf->endpoint = endpoint;

	if (rtk->shmem_setup) {
		ret = rtk->shmem_setup(rtk->cookie, buf);
		if (ret < 0) {
			printf("%s: shmen_setup failed for endpoint %d\n", __func__,
			       endpoint);
			return ret;
		}
	} else if (!buf->is_mapped){
		buf->buffer = memalign(SZ_16K, ALIGN(buf->size, SZ_16K));
		if (!buf->buffer)
			return -ENOMEM;

		buf->dva = (u64)buf->buffer;
	}

	if (!buf->is_mapped) {
		/* oslog uses different fields */
		if (endpoint == APPLE_RTKIT_EP_OSLOG) {
			msg->msg0 = FIELD_PREP(APPLE_RTKIT_OSLOG_TYPE,
					       APPLE_RTKIT_OSLOG_BUFFER_REQUEST);
			msg->msg0 |= FIELD_PREP(APPLE_RTKIT_OSLOG_SIZE, buf->size);
			msg->msg0 |= FIELD_PREP(APPLE_RTKIT_OSLOG_IOVA, buf->dva >> 12);
		} else {
			msg->msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE,
					   APPLE_RTKIT_BUFFER_REQUEST);
			msg->msg0 |= FIELD_PREP(APPLE_RTKIT_BUFFER_REQUEST_SIZE, buf->size >> 12);
			msg->msg0 |= FIELD_PREP(APPLE_RTKIT_BUFFER_REQUEST_IOVA, buf->dva);
		}

		return mbox_send(rtk->chan, msg);
	}

	return 0;
}

int apple_rtkit_poll(struct apple_rtkit *rtk, ulong timeout)
{
	struct apple_mbox_msg msg;
	int ret;
	int endpoint;
	int msgtype;

	ret = mbox_recv(rtk->chan, &msg, timeout);
	if (ret < 0)
		return ret;

	endpoint = msg.msg1;
	msgtype = FIELD_GET(APPLE_RTKIT_MGMT_TYPE, msg.msg0);

	if (endpoint == APPLE_RTKIT_EP_CRASHLOG ||
		endpoint == APPLE_RTKIT_EP_SYSLOG ||
		endpoint == APPLE_RTKIT_EP_IOREPORT) {
		if (msgtype == APPLE_RTKIT_BUFFER_REQUEST) {
			ret = rtkit_handle_buf_req(rtk, endpoint, &msg);
			if (ret < 0)
				return ret;
			return 0;
		}
	}

	if (endpoint == APPLE_RTKIT_EP_OSLOG) {
		msgtype = FIELD_GET(APPLE_RTKIT_OSLOG_TYPE, msg.msg0);

		if (msgtype == APPLE_RTKIT_OSLOG_BUFFER_REQUEST) {
			ret = rtkit_handle_buf_req(rtk, endpoint, &msg);
			if (ret < 0)
				return ret;
			return 0;
		} else {
			/* Ignore */
			return 0;
		}
	}

	if (endpoint == APPLE_RTKIT_EP_IOREPORT) {
		// these two messages have to be ack-ed for proper startup
		if (msgtype == 0xc || msgtype == 0x8) {
			ret = mbox_send(rtk->chan, &msg);
			if (ret < 0)
				return ret;
			return 0;
		}
	}

	if (endpoint == APPLE_RTKIT_EP_SYSLOG) {
		/* Ignore init */
		if (msgtype == 0x8)
			return 0;

		/* Ack logs */
		if (msgtype == 0x5) {
			ret = mbox_send(rtk->chan, &msg);
			if (ret < 0)
				return ret;
			return 0;
		}
	}

	if (endpoint != APPLE_RTKIT_EP_MGMT) {
		printf("%s: unexpected endpoint %d\n", __func__, endpoint);
		return -EINVAL;
	}

	switch (msgtype) {
		case APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE_ACK:
			rtk->iop_pwr = FIELD_GET(APPLE_RTKIT_MGMT_PWR_STATE, msg.msg0);
			return 0;
		case APPLE_RTKIT_MGMT_SET_AP_PWR_STATE:
			rtk->ap_pwr = FIELD_GET(APPLE_RTKIT_MGMT_PWR_STATE, msg.msg0);
			return 0;
		default:
			printf("%s: unexpected message type %d\n", __func__, msgtype);

			/* Just ignore it */
			return 0;
	}
}

/* Bound the whole transition even if unrelated messages keep arriving. */
static int rtkit_wait_power(struct apple_rtkit *rtk, const int *state, int wanted)
{
	ulong start = get_timer(0);
	int ret;

	while (*state != wanted) {
		ulong elapsed = get_timer(start);
		ulong remaining;

		if (elapsed >= RTKIT_PHASE_TIMEOUT_MS)
			return -ETIMEDOUT;
		remaining = (RTKIT_PHASE_TIMEOUT_MS - elapsed) * 1000;
		ret = apple_rtkit_poll(rtk, min(remaining, (ulong)TIMEOUT_1SEC_US));
		if (ret < 0)
			return ret;
	}
	return 0;
}

int apple_rtkit_boot(struct apple_rtkit *rtk)
{
	struct apple_mbox_msg msg;
	int endpoints[256];
	int nendpoints = 0;
	bool seen_endpoints[256] = {};
	ulong map_start, elapsed, remaining;
	int endpoint;
	int min_ver, max_ver, want_ver;
	int msgtype;
	u64 reply;
	u32 bitmap, base;
	int i, ret;

	/* Wakup the IOP. */
	msg.msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE) |
		FIELD_PREP(APPLE_RTKIT_MGMT_PWR_STATE, APPLE_RTKIT_PWR_STATE_ON);
	msg.msg1 = APPLE_RTKIT_EP_MGMT;
	ret = mbox_send(rtk->chan, &msg);
	if (ret < 0)
		return ret;

	/* Wait for protocol version negotiation message. */
	ret = mbox_recv(rtk->chan, &msg, TIMEOUT_1SEC_US);
	if (ret < 0)
		return ret;

	endpoint = msg.msg1;
	msgtype = FIELD_GET(APPLE_RTKIT_MGMT_TYPE, msg.msg0);
	if (endpoint != APPLE_RTKIT_EP_MGMT) {
		printf("%s: unexpected endpoint %d\n", __func__, endpoint);
		return -EINVAL;
	}
	if (msgtype != APPLE_RTKIT_MGMT_HELLO) {
		printf("%s: unexpected message type %d\n", __func__, msgtype);
		return -EINVAL;
	}

	min_ver = FIELD_GET(APPLE_RTKIT_MGMT_HELLO_MINVER, msg.msg0);
	max_ver = FIELD_GET(APPLE_RTKIT_MGMT_HELLO_MAXVER, msg.msg0);
	want_ver = min(APPLE_RTKIT_MAX_SUPPORTED_VERSION, max_ver);

	if (min_ver > APPLE_RTKIT_MAX_SUPPORTED_VERSION) {
		printf("%s: firmware min version %d is too new\n",
		       __func__, min_ver);
		return -ENOTSUPP;
	}

	if (max_ver < APPLE_RTKIT_MIN_SUPPORTED_VERSION) {
		printf("%s: firmware max version %d is too old\n",
		       __func__, max_ver);
		return -ENOTSUPP;
	}

	/* Ack version. */
	msg.msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_HELLO_REPLY) |
		FIELD_PREP(APPLE_RTKIT_MGMT_HELLO_MINVER, want_ver) |
		FIELD_PREP(APPLE_RTKIT_MGMT_HELLO_MAXVER, want_ver);
	msg.msg1 = APPLE_RTKIT_EP_MGMT;
	ret = mbox_send(rtk->chan, &msg);
	if (ret < 0)
		return ret;

	map_start = get_timer(0);

wait_epmap:
	elapsed = get_timer(map_start);
	if (elapsed >= RTKIT_PHASE_TIMEOUT_MS)
		return -ETIMEDOUT;
	/* Wait only within the remaining phase budget. */
	remaining = (RTKIT_PHASE_TIMEOUT_MS - elapsed) * 1000;
	ret = mbox_recv(rtk->chan, &msg, min(remaining, (ulong)TIMEOUT_1SEC_US));
	if (ret < 0)
		return ret;

	endpoint = msg.msg1;
	msgtype = FIELD_GET(APPLE_RTKIT_MGMT_TYPE, msg.msg0);
	if (endpoint != APPLE_RTKIT_EP_MGMT) {
		printf("%s: unexpected endpoint %d\n", __func__, endpoint);
		return -EINVAL;
	}
	if (msgtype != APPLE_RTKIT_MGMT_EPMAP) {
		printf("%s: unexpected message type %d\n", __func__, msgtype);
		return -EINVAL;
	}

	bitmap = FIELD_GET(APPLE_RTKIT_MGMT_EPMAP_BITMAP, msg.msg0);
	base = FIELD_GET(APPLE_RTKIT_MGMT_EPMAP_BASE, msg.msg0);
	for (i = 0; i < 32; i++) {
		if ((bitmap & (1U << i)) && !seen_endpoints[base * 32 + i]) {
			if (nendpoints >= ARRAY_SIZE(endpoints))
				return -EOVERFLOW;
			seen_endpoints[base * 32 + i] = true;
			endpoints[nendpoints++] = base * 32 + i;
		}
	}

	/* Ack endpoint map. */
	reply = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_EPMAP_REPLY) |
		FIELD_PREP(APPLE_RTKIT_MGMT_EPMAP_BASE, base);
	if (msg.msg0 & APPLE_RTKIT_MGMT_EPMAP_LAST)
		reply |= APPLE_RTKIT_MGMT_EPMAP_LAST;
	else
		reply |= APPLE_RTKIT_MGMT_EPMAP_REPLY_MORE;
	msg.msg0 = reply;
	msg.msg1 = APPLE_RTKIT_EP_MGMT;
	ret = mbox_send(rtk->chan, &msg);
	if (ret < 0)
		return ret;

	if (reply & APPLE_RTKIT_MGMT_EPMAP_REPLY_MORE)
		goto wait_epmap;

	for (i = 0; i < nendpoints; i++) {
		if (get_timer(map_start) >= RTKIT_PHASE_TIMEOUT_MS)
			return -ETIMEDOUT;
		/* Start only necessary endpoints. The syslog endpoint is
		 * particularly noisy and its message can't easily be handled
		 * within U-Boot.
		 */
		switch (endpoints[i]) {
		case APPLE_RTKIT_EP_MGMT:
		case APPLE_RTKIT_EP_SYSLOG:
		case APPLE_RTKIT_EP_DEBUG:
		case APPLE_RTKIT_EP_TRACEKIT:
			continue;
		default:
			break;
		}

		/* Request endpoint. */
		msg.msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_STARTEP) |
			FIELD_PREP(APPLE_RTKIT_MGMT_STARTEP_EP, endpoints[i]) |
			APPLE_RTKIT_MGMT_STARTEP_FLAG;
		msg.msg1 = APPLE_RTKIT_EP_MGMT;
		ret = mbox_send(rtk->chan, &msg);
		if (ret < 0)
			return ret;
	}

	rtk->iop_pwr = APPLE_RTKIT_PWR_STATE_SLEEP;
	rtk->ap_pwr = APPLE_RTKIT_PWR_STATE_QUIESCED;

	return rtkit_wait_power(rtk, &rtk->iop_pwr, APPLE_RTKIT_PWR_STATE_ON);
}

int apple_rtkit_set_ap_power(struct apple_rtkit *rtk, int pwrstate)
{
	struct apple_mbox_msg msg;
	int ret;

	if (rtk->ap_pwr == pwrstate)
		return 0;

	msg.msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_SET_AP_PWR_STATE) |
		FIELD_PREP(APPLE_RTKIT_MGMT_PWR_STATE, pwrstate);
	msg.msg1 = APPLE_RTKIT_EP_MGMT;
	ret = mbox_send(rtk->chan, &msg);
	if (ret < 0)
		return ret;

	return rtkit_wait_power(rtk, &rtk->ap_pwr, pwrstate);
}

int apple_rtkit_shutdown(struct apple_rtkit *rtk, int pwrstate)
{
	struct apple_mbox_msg msg;
	int ret;

	if (rtk->ap_pwr != APPLE_RTKIT_PWR_STATE_QUIESCED) {
		ret = apple_rtkit_set_ap_power(rtk, APPLE_RTKIT_PWR_STATE_QUIESCED);
		if (ret < 0)
			return ret;
	}

	msg.msg0 = FIELD_PREP(APPLE_RTKIT_MGMT_TYPE, APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE) |
		FIELD_PREP(APPLE_RTKIT_MGMT_PWR_STATE, pwrstate);
	msg.msg1 = APPLE_RTKIT_EP_MGMT;
	ret = mbox_send(rtk->chan, &msg);
	if (ret < 0)
		return ret;

	return rtkit_wait_power(rtk, &rtk->iop_pwr, pwrstate);
}

static void reset_test(void) { memset(queue,0,sizeof(queue)); qlen=qpos=recv_count=send_count=starts=0;clock_ms=0;start_delay=0;recv_error=send_error=0; }
static void add(u64 v, u64 ep) {queue[qlen++]=(struct apple_mbox_msg){v,ep};}
static void hello(void) {add((1ULL<<52)|11|(12ULL<<16),0);}
static void map(unsigned base,u32 bitmap,bool last) {add((8ULL<<52)|((u64)base<<32)|bitmap|(last?(1ULL<<51):0),0);}
static void ack(int type,int state) {add(((u64)type<<52)|state,0);}
static int failures, cases;
static void result(const char *name,bool ok,int ret) {cases++;printf("%s: %s ret=%d receives=%u elapsed_ms=%lu\n",name,ok?"PASS":"FAIL",ret,recv_count,clock_ms);if(!ok)failures++;}
int main(void) {
 struct apple_rtkit r={0}; struct mbox_chan c={0}; int ret;
 r.chan=&c;
 reset_test(); hello();map(0,0,false);map(1,1,true);ack(7,32);ret=apple_rtkit_boot(&r);result("boot_ack",ret==0 && starts==1,ret);
 reset_test();hello();map(0,0,true);ret=apple_rtkit_boot(&r);result("boot_noise_deadline",ret==-ETIMEDOUT && recv_count==12 && clock_ms==12000,ret);
 reset_test();r.ap_pwr=16;ret=apple_rtkit_set_ap_power(&r,32);result("ap_noise_deadline",ret==-ETIMEDOUT && recv_count==10 && clock_ms==10000,ret);
 reset_test();r.ap_pwr=16;r.iop_pwr=32;ret=apple_rtkit_shutdown(&r,1);result("shutdown_noise_deadline",ret==-ETIMEDOUT && recv_count==10,ret);
 reset_test();hello();map(1,1,false);map(1,1,true);ack(7,32);ret=apple_rtkit_boot(&r);result("duplicate_map_deduplicated",ret==0 && starts==1,ret);
 reset_test();hello();for(int i=0;i<20;i++)map(1,0,false);ret=apple_rtkit_boot(&r);result("map_noise_deadline",ret==-ETIMEDOUT && clock_ms==11000,ret);
 reset_test();hello();for(int i=0;i<8;i++)map(i,0xffffffff,i==7);ack(7,32);ret=apple_rtkit_boot(&r);result("full_256_endpoint_map",ret==0 && starts==252,ret);
 reset_test();hello();map(1,0xffffffff,true);start_delay=2000;ret=apple_rtkit_boot(&r);result("endpoint_start_deadline",ret==-ETIMEDOUT && starts==5,ret);
 reset_test();recv_error=-EIO;r.ap_pwr=16;ret=apple_rtkit_set_ap_power(&r,32);result("receive_error_preserved",ret==-EIO && recv_count==1,ret);
 reset_test();send_error=-EIO;ret=apple_rtkit_set_ap_power(&r,32);result("send_error_preserved",ret==-EIO && recv_count==0,ret);
 reset_test();r.ap_pwr=16;ack(11,32);ret=apple_rtkit_set_ap_power(&r,32);result("ap_ack",ret==0 && r.ap_pwr==32,ret);
 reset_test();r.ap_pwr=32;r.iop_pwr=32;ack(11,16);ack(7,1);ret=apple_rtkit_shutdown(&r,1);result("shutdown_ack_order",ret==0 && r.ap_pwr==16 && r.iop_pwr==1 && send_count==2,ret);
 printf("cases=%d failures=%d\n",cases,failures);return !!failures;
}
