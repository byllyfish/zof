.. _scalar:

Scalar Types
============




DatapathID
----------

64-bit value uniquely identifying a datapath.

Canonical Type: String

Canonical Form: "hh:hh:hh:hh:hh:hh:hh:hh"

Acceptable Forms:
    "0x0102" -> "00:00:00:00:00:00:01:02"  (String must begin with "0x")

Reference:  `Datapath ID`  (OF_v1.5.1: Section 7.3.1)


VlanNumber
----------

14-bit vlan vid.

0 means no VLAN tag is present.
1-4095 specifies a VLAN tag value.
4096 specifies VLAN tag value of 0.

For compatibility with the OpenFlow spec, 4096-8191 also specify VLAN tags 0-4095.

Negative integers represent a non-zero vlan_vid which does not have the OFPVID_PRESENT bit set.

Canonical Type: Integer

Canonical Form: SInt32


Mixed Types
===========

A mixed type may be either an JSON integer or string. Strings are used for reserved constants in the canonical form.


PortNumber
----------

32-bit port number.

Canonical Type:  Integer or String

Canonical Form:  UInt32 | "IN_PORT" | "TABLE" | "NORMAL" | "FLOOD" | "ALL" | "CONTROLLER" | "LOCAL" | "ANY" | "NONE"

