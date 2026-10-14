/* mapdemo.c -- a minimal DJGPP program written to PRODUCE A SYMBOL LISTING.
 *
 * It is never run.  Its whole job is to give `nm` and `ld` a handful of symbols of the
 * classes that decide how the reader behaves, which is why it looks like this:
 *
 *   - `map_demo_a_very_long_symbol_name` is 33 characters, well past the debugger's
 *     15-character name field, so the fixture exercises truncation.
 *   - two STATIC helpers share a name shape that truncates to the same 15 characters,
 *     so it exercises the collision the disambiguator exists for.
 *   - `map_demo_common` is an uninitialised global.  In an OBJECT file `nm` gives it
 *     type `C` and prints its SIZE in the address column; MEASURED in this LINKED
 *     executable it comes back `B` at a real BSS address, because the linker has
 *     allocated it by then.  Both are in the fixture's population for the honest
 *     reason: this is what a real link produces, and a fixture edited to show the type
 *     somebody expected is a fixture that stopped being evidence.
 *   - `map_demo_absolute` is an absolute: type `A`, a constant that is nowhere in the
 *     program.
 *
 * A tidy fixture is where somebody's idea of the input quietly replaces the input, so
 * every one of those is here because the reader has a branch for it.
 */

int map_demo_common;                       /* nm type C: the column holds a SIZE     */
asm(".globl _map_demo_absolute\n"
    ".set _map_demo_absolute, 0x3F8\n");   /* nm type A: a port number, not an address */

static int map_demo_helper_alpha(int v) { return v + 1; }
static int map_demo_helper_bravo(int v) { return v + 2; }

int map_demo_a_very_long_symbol_name(int v)
{
    return map_demo_helper_alpha(v) + map_demo_helper_bravo(v);
}

int map_demo_short(void) { return 7; }

int main(void)
{
    map_demo_common = map_demo_a_very_long_symbol_name(1) + map_demo_short();
    return map_demo_common;
}
