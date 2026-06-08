# Helper function to parse MIDI Variable-Length Quantities
# Takes 4 bytes of input (the maximum length of a VLQ)
# Returns tuple: (parsed value, bytes consumed)
# I hope we never encounter VLQs > 127, but just in case, this is here
def parse_vlq(vlq_bytes):
    result = vlq_bytes[0] & 0x7F
    if not vlq_bytes[0] & 0x80  == 0x80:
        return (result, 1)
    result = (result << 7) & (vlq_bytes[1] & 0x7F)
    if not vlq_bytes[1] & 0x80  == 0x80:
        return (result, 2)
    result = (result << 7) & (vlq_bytes[2] & 0x7F)
    if not vlq_bytes[2] & 0x80  == 0x80:
        return (result, 3)
    result = (result << 7) & (vlq_bytes[3] & 0x7F)
    return (result, 4)

# Try to decode the name from the MIDI file
# We're going to be slightly "bad" here and not properly parse the MIDI, because in practice, the MIDIs in the DJTS ROM are pretty simple
# Assumptions: 
#  * 14-byte header (basically every MIDI ever made has a 14-byte header),
#  * immediately followed by an MTrk chunk (again, basically every MIDI ever),
#  * which has a length > 0 (I wouldn't be surprised if some programs spit out 0-length chunks, but it's probably not a problem here)
# We also expect either an FF 03 or FF 01 meta-event as the first event in the chunk (DJTS is always FF 03), but can fallback if that's not true
# We also ignore the MTrk length because we're only going to parse one event. As long as it's > 0, it doesn't matter.
# All this means we get to skip 22 bytes of parsing! Hooray!
def get_track_name(midi_bytes):
    index = 22
    delta_time, consumed = parse_vlq(midi_bytes[index:index+4])
    if delta_time != 0:
        print("WARNING: non-zero delta time found, MIDI may parse incorrectly")
    index += consumed
    event_id = midi_bytes[index:index+2]
    if event_id != b'\xFF\x03' and event_id != b'\xFF\x01':
        return None
    else:
        index += 2
        name_length, consumed = parse_vlq(midi_bytes[index:index+4])
        index += consumed
        
        # By spec, this should be printable ASCII. But if we were to encounter non-ASCII characters, UTF-8 is a reasonable assumption
        return midi_bytes[index:index+name_length].decode('utf-8')