# Probe20 interpretation plan

This run changes observation only. It retains Probe19 host activation, port
unlock, cable information, one-second link observation and full-reset exit.

Linux reference: drivers/thunderbolt/ctl.c:tb_ctl_rx_callback and tb_async_error;
tb.c:tb_handle_event; tb_msgs.h:cfg_event_pkg and cfg_error_pkg;
include/linux/thunderbolt.h:tb_cfg_pkg_type.

- EOF 5 is a plug/unplug event; third word low 6 bits port, bit31 unplug.
  Linux acknowledges with EOF3/error7 and PG hotplug/unplug, then queues scan.
- EOF3 is an error/notification; third word low8 error, bits8..13 port,
  top2 PG. It must not be mistaken for a plug event or blindly acknowledged.
- Raw words are logged only after framing/size/CRC validation. Other unmatched
  responses can also appear here; logs do not label them as physical events.
- Both PHY capabilities are independently discovered. State7 is UNPLUGGED;
  state1 CONNECTING; 2..6 are link-up states in Linux.
- M3 mailbox status uses known M3 offsets0x50/0x80 and EMPTY bit17. No FIFO pop
  occurs. A nonempty FIFO alone does not prove firmware is blocked; it identifies
  the need for a bounded mailbox-service comparison.
- PHY snapshots read only already powered, known control/status registers.
  They allow comparison of mux, lane mode and reset across ACIO startup.

No speculative acknowledgment, firmware polling, reset or tunnel write is added.
No external SSD access or installed bootloader changes. Passed hardware stages
are traversed only because they are prerequisites for the new observations.
