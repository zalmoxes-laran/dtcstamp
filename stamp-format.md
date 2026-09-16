# Il timbro — formato deciso (14-09-2026)

> **Nota sulla lingua.** Questa specifica è in italiano perché è nata così, e
> muoverla di repo non è il momento di riscriverla: una traduzione fatta di
> fretta perderebbe le distinzioni che queste pagine esistono per fare. Una
> versione inglese è una decisione aperta — il formato esce dal nostro perimetro,
> e i NOMI dei file sono già in inglese per quel motivo. Vedi il README.

## Questo NON è un registro distribuito

Nessun consenso, nessun ordinamento globale, nessuna rete, nessun token, niente
da minare e nessuno con cui mettersi d'accordo.

Va detto per primo perché «catena» più «hash» più «immutabile» si legge
*blockchain*, quella domanda arriverà ogni volta, e conviene che la risposta la
preceda: **un timbro è un file JSON che una persona scrive accanto a un file che
ha fatto**, e una catena è quello che si ottiene seguendo i digest all'indietro.

Da cui tre conseguenze che il resto del documento dà per acquisite. L'identità è
**locale e verificabile da chiunque** — si ricalcola l'impronta e si guarda — e
non richiede che qualcuno attesti alcunché. Due timbri che si contraddicono sullo
stesso digest **restano tutti e due**, perché non c'è un registro che debba
convergere su una versione sola: la contraddizione è una scoperta e la si fa
emergere. E non c'è **nessuna autorità**: chi scrive un timbro afferma qualcosa e
lo firma, e chi legge decide quanto fidarsi, esattamente come per qualunque altra
affermazione scritta da una persona.

Il valore non sta nell'impossibilità di mentire — mentire è possibilissimo — ma
nel fatto che **una provenienza sbagliata si può contestare**, perché dice chi
l'ha affermata e quando.


Il timbro è il **verbale immutabile di un passo**: un agente, con un processo e dei parametri, consuma uno o
più ingressi e produce **un** artefatto. Non è un formato nuovo: i nodi che cita — risorsa, processo con
parametri, agente, licenza, embargo — sono già tipi di s3Dgraphy. È un **frammento di em.json**, scritto in
miniatura, e riattaccarlo al grafo è un merge per UUID.

## Tre strati, e cosa sta in quale

**L'identità** è un digest: non cambia mai, sta nel timbro. **Il timbro** nomina i suoi ingressi **solo per
identità**, mai per percorso. **Le piste** — «ho visto questo digest in questo posto, in questo momento» — sono
un registro mutevole, plurale e non autorevole che sta **fuori** dal timbro, per necessità: un record
immutabile non può contenere un campo mutevole, perché riscriverlo ne cambierebbe il contenuto e quindi
l'identità.

Il guadagno: **una pista sbagliata è innocua**, perché la si segue, si ricalcola il digest e o è la cosa giusta
o ci si accorge subito. Un sistema che punta per nome consegna *in silenzio* il file sbagliato.

## L'identità del timbro è quella di ciò che descrive

Un timbro **non ha identità di contenuto propria**: è chiavato dal **digest della sua uscita**. Quindi non
serve nessuna serializzazione canonica, e non si deve dipendere dal fatto che due implementazioni producano gli
stessi byte per gli stessi fatti (è la lezione già pagata sul `jsonb`).

Regola che ne discende: **due timbri per lo stesso digest di uscita che si contraddicono nella sostanza —
genitori diversi, processo diverso — non sono un errore, sono una scoperta**, e vanno fatti emergere. Due che
differiscono solo nell'istante sono lo stesso fatto registrato due volte, e si deduplicano.

## Il formato

