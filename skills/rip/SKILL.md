---
name: rip
description: Digitalisiert eine eingelegte DVD Jellyfin-ready. Scannt die Disc, waehlt intelligent den echten Hauptfilm (keine Decoys), rippt EN+DE Ton + Untertitel verlustfrei mit MakeMKV, komprimiert mit HandBrake (H.264 RF19, Decomb) und legt sie sauber benannt als "Titel (Jahr)/Titel (Jahr).mkv" ab. Nutze bei "/rip", "DVD digitalisieren", "DVD rippen".
---

# DVD Rip → Jellyfin

Automatisierter Workflow, um eine eingelegte DVD in eine komprimierte, Jellyfin-taugliche MKV zu verwandeln.

## Werkzeuge (feste Pfade)

- Scan:       `P:\File Archive\Medien\Filme\DVDs\DVDAgent\scripts\scan-disc.ps1`
- Rip:        `P:\File Archive\Medien\Filme\DVDs\DVDAgent\scripts\rip-title.ps1`
- Recovery:   `P:\File Archive\Medien\Filme\DVDs\DVDAgent\scripts\recover-disc.ps1` (nur bei beschaedigter Disc, siehe Schritt 4)
- Komprimieren:`P:\File Archive\Medien\Filme\DVDs\DVDAgent\scripts\compress.ps1`
- Temp-Ordner: `P:\File Archive\Medien\Filme\DVDs\DVDAgent\temp`
- Zielbasis:   `P:\File Archive\Medien\Filme\MOVIES`

Alle Skripte per `powershell -ExecutionPolicy Bypass -File "<pfad>" ...` aufrufen.

## Ablauf (strikt in dieser Reihenfolge)

### 1. Disc scannen
`scan-disc.ps1` ausfuehren (dauert ~1 Min, laeuft am besten im Hintergrund). Ergebnis ist JSON:
`{ disc:{label}, titles:[ {id, duration, seconds, chapters, sizeGB, audio:[], subs:[]} ] }`
Titel sind nach Laenge absteigend sortiert.

### 2. Hauptfilm bewerten (NICHT blind den laengsten nehmen)
Analysiere die Titelliste selbst und begruende kurz:
- **Decoys aussortieren:** Titel mit ungewoehnlich vielen Kapiteln (z.B. 99) sind fast immer Kopierschutz-Fakes.
- **Duplikate erkennen:** Mehrere Titel mit nahezu identischer Laenge/Groesse → nimm den mit den vollstaendigsten/passenden Tonspuren (EN+DE bevorzugt).
- **Plausibilitaet:** Ein Spielfilm hat i.d.R. 70–210 Min. Sehr kurze Titel = Extras/Trailer.
- **Sprachen:** Bevorzuge den Kandidaten, der die gewuenschten Tonspuren (Englisch + Deutsch) enthaelt.
Sag dem User in 1–2 Saetzen, welchen Titel (id, Laenge, Tonspuren) du nimmst und warum. Bei echter Uneindeutigkeit kurz nachfragen, sonst weiter.

### 3. Film identifizieren (Online-Lookup)
Nutze WebSearch mit dem Disc-Label (`disc.label`) und ggf. der Laufzeit, um Titel + Erscheinungsjahr zu bestimmen.
Schlage dem User `Titel (Jahr)` vor und lass es in einem Satz bestaetigen/korrigieren.
Bereinige den Namen fuer das Dateisystem (keine `\ / : * ? " < > |`).

### 4. Rippen
`rip-title.ps1 -TitleId <id> -OutDir "<Temp>\rip_<safeLabel>"` aufrufen (Hintergrund).
**IMMER einen EIGENEN Temp-Unterordner pro Film** (`rip_<safeLabel>`, z.B. `rip_the_predator`) —
NICHT den gemeinsamen `rip`-Ordner. Sonst loescht ein neuer Rip die MKV einer noch laufenden Kompression.
Letzte Ausgabezeile = Pfad der erzeugten MKV. Bei `ERROR:` abbrechen und melden.

**Wichtig — Fast-Path zuerst, Recovery nur bei Bedarf (spart bei leicht zerkratzten Discs Stunden):**
Der direkte Rip oben IST der Schnell-Check. Leichte Kratzer steckt MakeMKV weg und rippt in ~15 Min
durch. Waehrend er laeuft, einen Waechter setzen, der bei Lesefehlern SOFORT abbricht statt zu haengen:
  Bash (run_in_background):
  `until grep -qiE "read error|L-EC UNCORRECTABLE|TIMEOUT ON LOGICAL|TRAY OPEN|Failed to save|Copy complete|titles saved" "<rip-logfile>"; do sleep 3; done` + danach die Trefferzeile ausgeben.
  → "Copy complete/titles saved" = sauber durch (weiter Schritt 5). → Fehler-Signatur = Rip killen (TaskStop) und Recovery starten.

