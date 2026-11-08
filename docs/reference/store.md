# The Store tools

<!-- scry-reference:begin promote -->
## `promote`

*Promote what the session learned*

```text
promote(dry_run=false, entries=null, names=null, root="")
```

What this session learned, written into the repository's store (`.scry/`) only when
approved. `start` keeps the recipe it ran, a map's `add` keeps the map, a
`perform_export` keeps the script; each is complete only with what its reader accepts
(the arguments a recipe cannot boot without, a map the map reader parses, a script
with a check), and a reply that keeps one says `kept N (promote to review)`. The
identity is (kind, name): an entry a call loaded (`start(profile=)`,
`screen_map_write` `load`, `perform(path=)`) names what is learned next, and a name
the store already holds is an update, which keeps the keys a run owns (`logfile`) as the
store has them, and one that changes nothing is named in `unchanged`, not offered.
`dry_run=true` lists every candidate with its
file, its size and whether it is new or an update, an update with its diff; `entries`
(`<kind>/<name>`, the kind one of `start`, `maps`, `perform`) writes only those,
`names` renames one as it is written, and only
that approved call creates `.scry/`. `root` names the repository the store is in or
becomes; without it the nearest `.scry/` above the draft's paths, then above this
server's directory, is used, and a promotion that finds none is refused. Every path is
written as a `project_store` placeholder; one that would leave them is refused, since a
tracked file carries no path of this machine. Reply: `store`, `candidates` and
`unchanged` (a review), `written` and `draft` (an approval), `total_bytes`,
`store_bytes`; `close` names what was left unkept, which stays in the draft until the
server ends. Refused: nothing kept (`needs_call`); an entry the draft does not hold; two
entries written to one file; a candidate the caps cannot hold; an entry that is there
and cannot be read as JSON.

Reference: REFERENCE.md, The store.

| argument | type | default |
|---|---|---|
| `dry_run` | boolean | `false` |
| `entries` | array of string or null | `null` |
| `names` | object or null | `null` |
| `root` | string | `""` |

| reply field | type |
|---|---|
| `candidates` | array |
| `unchanged` | array of string |
| `written` | array |
| `draft` | array of string |
| `total_bytes` | integer |
| `store` | string |
| `store_bytes` | integer |

Example, from a live run:

```json
{
  "dry_run": true,
  "root": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/n31-promote"
}
```

```json
{
  "summary": "promote: 3 candidates in /var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/n31-promote/.scry",
  "status": "ok",
  "store": "/var/folders/_2/sx7y70hj2kb1nqr6fpfrxsd40000gq/T/dosbox-x-live-matrix-<run>/n31-promote/.scry",
  "candidates": [
    {
      "entry": "maps/probe",
      "kind": "maps",
      "name": "probe",
      "file": ".scry/maps/probe.screen-map.json",
      "bytes": 328,
      "change": "new"
    },
    {
      "entry": "start/probe",
      "kind": "start",
      "name": "probe",
      "file": ".scry/start/probe.json",
      "bytes": 122,
      "change": "new"
    },
    {
      "entry": "start/probe-profile",
      "kind": "start",
      "name": "probe-profile",
      "file": ".scry/start/probe-profile.json",
      "bytes": 243,
      "change": "new"
    }
  ],
  "total_bytes": 693,
  "store_bytes": 693
}
```
<!-- scry-reference:end promote -->