```json
{
  "stamp": 1,
  "self": {
    "resource_id": "res:7f3a2c…",
    "digest": "sha256:6e4a5f…",
    "digest_covers": "artifact",
    "media_type": "model/gltf+json",
    "format": "gltf",
    "packaging": "file",
    "tier": "distribution",
    "measures": { "size_bytes": 1234567, "faces": 48210 }
  },
  "from": [
    { "resource_id": "res:91c2…", "digest": "sha256:aa17b3…",
      "size_bytes": 84213760,
      "label": "GT16 · rilievo 2015, nuvola" },
    { "resource_id": "acq:5b7e…", "kind": "acquisition",
      "label": "campagna Aiano 2015" }
  ],
  "how": {
    "process_id": "proc:d41e…",
    "dtc_kind": "transformation",
    "technique": "decimation",
    "parameters": { "target_faces": 50000, "preserve_boundary": true },
    "software": [
      { "name": "EM Tools", "version": "1.6.0-dev.8", "commit": "9555447" },
      { "name": "s3dgraphy", "version": "1.6.0.dev17", "commit": "afe62e3" }
    ],
    "acquisition": { "device": { "id": "dev:3004afbb-4f86-598a-94ec-0cf0fef46c92",
                                 "label": "Nikon D850",
                                 "make": "Nikon", "model": "D850",
                                 "serial": "3018522",
                                 "dtc_kind": "camera",
                                 "distinguishes": "serial" },
                     "location": { "lat": 43.1102, "lon": 11.8423, "alt": 412.0,
                                   "crs": "EPSG:4326", "source": "exif" },
                     "lens": "24mm f/1.8",
                     "campaign": "Aiano 2015" }
  },
  "by": {
    "operator": { "id": "https://orcid.org/0000-0002-5065-7970",
                  "label": "Emanuel Demetrescu" },
    "at": "2026-09-15T20:14:07Z"
  },
  "declared": { "license": "CC-BY-NC", "embargo_until": "2025-12-31",
                "as_of": "2026-09-15T20:14:07Z",
                "by": { "id": "https://orcid.org/0000-0002-5065-7970",
                        "label": "Emanuel Demetrescu" } },
  "registry": { "graph_id": "graph:6af9866e…", "label": "Great Temple",
                "revision": 47, "room": "em.localhost/aiano" }
}
```

### Le scelte che non sono ovvie

`digest_covers` dichiara cosa il digest copre — `artifact` (i byte come usciti dal processo) o `payload` (il
contenuto al netto del timbro, quando il timbro vive dentro il vascello). Stessa disciplina del `checksum_of`
del tileset: il digest **dice** cosa copre invece di lasciarlo intuire.

`from` **non porta mai un percorso**. Nominare e non aprire è la regola che ferma la ricorsione: è
tutta lì la differenza fra il passo e la catena. La `label` è cortesia per un umano, non identità.

Il software sta in `how`, non in `by`, perché è un parametro a tutti gli effetti — lo stesso algoritmo in due
versioni non produce gli stessi byte — e porta **il commit**, non solo la versione: «EM Tools 1.6» non dice
quale build.

`technique` e `parameters` sono separati: «decimation» è la tecnica, `target_faces 50000` è come è stata
applicata. Serve a interrogare la tecnica senza interpretare i parametri.

`from` porta **`size_bytes`**, e non è ridondanza: è ciò che rende economica la **ricerca di un genitore**.
Riconoscere un file costa poco perché il suo timbro dichiara la dimensione e il filtro scarta senza leggere un
byte; senza la stessa cifra sulla voce `from`, cercare un genitore smarrito costerebbe hashare tutto. Non può
contraddire l'identità (stesso digest ⇒ stessa dimensione), quindi è un derivato che non invecchia. Aggiunto in
modo **additivo**: i timbri emessi prima restano validi, chi legge lo tratta come facoltativo.

`from` ha un quarto campo **`kind`** per un ingresso che non è un file: una campagna di acquisizione è un
ingresso legittimo e **non ha byte da hashare**. `kind: "acquisition"` lo dichiara, e il `digest` manca senza
che sia un difetto.

**`dtc_kind` e `technique` sono due granularità, non due nomi.** `dtc_kind` viene dal vocabolario controllato
(`photogrammetry`, `transformation`, …) ed è l'asse su cui si interroga; `technique` è la parola libera di chi
ha fatto il gesto — «decimation» non sta nel vocabolario e non ci deve entrare. Senza `dtc_kind` il giro
completo perde un campo che il costruttore valida. **Il vocabolario non si allarga da un file arrivato da
fuori**: un genere sconosciuto cade sul default.

