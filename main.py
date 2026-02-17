#!/usr/bin/env python3
"""
can_sim.py - Simple CAN simulation/replay/inject tool using python-can + SocketCAN.

Usage:
  # Replay recorded CSV keeping timestamps (wallclock)
  python3 can_sim.py --iface vcan0 --replay log.csv --log-out out.csv

  # Replay but scale byte 2 (speed) by factor 2
  python3 can_sim.py --iface vcan0 --replay log.csv --modify "id:0x110:byte:2:scale:0.5" --log-out out.csv

  # Generate single ID repeatedly
  python3 can_sim.py --iface vcan0 --gen "id:0x110:d1:00:d2:3C:freq:10" --log-out out.csv
"""
import can
import argparse
import csv
import time
import sys
import threading

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--iface', required=True, help='SocketCAN interface, e.g., can0 or vcan0')
    p.add_argument('--replay', help='CSV replay input')
    p.add_argument('--gen', help='Generate mode (one-shot generator spec)')
    p.add_argument('--log-out', help='CSV log output file to write observed frames')
    p.add_argument('--modify', help='Modify rule: "id:0x110:byte:2:scale:0.5" (single rule)')
    return p.parse_args()

def open_bus(iface):
    bus = can.interface.Bus(channel=iface, bustype='socketcan')
    return bus

def parse_csv_row(row):
    # row: timestamp,id_hex,is_ext,dlc,data_hex
    ts = float(row[0])
    ident = int(row[1], 16)
    is_ext = bool(int(row[2]))
    dlc = int(row[3])
    data_hex = row[4].strip()
    data = bytes.fromhex(data_hex)
    return ts, ident, is_ext, dlc, data

def read_replay_csv(path):
    rows = []
    with open(path, newline='') as fh:
        rdr = csv.reader(fh)
        for r in rdr:
            if not r or r[0].startswith('#'): continue
            rows.append(parse_csv_row(r))
    return rows

def apply_modify_rule(msg, rule):
    # Rule syntax: id:0x110:byte:2:scale:0.5
    parts = rule.split(':')
    try:
        _, idstr, _, byteidx, _, scale = parts
        idval = int(idstr, 16)
        byteidx = int(byteidx)
        scale = float(scale)
    except Exception:
        return msg
    if msg.arbitration_id != idval:
        return msg
    b = bytearray(msg.data)
    if byteidx < len(b):
        original = b[byteidx]
        scaled = int(original * scale) & 0xFF
        b[byteidx] = scaled
        msg.data = bytes(b)
    return msg

def replay(bus, csv_rows, modify_rule=None, log_writer=None):
    if not csv_rows:
        return
    start_ts = csv_rows[0][0]
    t0 = time.time()
    for (ts, ident, is_ext, dlc, data) in csv_rows:
        rel = ts - start_ts
        target = t0 + rel
        now = time.time()
        to_sleep = target - now
        if to_sleep > 0:
            time.sleep(to_sleep)
        msg = can.Message(arbitration_id=ident, is_extended_id=is_ext,
                          data=data, dlc=dlc, is_remote_frame=False)
        if modify_rule:
            msg = apply_modify_rule(msg, modify_rule)
        try:
            bus.send(msg)
            print("[SEND] t={:.6f} ID=0x{:X} EXT={} DLC={} DATA={}".format(
                time.time()-t0, msg.arbitration_id, msg.is_extended_id, msg.dlc,
                ' '.join(f"{b:02X}" for b in msg.data)))
        except can.CanError as e:
            print("Send failed:", e)
        # optionally log what we sent (with timestamp)
        if log_writer:
            log_writer.writerow([time.time(), f"{msg.arbitration_id:X}", int(msg.is_extended_id),
                                 msg.dlc, msg.data.hex()])

def generator_mode(bus, spec, log_writer=None):
    # spec example: id:0x110:d1:00:d2:3C:freq:10
    parts = spec.split(':')
    # naive parser:
    idval = int(parts[1], 16)
    data_bytes = bytearray()
    freq = 1.0
    i = 2
    while i < len(parts):
        if parts[i].startswith('d'):
            # dN:XX pairs => d1:00
            # skip label like d1, take hex next
            i += 1
            val = int(parts[i], 16)
            data_bytes.append(val)
        elif parts[i] == 'freq':
            i += 1
            freq = float(parts[i])
        i += 1
    period = 1.0 / max(0.0001, freq)
    print(f"Generator: ID=0x{idval:X} DATA={data_bytes.hex()} FREQ={freq}Hz")
    try:
        while True:
            msg = can.Message(arbitration_id=idval, is_extended_id=False, data=bytes(data_bytes))
            try:
                bus.send(msg)
            except can.CanError as e:
                print("send err", e)
            print("[GEN SEND] ID=0x{:X} DATA={}".format(msg.arbitration_id, msg.data.hex()))
            if log_writer:
                log_writer.writerow([time.time(), f"{msg.arbitration_id:X}", int(msg.is_extended_id),
                                     msg.dlc, msg.data.hex()])
            time.sleep(period)
    except KeyboardInterrupt:
        print("Generator stopped")

def start_listener(bus, log_writer=None):
    def on_message(msg):
        print("[RECV] t={:.6f} ID=0x{:X} EXT={} DLC={} DATA={}".format(
            time.time(), msg.arbitration_id, msg.is_extended_id, msg.dlc,
            ' '.join(f"{b:02X}" for b in msg.data)))
        if log_writer:
            log_writer.writerow([time.time(), f"{msg.arbitration_id:X}", int(msg.is_extended_id),
                                 msg.dlc, msg.data.hex()])
    # using a notifier thread
    listener = can.BufferedReader()
    notifier = can.Notifier(bus, [listener], 1.0)
    def reader():
        while True:
            msg = listener.get_message(timeout=1.0)
            if msg:
                on_message(msg)
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    return (notifier, t)

def main():
    args = parse_args()
    bus = open_bus(args.iface)
    log_f = None
    log_writer = None
    if args.log_out:
        log_f = open(args.log_out, 'w', newline='')
        log_writer = csv.writer(log_f)
        log_writer.writerow(['ts', 'id_hex', 'is_ext', 'dlc', 'data_hex'])
    # listener will log incoming frames
    notifier, thread = start_listener(bus, log_writer)
    try:
        if args.replay:
            rows = read_replay_csv(args.replay)
            replay(bus, rows, modify_rule=args.modify, log_writer=log_writer)
            print("Replay finished.")
        elif args.gen:
            generator_mode(bus, args.gen, log_writer)
        else:
            print("No mode specified. Listening only. Ctrl-C to exit.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        if log_f:
            log_f.close()
        notifier.stop()
        bus.shutdown()

if __name__ == '__main__':
    main()
