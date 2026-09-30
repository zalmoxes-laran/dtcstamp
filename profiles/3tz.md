# Il profilo `.3tz` canonico (21-10-2026, rivisto il 22-10-2026)

**Uno solo, quello di 3DSC** (decisione di E.D. del 30-09-2026). Preso da
`3D-survey-collection/cesium_exporter/archive_3tz.py`, commit `1430128` (ramo
`3DSC-dev-1.7.0`, sha256 del file `3309db81…`), `write_3tz(src_dir, out_path)`
con il suo default `compress=False`, **più la normalizzazione NFC dei nomi**
che 3DSC fa dal 22-10-2026. È la stessa regola della costante
`CANONICAL_3TZ_PROFILE` di s3Dgraphy (`resources/tiles3tz.py`), che da quel
giorno rimanda qui come fonte del profilo.

Il formato di base è la *3D Tiles Archive Format* v1.3
(github.com/erikdahlstrom/3tz-specification), media type
`application/vnd.maxar.archive.3tz+zip`. Il profilo non la cambia: sceglie, fra
ciò che la specifica permette, l'unica forma per cui **lo sha256 del file nomina
il contenuto e non il momento in cui è stato impacchettato**.

## Le regole

1. `tileset.json` alla radice; nessun percorso contiene `.3tz`.
2. **Voci in ordine di percorso** (ordine dei byte UTF-8 del nome normalizzato:
   NFC, barre in avanti, nessuna barra iniziale).
3. **Ogni voce, indice compreso**: data `1980-01-01 00:00:00`, `create_system` 3
   (unix, qualunque sia la macchina), `external_attr` `0o100644 << 16`
   (`0x81a40000`).
4. **STORED**, ogni voce. (`compress=True` esiste in 3DSC e **non** è questo
   profilo: uno stream deflate dipende dal compressore.)
5. Nessun campo extra, salvo lo zip64 per una voce da 4 GB in su.
6. **Ogni nome in Unicode NFC**, prima dell'ordinamento, del nome
   nell'archivio e dell'MD5 dell'indice (vedi sotto). Due file che in NFC hanno
   lo stesso nome non si impacchettano: lo scrittore si ferma e li nomina.
7. Flag generali **0 sui nomi ASCII, `0x800` sui nomi NFC non ASCII**, e
   nient'altro (vedi sotto).
8. `.DS_Store` e `Thumbs.db` mai impacchettati.
9. L'indice `@3dtilesIndex1@` è **l'ultima voce, STORED**: record di 24 byte,
   MD5 del percorso normalizzato (NFC) + offset uint64 LE dell'intestazione locale,
   **ordinati per l'MD5 letto come due uint64 little-endian** (byte 0-7, poi
   8-15).

`create_version` non è una regola: Python scrive 20 (3DSC), `3d-tiles-tools`
scrive 45. Si riferisce e non si esige.

## Il flag `0x800` (decisione di E.D. del 30-09-2026)

Il `zipfile` di Python — quindi 3DSC — mette il bit 11 (`0x800`, «il nome è
UTF-8») su ogni voce il cui nome non è ASCII, e su nessun'altra. Il bit dipende
solo dal nome, quindi è deterministico: è del profilo, esattamente lì. Un nome
non ASCII **senza** il bit sarebbe letto in CP437 da ogni lettore zip, cioè un
altro nome; un nome ASCII **con** il bit è una scelta dello scrittore che il
nome non chiede, e cambia i byte.

Fino al 22-10-2026 `CANONICAL_3TZ_PROFILE` di s3Dgraphy chiedeva `flag_bits == 0`
a ogni voce e diceva *non canonico* all'archivio di 3DSC di `Data/città.b3dm`.
Misurato e allineato: oggi i due verificatori dicono la stessa cosa (caso `23`).

## I nomi in NFC

**macOS dà i nomi in NFD** (`città` come `citta` + U+0300), Linux e Windows li
danno come sono stati scritti, di solito NFC. Senza normalizzare, **la stessa
cartella dà due sha256**: misurato il 22-10-2026 col modulo di 3DSC a `1430128`,
lo stesso albero con `Data/città.b3dm` dà `4d92f8eb…` in NFC e `4dc917e6…` in
NFD. La forma canonica è NFC, la stessa del `content_digest` (`member_path`):
normalizza chi scrive, e `is_canonical_3tz` dice *non canonico* a un nome NFD
(criterio `names_nfc`). Il `content_digest` di un archivio con nomi NFD è comunque
quello giusto, perché normalizza anche lui: è instabile solo lo sha256 del file.

## Il `content_digest` lo calcola chi produce

Lo scrittore che impacchetta legge già ogni byte: calcola il `content_digest`
(`role NUL percorso NUL sha256:<hex> LF`, righe in ordine dei byte UTF-8 del
percorso NFC, `tileset.json` `entry_point`, esclusi `.DS_Store`, `Thumbs.db` e
l'indice) durante la scrittura, senza una seconda passata, e lo dichiara
`computed_by: producer`. 3DSC lo fa dal 22-10-2026 (`write_3tz` →
`content_digest`) e lo scrive nel log e nella barra; non scrive ancora un timbro.

## Chi lo verifica

`dtcstamp.is_canonical_3tz(path)`: criterio per criterio, con le ragioni. Un
`.3tz` non canonico resta un `.3tz` leggibile, e il suo `content_digest` è
quello della forma canonica: è instabile solo il suo sha256.

Misurato: il `.3tz` di `3d-tiles-tools` 0.5.4 **non è canonico per due
ragioni** — ogni voce porta l'ora di scrittura, e negli attributi c'è il bit
«archivio» del DOS (`0x81a40020`). È il caso `21` della conformità.

## Il caso che ogni scrittore riproduce

`conformance/20-tileset-folder-and-3tz.json` e, con un nome non ASCII,
`conformance/23-tileset-non-ascii-name.json`: si scrivono i file di `tree.files`
in una cartella, la si impacchetta con il proprio scrittore, e lo sha256 deve
essere `expect.archive_sha256` byte per byte. Misurato: il modulo di 3DSC li
riproduce entrambi, il 23 anche dalla cartella scritta in NFD.
