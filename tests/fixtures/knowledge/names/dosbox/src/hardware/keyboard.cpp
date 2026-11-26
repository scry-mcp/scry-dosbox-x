// synthetic source for the tests of the namer: it is not DOSBox-X code

void KEYBOARD_Init(Section* sec) {
	IO_RegisterReadHandler(0x60, read_p60, IO_MB);
}
