/* MAPDEMO.C -- a minimal Open Watcom program written to PRODUCE A LINKER MAP.
 *
 * It is never run.  Its job is to give WLINK symbols of the classes that decide how the
 * reader behaves, which is why it looks like this:
 *
 *   - TWO STATICS, so the map carries the `s` mark GLUED to the address.  That mark is
 *     the shape this artefact exists to capture, and `OPTION STATICS` is what makes the
 *     linker print it at all -- without it the map lists only publics and the mark never
 *     appears.
 *   - one static that is never called.  It was put here to produce the `*`
 *     (unreferenced) mark, and MEASURED, IT DOES NOT: `-oc` removes it before the
 *     linker ever sees it, and `map_demo_unused` appears nowhere in the map.  It is
 *     kept because it costs nothing and documents the attempt; the `*` mark IS in the
 *     artefact, fourteen times, from the C library's own symbols -- which is where an
 *     unreferenced symbol realistically comes from anyway.
 *   - symbols in CODE and in DATA, so the map spans MORE THAN ONE SECTION.  With one
 *     section a reader that consults the section index and one that ignores it produce
 *     the same answer, and the fixture asserts nothing about the feature it exists for.
 *
 * A tidy fixture is where somebody's idea of the input quietly replaces the input.
 */

/* Optimised away by `-oc` before the linker sees it: see the header. */
static int map_demo_unused(int v)   { return v * 3; }
static int map_demo_local(int v)    { return v + 1; }

int  map_demo_table[4] = { 1, 2, 3, 4 };
int  map_demo_count;
char map_demo_tag[8] = "MAPDEMO";

int map_demo_reached(int v)
{
    return map_demo_local(v) + map_demo_table[0];
}

int main(void)
{
    map_demo_count = map_demo_reached(1) + map_demo_tag[0];
    return map_demo_count;
}
