// SPDX-License-Identifier: GPL-2.0+
/*
 * RTKit buffer-request function from U-Boot b33034a515a0:
 * (C) Copyright 2021 Mark Kettenis <kettenis@openbsd.org>
 * (C) Copyright 2021 The Asahi Linux Contributors
 * Host-only reproducer: mailbox and allocation callback are mocked.
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <malloc.h>
#include <errno.h>
typedef uint64_t u64;
#define BIT(n) (1ULL << (n))
#define GENMASK(h,l) ((~0ULL >> (63-(h))) & (~0ULL << (l)))
#define GENMASK_ULL(h,l) GENMASK(h,l)
#define FIELD_GET(mask,x) (((x)&(mask)) >> __builtin_ctzll(mask))
#define FIELD_PREP(mask,x) (((u64)(x) << __builtin_ctzll(mask)) & (mask))
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
#define SZ_16K 16384
struct apple_mbox_msg { u64 msg0, msg1; };
struct apple_rtkit_buffer { void *buffer; u64 dva; size_t size; bool is_mapped; int endpoint; };
struct apple_rtkit { void *cookie, *chan; int (*shmem_setup)(void*,struct apple_rtkit_buffer*); struct apple_rtkit_buffer syslog_buffer,crashlog_buffer,ioreport_buffer,oslog_buffer; };
static int mbox_send(void *chan,struct apple_mbox_msg *msg) { return 0; }
static struct apple_rtkit_buffer observed;
static int record(void *ctx,struct apple_rtkit_buffer *b) { observed=*b;if (!b->dva) b->dva=0x123456000ULL;return 0; }
#define APPLE_RTKIT_EP_MGMT 0
#define APPLE_RTKIT_EP_CRASHLOG	1
#define APPLE_RTKIT_EP_SYSLOG 2
#define APPLE_RTKIT_EP_DEBUG 3
#define APPLE_RTKIT_EP_IOREPORT 4
#define APPLE_RTKIT_EP_OSLOG 8
#define APPLE_RTKIT_EP_TRACEKIT 10
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
#define APPLE_RTKIT_BUFFER_REQUEST 1
#define APPLE_RTKIT_BUFFER_REQUEST_SIZE GENMASK(51, 44)
#define APPLE_RTKIT_BUFFER_REQUEST_IOVA GENMASK(41, 0)
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
		buf->dva = FIELD_GET(APPLE_RTKIT_OSLOG_IOVA, msg->msg0 << 12);
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

	buf->dva = FIELD_GET(APPLE_RTKIT_BUFFER_REQUEST_IOVA, msg->msg0);
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

int main(void) {
 const u64 addresses[]={0x123456000ULL,0xabcdef000000ULL,0x1000ULL,0xfffffff000ULL};
 int fail=0;
 for (unsigned int i=0;i<4;i++) {
  struct apple_rtkit r={.shmem_setup=record};
  struct apple_mbox_msg msg={.msg0=FIELD_PREP(APPLE_RTKIT_OSLOG_TYPE,1)|FIELD_PREP(APPLE_RTKIT_OSLOG_SIZE,0x1000)|FIELD_PREP(APPLE_RTKIT_OSLOG_IOVA,addresses[i]>>12)};
  int ret=rtkit_handle_buf_req(&r,APPLE_RTKIT_EP_OSLOG,&msg);
  int bad=ret || observed.dva!=addresses[i] || observed.size!=4096 || !observed.is_mapped;
  printf("OSLOG mapped %u expected=%llx actual=%llx %s\n",i,(unsigned long long)addresses[i],(unsigned long long)observed.dva,bad?"FAIL":"PASS");fail+=bad;
 }
 for (unsigned int oslog=0;oslog<2;oslog++) {
  struct apple_rtkit r={.shmem_setup=record};
  struct apple_mbox_msg msg={.msg0=oslog?FIELD_PREP(APPLE_RTKIT_OSLOG_TYPE,1)|FIELD_PREP(APPLE_RTKIT_OSLOG_SIZE,8192):FIELD_PREP(APPLE_RTKIT_MGMT_TYPE,1)|FIELD_PREP(APPLE_RTKIT_BUFFER_REQUEST_SIZE,2)};
  int ret=rtkit_handle_buf_req(&r,oslog?APPLE_RTKIT_EP_OSLOG:APPLE_RTKIT_EP_SYSLOG,&msg);
  u64 reply=oslog?FIELD_GET(APPLE_RTKIT_OSLOG_IOVA,msg.msg0)<<12:FIELD_GET(APPLE_RTKIT_BUFFER_REQUEST_IOVA,msg.msg0);
  int bad=ret || observed.is_mapped || observed.size!=8192 || reply!=0x123456000ULL;
  printf("host allocation oslog=%u %s\n",oslog,bad?"FAIL":"PASS");fail+=bad;
 }
 {
  struct apple_rtkit r={.shmem_setup=record};
  struct apple_mbox_msg msg={.msg0=FIELD_PREP(APPLE_RTKIT_MGMT_TYPE,1)|FIELD_PREP(APPLE_RTKIT_BUFFER_REQUEST_SIZE,2)|0x1234000ULL};
  int ret=rtkit_handle_buf_req(&r,APPLE_RTKIT_EP_SYSLOG,&msg);
  int bad=ret || observed.dva!=0x1234000 || observed.size!=8192 || !observed.is_mapped;
  printf("normal mapped %s\n",bad?"FAIL":"PASS");fail+=bad;
 }
 {
  struct apple_rtkit r={.shmem_setup=record};
  struct apple_mbox_msg msg={.msg0=FIELD_PREP(APPLE_RTKIT_OSLOG_TYPE,1)|0x1234};
  int ret=rtkit_handle_buf_req(&r,APPLE_RTKIT_EP_OSLOG,&msg);
  int bad=ret>=0;printf("zero size %s\n",bad?"FAIL":"PASS");fail+=bad;
 }
 printf("8 cases, failures=%d\n",fail);return fail?1:0;
}
