/* SPDX-License-Identifier: GPL-2.0 */
#ifndef __USB4_CFG_H
#define __USB4_CFG_H

#include <linux/types.h>

#define USB4_CFG_FRAME_BYTES 256
#define USB4_CFG_MAX_WORDS 60
#define USB4_CFG_READ 1
#define USB4_CFG_WRITE 2
#define USB4_CFG_ERROR 3
#define USB4_CFG_EVENT 5

struct usb4_cfg_event {
	u64 route;
	unsigned int port;
	bool unplug;
};

/* Values are deliberately wider than their wire fields for input validation. */
struct usb4_cfg_request {
	u64 route;
	u32 offset;
	unsigned int port, space, seq, words, type;
};

/*
 * Encode one read/write request, including the final CRC32C. The caller sets
 * both TX SOF and EOF to req->type. Return frame bytes, or a negative errno.
 * All input validation completes before frame is changed.
 */
int usb4_cfg_encode(const struct usb4_cfg_request *req, const u32 *data,
		    void *frame, size_t capacity);

/*
 * Decode a normal read/write response from the NHI RX ring. Size includes CRC.
 * RX SOF must be zero; EOF identifies the response. A different response type,
 * route or sequence returns -EAGAIN for the caller to dispatch or discard.
 * In particular, events/error packets need separate handling by the transport.
 * Response port is the responder's upstream port, not necessarily req->port.
 * Data and response_port change only after every check succeeds.
 */
int usb4_cfg_decode(const struct usb4_cfg_request *req, const void *frame,
		    size_t size, unsigned int sof, unsigned int eof,
		    u32 *data, unsigned int *response_port);

/* Validated plug events only. Output is unchanged on failure. */
int usb4_cfg_decode_event(const void *frame, size_t size, unsigned int sof,
                         unsigned int eof, struct usb4_cfg_event *event);
/* Linux tb_cfg_ack_plug wire format; no reply is expected. TX SOF/EOF are 3. */
int usb4_cfg_ack_plug_encode(const struct usb4_cfg_event *event,
                            void *frame, size_t capacity);

struct usb4_cfg_error {
 u64 route;
 unsigned int port, code, pg;
};
/* Output is unchanged on malformed framing/CRC/reserved fields. */
int usb4_cfg_decode_error(const void *, size_t, unsigned int, unsigned int,
                         struct usb4_cfg_error *);
/* -EAGAIN denotes a valid asynchronous notification, not success. */
int usb4_cfg_error_result(const struct usb4_cfg_request *, const struct usb4_cfg_error *);
#endif