**`how.acquisition` è la casa dei fatti dell'atto di acquisizione** — apparecchio, obiettivo, campagna,
condizioni — e non vanno in `parameters`, che vuol dire «come la tecnica è stata applicata». È la distinzione
che CRM3D fa fra `L12 happened on device` e `L13 used parameters`. Blocco aperto. Per un rilievo fotogrammetrico
è metà di quello che serve fra vent'anni.

**`how.acquisition.device` è un'IDENTITÀ, non una stringa** (16-09-2026). Era «Nikon D850», e una stringa non
si interroga: «cosa ha prodotto questa macchina», «quali rilievi hanno usato quello scanner», «quell'obiettivo
si è rivelato distorto, quali modelli ne sono affetti» sono tre domande che con una stringa non esistono. Ora
porta un `id` derivato dal descrittore — marca, modello, e **numero di serie quando c'è** — più l'etichetta e
il descrittore stesso, e vale la regola delle etichette: una `label` che ripete l'id va omessa.

`distinguishes` è la parte onesta e viaggia con l'id: **`serial`** vuol dire che quell'id nomina un CORPO,
**`make+model`** che nomina un MODELLO e che due corpi identici lo condividono. Senza numero di serie due
fotocamere uguali si fondono in un'identità sola, e chi legge il timbro fuori dal nostro perimetro deve poterlo
sapere invece di dedurlo: è una perdita d'informazione, non un dettaglio di implementazione. Una fusione
dichiarata è meglio di una distinzione inventata — salare l'id con qualcosa che non riguarda l'apparecchio (un
grafo, un istante, un contatore) farebbe sembrare due macchine due registrazioni della stessa, e *quel*
fallimento è silenzioso.

**`how.acquisition.location` porta valori nudi** (16-09-2026): `lat`, `lon`, `alt`, il `crs`, e **`source`**,
che dice se la posizione l'ha letta una macchina (`exif`) o l'ha battuta una persona (`stated`) — perché le due
hanno statuto diverso, ed è la stessa disciplina di `identity_strength`. Il blocco è **chiuso**, al contrario
di `acquisition` che lo contiene: ciò che conta di uno strumento cambia con lo strumento, mentre una posizione
è una posizione, e un elenco aperto qui avrebbe lasciato uscire prima o poi l'ombra di un nodo.

**E qui il formato dice la sua regola più importante: valori, mai tipi.** Delle coordinate sono numeri più un
codice EPSG — universali — e chi scrive un plugin per Metashape non deve sapere che cosa sia un nodo di
geolocalizzazione per leggere dov'era la fotocamera. La libreria che implementa questo formato **non conosce
nessun nome di classe** di nessun consumatore, ed è quello che le permette di essere un file solo da copiare.
Trasformare i valori in nodi tipizzati è il lavoro di chi un grafo ce l'ha.

Vale la regola di ammissione: **entra solo ciò che serve a capire il passo quando il grafo non è
raggiungibile.** Le coordinate passano — una foto senza le sue coordinate perde ciò che la rende ritrovabile.
Un nodo di geolocalizzazione con le sue relazioni no: quello è grafo, e chi lo vuole ha il grafo.

**Un'etichetta che ripete l'identificatore non è un'etichetta**, ed è meglio assente: una `label` che ridice
l'ORCID va omessa, non duplicata.

**`declared` atterra su `data.declared` del nodo del passo e NON si materializza** in un `LicenseNode` con
`has_license`: materializzarlo farebbe decidere il cancello vivo a un file arrivato per posta, non riassorbirlo
romperebbe il giro completo.

**`declared` porta `by`, cioè chi lo ha dichiarato.** `rights.py` fa questa distinzione con cura — l'autore è
chi ha fatto il dato, l'**attributore** è chi lo dice, e l'atto è firmato — e senza di essa un timbro che
afferma «CC-BY-NC al 15 settembre» perde metà di ciò che serve per **contestarlo**: si sa cosa è stato
dichiarato e non da chi. Vale anche qui la regola delle etichette: una `label` che ripete l'id va omessa.

**`registry` lo passa chi emette**: `revision` e `room` non stanno nel grafo, e se assenti restano assenti.

`by.operator` **può mancare**: quando manca, l'agente è il software nominato in `how`. Una regola sola, nessuna
ridondanza — è il caso del bake in batch, del servizio, del chatbot che produce risorse.

