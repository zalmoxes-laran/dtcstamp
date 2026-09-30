# Il profilo `.3tz` canonico (21-10-2026)

**Uno solo, quello di 3DSC** (decisione di E.D. del 30-09-2026). Preso da
`3D-survey-collection/cesium_exporter/archive_3tz.py`, commit `1430128` (ramo
`3DSC-dev-1.7.0`, sha256 del file `3309db81…`), `write_3tz(src_dir, out_path)`
con il suo default `compress=False`. È la stessa regola della costante
`CANONICAL_3TZ_PROFILE` di s3Dgraphy (`resources/tiles3tz.py`, commit
`0bbf68a`), con **una differenza misurata** detta sotto.

Il formato di base è la *3D Tiles Archive Format* v1.3
(github.com/erikdahlstrom/3tz-specification), media type
`application/vnd.maxar.archive.3tz+zip`. Il profilo non la cambia: sceglie, fra
ciò che la specifica permette, l'unica forma per cui **lo sha256 del file nomina
il contenuto e non il momento in cui è stato impacchettato**.

## Le regole

1. `tileset.json` alla radice; nessun percorso contiene `.3tz`.
2. **Voci in ordine di percorso** (ordine dei byte UTF-8 del nome normalizzato:
   barre in avanti, nessuna barra iniziale).
3. **Ogni voce, indice compreso**: data `1980-01-01 00:00:00`, `create_system` 3
   (unix, qualunque sia la macchina), `external_attr` `0o100644 << 16`
   (`0x81a40000`).
4. **STORED**, ogni voce. (`compress=True` esiste in 3DSC e **non** è questo
   profilo: uno stream deflate dipende dal compressore.)
5. Nessun campo extra, salvo lo zip64 per una voce da 4 GB in su.
6. Flag generali **0**, oppure **`0x800` esattamente sulle voci il cui nome non
   è ASCII** (vedi sotto).
7. `.DS_Store` e `Thumbs.db` mai impacchettati.
8. L'indice `@3dtilesIndex1@` è **l'ultima voce, STORED**: record di 24 byte,
   MD5 del percorso normalizzato + offset uint64 LE dell'intestazione locale,
   **ordinati per l'MD5 letto come due uint64 little-endian** (byte 0-7, poi
   8-15).

`create_version` non è una regola: Python scrive 20 (3DSC), `3d-tiles-tools`
scrive 45. Si riferisce e non si esige.

## La differenza con s3Dgraphy (misurata il 30-09-2026)

`CANONICAL_3TZ_PROFILE` chiede `flag_bits == 0` a ogni voce. Ma il `zipfile` di
Python — quindi 3DSC — mette il bit 11 (`0x800`, «il nome è UTF-8») su ogni voce
il cui nome non è ASCII: scritto con 3DSC un albero con `Data/città.b3dm`,
`is_canonical_3tz` di s3Dgraphy risponde *non canonico* («general purpose flags
are set») a un archivio del profilo stesso. Il bit è deterministico (dipende
solo dal nome), quindi qui è ammesso, e solo lì. **s3Dgraphy va allineato**
(decisione di E.D. del 30-09: flag 0x800 ammesso).

## Chi lo verifica

`dtcstamp.is_canonical_3tz(path)`: criterio per criterio, con le ragioni. Un
`.3tz` non canonico resta un `.3tz` leggibile, e il suo `content_digest` è
quello della forma canonica: è instabile solo il suo sha256.

Misurato: il `.3tz` di `3d-tiles-tools` 0.5.4 **non è canonico per due
ragioni** — ogni voce porta l'ora di scrittura, e negli attributi c'è il bit
«archivio» del DOS (`0x81a40020`). È il caso `21` della conformità.

## Il caso che ogni scrittore riproduce

`conformance/20-tileset-folder-and-3tz.json`: si scrivono i file di `tree.files`
in una cartella, la si impacchetta con il proprio scrittore, e lo sha256 deve
essere `expect.archive_sha256` byte per byte. Misurato: il modulo di 3DSC lo
riproduce.