**Fallback bei beschaedigter Disc** (Waechter meldet `Read Error`/`L-EC UNCORRECTABLE`/`TIMEOUT ON
LOGICAL UNIT`/`TRAY OPEN`/`Failed to save`): Das Laufwerk kommt ueber physische Defekte nicht hinweg.
Disc mit dvdisaster in ein vollstaendiges ISO retten und daraus rippen:
1. `recover-disc.ps1 -Image "<Temp>\<label>.iso" -Drive D:` (Hintergrund). **Default ist -Fast**
   (1 Versuch/Sektor, grosse Spruenge) — deutlich schneller als gruendlich. Bei sehr wichtigem Film
   und vielen Ausfaellen `-Thorough` fuer maximale Rettung nachlegen (Resume: liest nur Fehlendes nach).
   Nutzt lineares Lesen + `--ignore-fatal-sense`, ueberspringt Defekte und fuellt mit 0.
   Auch mit -Fast kann es bei vielen Defektsektoren dauern (jeder Timeout kostet Sekunden) — normal.
   Endzeile `OK image=<GB>` und ISO-Groesse == volle Discgroesse (Sektoren*2048) = fertig.
2. Dann aus dem ISO rippen (kein zickiges Laufwerk mehr, schnell, keine Lesefehler):
   `makemkvcon64.exe -r --cache=1 --noscan mkv "iso:<Temp>\<label>.iso" <TitleId> "<Temp>\rip"`
   MakeMKV oeffnet das ISO direkt (`iso:`-Quelle) und entschluesselt CSS wie bei einer echten Disc.
   Die Titel-Nummerierung entspricht der des physischen Scans (Titel wie in Schritt 2 gewaehlt).
3. Weiter mit Schritt 5. Dem User die Anzahl null-gefuellter Sektoren nennen (grobe Glitch-Menge).

### 5. Komprimieren
Zielordner `"<Zielbasis>\<Titel (Jahr)>"` bilden.
`compress.ps1 -InFile "<gerippte.mkv>" -OutFile "<Zielordner>\<Titel (Jahr)>.mkv"` aufrufen
(Hintergrund, kann je nach Laenge 20–60 Min dauern). Ausgabe `OK <MB>` = Erfolg.

### 6. Aufraeumen & melden
Nach Erfolg NUR den film-eigenen Temp-Unterordner (`rip_<safeLabel>`) loeschen (nicht andere, die
evtl. noch fuer eine parallele Kompression gebraucht werden). Endpfad + Groesse nennen; bei Recovery
an Glitch-Sichtpruefung erinnern.

## Pipeline-Modus (Rip parallel zur Kompression)
Rippen ist laufwerks-/IO-gebunden, Komprimieren CPU-gebunden -> sie ueberlappen ohne nennenswerten
Konflikt. Ablauf fuer maximalen Durchsatz bei mehreren Discs:
- Sobald ein Rip fertig ist: Kompression im Hintergrund starten UND dem User sofort "Disc raus,
  naechste rein" sagen. Nicht auf die Kompression warten.
- **Nur EINE Kompression gleichzeitig** (zwei HandBrakes teilen sich nur die CPU = kein Gewinn).
  Wird ein weiterer Rip fertig, waehrend noch eine Kompression laeuft: dessen MKV im eigenen
  `rip_<safeLabel>`-Ordner liegen lassen und die Kompression erst starten, wenn die laufende fertig
  ist (Kompressions-Queue). Rips duerfen jederzeit parallel zur laufenden Kompression laufen.
- Jeder Film hat seinen eigenen `rip_<safeLabel>`-Ordner -> keine Kollision. Nach erfolgreicher
  Kompression den jeweiligen Ordner loeschen.
- Effektiver Durchsatz wird so von der Kompression begrenzt (Rip verschwindet dahinter).

## Standard-Einstellungen (bereits in den Skripten)
- Video: H.264 (x264), RF 19, Preset "slow", Decomb (gegen DVD-Interlacing)
- Audio: Original-AC3 EN+DE durchgereicht (kein Requalitaetsverlust), Fallback AAC
- Untertitel: EN+DE (VobSub) in die MKV gemuxt
- Container: MKV

## Hinweise
- MakeMKV BETA muss registriert sein (GUI: Help → Register); der CLI nutzt denselben Key.
- Nur DVDs. Blu-ray/UHD ist bewusst nicht abgedeckt.
- Bei mehreren Laufwerken hat `disc:0` Vorrang; ggf. `-DiscNr` anpassen.