`declared` è **storia, non regola**: licenza ed embargo come dichiarati allora, con `as_of` a dirlo. Il
cancello vivo sta altrove.

`registry` è un **indizio per ritrovare, non un'autorità**, e porta la `revision`, che è ciò che rende citabile
qualcosa che non cambia sotto i piedi.

## Le piste — file separato, mutevole, mai coperto dal digest

```json
{
  "hints": 1,
  "digest": "sha256:aa17b3…",
  "seen": [
    { "locator": "s3://em-assets/res_91c2/nuvola.ply", "kind": "s3",
      "scope": "public", "when": "2026-09-14T09:12:00Z" },
    { "locator": "/Users/…/rilievi/2015/nuvola.ply", "kind": "local",
      "scope": "private", "machine": "mbp-ed", "when": "2026-09-14T18:40:11Z" }
  ]
}
```

`scope` decide cosa viaggia: una pista `public` (un URI dello store) può accompagnare un artefatto pubblicato;
una pista `private` **non esce mai**, perché un percorso assoluto pubblicato è inutile agli altri e indiscreto
— porta il nome utente, la struttura delle cartelle, a volte il nome di un committente.

Le piste **non si cancellano, invecchiano**. Nessuna manutenzione e nessuna richiesta all'utente di sistemare i
percorsi: aggiornamento **opportunistico** (ogni volta che uno strumento tocca un file ne calcola il digest e
annota «visto qui, adesso») e **su richiesta** (scansione di una cartella).

## I due casi limite

**Il passo vuoto**: `"from": []` è una dichiarazione **completa** — nato qui, da questa persona, in questo
momento. In un progetto archeologico metà degli asset sono origini: trattare l'assenza di genitori come errore
trasforma metà del progetto in rumore.

**Il digest di sé**: se il timbro vive dentro il vascello, scriverlo cambia i byte — `digest_covers: "payload"`.

## Il limite dichiarato: l'identità è più debole all'origine

Il digest di un **datablock dentro un .blend non è il digest di un file**: non ci sono byte canonici, il .blend
cambia per ragioni che non c'entrano con quella mesh. Quel che c'è è l'impronta strutturale (vertici, facce,
bounding box, nomi dei materiali, sulla mesh valutata), che basta ad **accorgersi che è cambiata** ma non a
**verificare che è lei**. Va **dichiarato**: per un master `blend://`, `self.digest` porta un prefisso diverso
— `emstruct1:` invece di `sha256:` — così chi legge sa che quella riga non è verificabile come le altre.

La catena è **forte all'estremità pubblicata e molle all'estremità autoriale**: fino al bake *ricorda*, dal
bake in poi *dimostra*.

## Nomi dei file

`<asset>.stamp.json` e `<asset>.hints.json`, in inglese perché il formato esce dal nostro perimetro. Non
`em.json` (specie diversa: inviterebbe a fondere, editare, versionare il timbro). Non `dtc.json` (promette una
catena e consegna un anello).

## Aperto

Il timbro dell'insieme per i cluster di .blend linkati. Quando un PID sostituisce il puntatore in `registry`.
Chi verifica i digest e quando — ricalcolare l'impronta di una nuvola da duecento milioni di punti non è un
gesto casuale, quindi su richiesta e non a ogni apertura.

## Quando qualcuno riordina senza EMStudio (aggiunto 14-09-2026)

È il caso normale: la maggior parte dei riordini avviene nel Finder, per mano di chi non ha i nostri strumenti
e vede un `.json` accanto a un `.glb`.

**Cosa sopravvive.** Coppia mossa insieme: non è successo niente, basta una pista nuova. File rinominato e
timbro no: il timbro sembra solitario ma dichiara `self.digest`, quindi si ricalcola l'impronta dei file lì
intorno e si riaccoppia. File spostato e timbro rimasto: stessa cosa su un albero più largo. File copiato: due
copie dello stesso digest sono coperte dallo stesso timbro — un timbro descrive byte, non un percorso.

**Cosa non sopravvive.** Il timbro cancellato perché sembra spazzatura: lì la copia locale è persa e si
recupera solo da un altro detentore (il grafo, la tabella, la copia nello store). È la ragione per cui il
timbro accanto al file è una **cortesia** e non la verità: è la copia che una persona può cancellare senza
sapere cosa cancella, e il sistema è disegnato perché nessun detentore singolo sia necessario.

