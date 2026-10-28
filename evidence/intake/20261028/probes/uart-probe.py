import os, select, time, struct, math, json, termios, tty
fd=os.open('/dev/ttyS7',os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
original=termios.tcgetattr(fd)
try:
    tty.setraw(fd)
    attrs=termios.tcgetattr(fd); attrs[4]=termios.B115200; attrs[5]=termios.B115200
    termios.tcsetattr(fd,termios.TCSANOW,attrs)
    termios.tcflush(fd,termios.TCIFLUSH)
    start=time.monotonic(); raw=bytearray()
    while time.monotonic()-start < 5:
        if select.select([fd],[],[],0.1)[0]: raw.extend(os.read(fd,65536))
finally:
    termios.tcsetattr(fd,termios.TCSANOW,original); os.close(fd)
frames=[]; invalid=0; pos=0; header=b'\x55\xd1\x00\x02'
while True:
    at=raw.find(header,pos)
    if at<0 or at+54>len(raw): break
    packet=raw[at:at+54]
    if sum(packet[:52])&65535 == struct.unpack('<H',packet[52:54])[0]:
        frames.append(struct.unpack('<12f',packet[4:52])); pos=at+54
    else: invalid+=1; pos=at+1
print(json.dumps({'mode':'receive_only_temporary_115200_raw_restore_on_exit','seconds':time.monotonic()-start,'bytes':len(raw),'header_hits':raw.count(header),'valid_frames':len(frames),'bad_checksum_candidates':invalid,'finite_frames':sum(all(math.isfinite(v) for v in a) for a in frames),'mean_acceleration_norm':sum(math.sqrt(sum(v*v for v in a[3:6])) for a in frames)/len(frames) if frames else None,'samples':frames[:2],'prefix_hex':raw[:54].hex()},indent=2))
