// synthetic source for the tests of the namer: it is not DOSBox-X code

void VGA_SetupDAC(void) {
	IO_RegisterWriteHandler(0x3c8, write_p3c8, IO_MB);
	IO_RegisterReadHandler(0x3c8, read_p3c8, IO_MB);
}