**Il caso che un sistema a nomi sbaglierebbe.** File riaperto e riesportato sopra: il digest cambia. Il timbro
non è rotto, è **un'affermazione vera su byte che non ci sono più**, e il file nuovo è un artefatto non
timbrato. Riaccoppiare per nome attaccherebbe in silenzio la vecchia provenienza ai byte nuovi. Quindi il
riordino ingenuo è recuperabile in tutti i casi tranne uno, e quell'uno è precisamente quello in cui un sistema
basato sui nomi non fallirebbe: darebbe una risposta sbagliata.

**Lo strumento di riparazione.** Raccoglie i timbri di un albero e i file di dati, confronta per digest, e
riferisce **tre classi**: accoppiati, timbri senza byte, byte senza timbro. Un timbro senza byte non dice da
solo se il file è stato spostato, rinominato fuori dall'albero, cancellato o modificato: sono cose diverse e
non si indovinano. Due regole: si **rinomina il timbro per seguire il file, mai il contrario** (il nome del
file lo ha scelto una persona e vuol dire qualcosa; il nome del timbro non porta informazione, la porta il
contenuto), e l'accettazione è **sempre** per digest.

**Il costo.** Ricalcolare l'impronta di un albero fotogrammetrico da centinaia di GB a ogni scansione non si
può fare. Tre filtri in cascata, e nessuno dei tre è il legame: la **somiglianza del nome** ordina i tentativi,
la **dimensione** (`measures.size_bytes`, che il timbro porta) scarta i candidati impossibili prima di leggere
un byte, il **digest** accetta. Su una cartella di quattrocento scatti la dimensione riduce i candidati a una
manciata e di solito si hasha esattamente un file. Cache delle impronte per `(percorso, dimensione, mtime)`.
`measures.size_bytes` non è decorazione: è **l'indice del recupero**.

**Il lettore di ultima istanza** è un umano con un editor di testo, fra trent'anni: un'altra ragione per
`.stamp.json` e per scriverlo leggibile invece che compatto.


## Stato dell'implementazione (aggiornato 15-09-2026, sera)

Deciso e **implementato**: struttura a sei blocchi, `digest_covers`, `from` per identità, `dtc_kind`,
`declared` su `data.declared`, `kind: "acquisition"`, `identity_strength` a tre risposte, piste con `scope`.

**Chiuse stanotte** le quattro che erano dichiarate e non scritte:

* **`size_bytes` sulla voce `from`** — `_from_block` lo emette quando la risorsa lo dichiara. Additivo: un
  genitore di cui non si conosce la dimensione esce senza il campo e non è un errore. Un valore che una
  dimensione non è (un booleano, un negativo, una stringa) non entra.
* **`how.acquisition`** — `_how_block` lo emette da `data["acquisition"]` quando c'è, e altrimenti, per un
  nodo `dtc_acquisition`, da ciò che resta del suo `data` tolti i campi strutturali. Così
  `bucket_acquisition` funziona com'è: fondeva già i fatti del lotto sull'evento, mancava la porta per
  uscirne. Una volta sola: non anche in `parameters`.
* **`label` che ripete l'id** — omessa, e per **ogni** etichetta del timbro (ingresso, operatore, registro),
  confrontando anche l'ultimo segmento: `https://orcid.org/0000-…` e `author:0000-…` sono due vestiti della
  stessa stringa.
* **`api.declare_derivation` inoltra** `dtc_kind`/`technique`/`parameters`/`software`. Misurato prima di
  toccarla: la funzione sottostante accettava **solo** `dtc_kind` — gli altri tre non esistevano nemmeno lì,
  e sono stati aggiunti. `data.tool` resta compilata dal primo software, ma **non soppianta** un `tool`
  passato a mano.

