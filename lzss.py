def decompress(input_bytes):
	index = 0
    
	header_byte = input_bytes[index]
	shift = header_byte & 0b111
	entries = 0b01111111 >> shift
	inflection = (entries >> 1 if entries < 0b00011111 else 19) # Condition is equivalent to shift < 3
	inflected_growth = 1 << (header_byte >> 3 & 0b11) # There's some weird arithmetic going on here in the source - I think this is right?
	lengths_array = [x+3 if x <= inflection else 3 + inflection + (x-inflection)*inflected_growth for x in range(entries+1)]
	# Appears to be the number of symbols (raw bytes or backreferences) to expect to decode
	total_symbols = int.from_bytes(input_bytes[index+1:index+4], byteorder='big') # Seems to be BE despite NTR being LE
	index += 4

	output = bytes()
	symbols = 0
	finished_flag = False
	while True:
		flags_byte = input_bytes[index]
		index += 1
		for i in range(8):
			is_raw = flags_byte & 0b1 == 0b1
			flags_byte >>= 1
			if is_raw:
				output += input_bytes[index].to_bytes()
				index += 1
			else:
				backshift_token = int.from_bytes(input_bytes[index:index+2], byteorder='big') # Yes, it's BE again - I get the feeling this wasn't originally written for NTR lol
				backshift_offset = backshift_token >> (7 - shift)
				backshift_length = lengths_array[backshift_token & (0x7F >> shift)]
				# We might try to copy more bytes than we currently have available, so loop manually and copy byte by byte
				output_idx = len(output) - backshift_offset
				#print("BSO: "+str(backshift_offset))
				#print("Output Index: "+str(output_idx))
				for j in range(backshift_length):
					#print(f"{output[output_idx]:02x}")
					output += output[output_idx].to_bytes()
					output_idx += 1
				index += 2
			symbols += 1
			if symbols == total_symbols:
				finished_flag = True
				break
		if finished_flag:
			break

	return output