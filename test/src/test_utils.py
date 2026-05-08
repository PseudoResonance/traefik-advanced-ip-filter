import string

def normalize_line_endings(text: str) -> str:
	return text.replace("\r\n", "\n").replace("\n\r", "\n").replace("\r", "\n").rstrip() + "\n"

def capitalize_header(text: str) -> str:
	return string.capwords(text, sep="-")

def convert_header_dict(input: dict[str, str]):
	output = dict()
	for k, v in input.items():
		output[capitalize_header(k)] = v
	return output