Corretto insieme, perché era un cancello e non un fastidio: **`rights._sections` non leggeva un em.json a
grafo singolo**. Cercava `graphs` (plurale, la forma container) mentre `build_emjson`/`export_emjson`
scrivono `graph`, e su quei documenti trovava zero sezioni e rispondeva «di questo asset non so niente».
I due chiamanti che decidono se trattenere — `iiif.iiif_manifest` e `contract.consumer` — scrivono entrambi
`if rights and rights.get("embargo_active")`: su `None` **non trattengono**, quindi un embargo scritto nel
grafo e serializzato usciva in un manifesto IIIF.

**Resta aperto**, e non è piccolo: `None` da `rights_for_digest` significa «non conosco questo digest» e i
due cancelli lo trattano come via libera. Oggi è coerente col significato documentato, ma è un fallimento
aperto per costruzione — chi decide se un cancello debba chiudersi sull'ignoto è E.D., non una riga.

**Chiuso il 15-09-2026**: `declared.by`, l'attributore. Era deciso e non scritto, ed è diventato bloccante il
giorno in cui EMStudio ha cominciato a emettere verbali d'ingestione: l'onestà di quel verbale sta tutta nel
dire «questa persona è l'**attributore**, non l'autore», e senza la firma un timbro che afferma «CC-BY-NC al
15 settembre» non dice da chi — cioè **non è contestabile**.

`rights_for_digest` ora riporta `attributed_by` (una **lista**, perché licenza ed embargo possono essere stati
firmati da due persone diverse) e `_declared_block` la scrive come `declared.by`. **Con due firmatari non se
ne sceglie uno**: scrivere un nome accanto a una dichiarazione che tiene insieme due affermazioni direbbe una
cosa falsa su metà di esse, quindi `by` si omette e il grafo — che le firme le ha tutte — resta il posto dove
guardare. Vale la regola delle etichette: una `label` che ripeterebbe l'iD va omessa. Sopravvive al giro
completo, riassorbimento compreso.

**Resta aperto** (e non è del formato, è del lettore): `None` da `rights_for_digest` significa «non conosco
questo digest» e i due cancelli lo trattano come via libera.

**Chiuso il 16-09-2026 (HW1)**: `how.acquisition.device` come identità e `how.acquisition.location` come
valori — vedi sopra. Dal lato s3Dgraphy l'apparecchio è diventato un nodo (`DTCDeviceNode`, crmdig:D8) attaccato
all'evento da `dtc_happened_on_device` (crmdig:L12), che è **contesto e non catena**: una risalita di
provenienza non ci entra.

**Resta aperto**: il luogo non ha un nodo tipizzato dall'altra parte. In s3Dgraphy l'unico E53_Place è
`GeoPositionNode`, che è l'**ancora della scena**, una per grafo, e il suo stesso docstring dice che «non è dove
va il puntino sulla mappa» — scriverci dentro dove è stata scattata una foto sovrascriverebbe lo shift del
grafo con una coordinata di campo. Il tipo per «dove è avvenuto un passo» non esiste, e non è stato inventato:
i valori viaggiano e tornano sull'evento. Decisione di E.D.

## Dove vive questo formato

Da oggi in una libreria sua: **un modulo solo, senza dipendenze di terze parti**, che si copia accanto al
proprio codice invece di essere installato. Leggere, scrivere, validare, confrontare due timbri, risalire una
catena e misurare la forza di un'identità non hanno mai avuto bisogno di un grafo — e chi scrive un addon per
Blender o uno script per Metashape non installerà mai pandas, lxml, openpyxl e networkx per scrivere due
kilobyte di JSON.

Restano in s3Dgraphy le due funzioni che un grafo ce l'hanno per forza: **emettere** (grafo → timbro) e
**riassorbire** (timbro → grafo). Importano la libreria invece di contenerla, perché due copie di una regola
di formato divergono.

**La risalita non sa dove stanno le cose.** Sa camminare: le si dà un timbro e una funzione «dammi il timbro
(o i byte) per questo digest», e risale un anello alla volta fermandosi a **dire dove non arriva** — «c'era un
genitore con questo id e questo digest, e non ce l'ho» è un risultato, non un errore. Il risolutore lo passa
chi chiama: il filesystem per un plugin Blender, lo store per un server, il grafo per s3Dgraphy, un indice per
un catalogo. Nessuno dei quattro dentro la libreria.

Un formato dichiarato e non implementato è peggio di uno non deciso, perché qualcuno ci costruisce sopra.
