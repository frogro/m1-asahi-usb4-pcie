# Startablauf und Befehle im untersuchten M1-U-Boot

Stand: 1. November 2026. Untersucht wurden der tatsächlich gebaute Quellstand
auf Basis b33034a515a068381c4aa28831fb709e91300cd1 mit unseren Änderungen,
die eingefrorenen Konfigurationen von Probe49/50 und deren UART-Protokolle.
Das ist eine Analyse dieser RAM-Testumgebung; die Konfiguration jedes anderen
installierten U-Boot-Binaries ist damit nicht automatisch belegt. Kein neuer
Hardwaretest und keine Änderung an installierten Startdateien wurden ausgeführt.

## 1. Tatsächliche Reihenfolge

1. **Apple-Start und m1n1.** Im aufgezeichneten m1n1-Lauf erfolgen bereits
   Stromzustandsbereinigung und ein Versuch der Displayinitialisierung. Der
   DCP-HELLO-Timeout liegt vor U-Boot. Die internen Sonoma-Test-Startoptionen
   sind nicht gleichbedeutend mit einem extern gestarteten macOS. m1n1-Quellcode
   wurde für diese Analyse weder gelesen noch geändert; diese Aussagen stammen
   aus dem vorhandenen Laufprotokoll.
2. **U-Boot-Bindung und automatische Geräteinitialisierung.** Der Device Tree
   wird ausgewertet; deaktivierte Knoten werden regulär nicht gebunden.
   Gerätebindung allein ist von `device_probe()` zu unterscheiden: Probing
   kann Eltern, Strombereiche, Pinsteuerung und Hardware initialisieren.
3. **Watchdog und frühe EFI-Grundstruktur.** Der Watchdog startet mit 60 Sekunden
   und zyklischer Bedienung. Die frühe EFI-Initialisierung registriert zunächst
   Grundobjekte; sie ist noch kein vollständiger EFI-Bootmanager-Lauf.
4. **Umgebung laden.** `CONFIG_ENV_IS_NOWHERE=y`: die U-Boot-Umgebung kommt aus
   dem Build. `setenv` wirkt zunächst im RAM; `saveenv` hat hier keinen
   konfigurierten persistenten Speicher. EFI-Variablen sind davon getrennt.
5. **PCIe initialisieren.** `CONFIG_PCI_INIT_R=y` führt `pci_init()` schon vor
   Konsoleneinrichtung und `preboot` aus. Bekannte PCI-Controller werden dabei
   geprobt, Links eingerichtet und Geräte enumeriert. Dies betrifft nicht
   automatisch einen Thunderbolt-Tunnel.
6. **Ein-/Ausgabegeräte.** `stdio_add_devices()` kann bei `CONFIG_DM_KEYBOARD=y`
   gebundene Tastaturgeräte unabhängig vom `stdin`-Text proben. Die normale
   Umgebung verwendet `serial,usbkbd,spikbid,mtpkbd` und `vidconsole,serial`.
   Probe50 wählt nur `serial`. Das verhindert nicht pauschal jede andere frühe
   Geräteinitialisierung. Der Videopfad hängt zusätzlich an
   `CONFIG_SYS_CONSOLE_IS_IN_ENV`; Splash ist hier deaktiviert.
7. **Interne Asahi-ESP suchen.** `board_late_init()` ruft `asahi_esp_devpart()`
   auf. Diese Funktion führt bereits `nvme_scan_namespace()` aus und liest
   Partitionstabellen. Für die Wahl der Firmware-ESP berücksichtigt sie nur
   `apple,nvme-ans2`, also den internen Apple-NVMe-Controller. Vorrang hat die
   übergebene ESP-PARTUUID, sonst die erste passende ESP. Das verhindert nicht
   grundsätzlich das spätere Laden eines EFI-Programms von USB, bedeutet aber:
   unser erster expliziter `nvme scan` ist nicht der erste NVMe-Zugriff.
8. **`preboot`.** Im ursprünglichen Testbuild: `usb start`. In Probe50: leer.
   Das läuft vor dem Autoboot-Countdown und vor dem Device-Tree-`bootcmd`.
9. **Countdown und eigentlicher Startbefehl.** Build-Vorgabe:
   `bootflow scan -b`. `/config/bootdelay` im Device Tree hat Vorrang vor der
   Umgebungs-/Buildvorgabe; `/config/bootcmd` kann anschließend den ausgewählten
   Startbefehl ersetzen. Probe49/50 verwenden dort ihre eigenen Testskripte.
   Nur `printenv bootcmd` anzusehen genügt deshalb nicht.
10. **Bootsuche und Übergabe.** Im normalen Ablauf suchen Bootmethoden nach
    EFI, Extlinux oder Skripten. EFI lädt beispielsweise
    `/EFI/BOOT/BOOTAA64.EFI`; das kann GRUB sein. Erst danach folgt dessen
    Menü. Unsere Diagnose-`bootcmd` führt dagegen Messungen und `reset` aus.

## 2. Bedeutungen der relevanten Befehle und Einstellungen

| Befehl / Einstellung | Tatsächliche Wirkung und Grenze |
|---|---|
| `usb start` | Startet bekannte USB-Hostcontroller, enumeriert Hubs/Geräte und sucht Massenspeicher. Bei bereits gestarteter USB-Schicht kein erneuter Scan. Kein USB4-/TB-Verbindungsmanager. |
| `usb reset` | Stoppt USB und startet es erneut. Betrifft die registrierten USB-Busse, nicht gezielt nur das OWC-Gehäuse. |
| `usb stop` | Entfernt USB-Geräte/Hostcontroller und setzt den Suchzustand zurück; kann Tastatur und andere USB-Geräte verlieren. Kein allgemeiner Thunderbolt-Reset. |
| `usb tree`, `usb info`, `usb storage` | Zeigen den USB-Zustand bzw. Geräteinformationen nach Initialisierung. Eine Anzeige ist kein Nachweis eines PCIe-Tunnels. Informationsabfragen können USB-Transfers enthalten. |
| `pci enum` | Ruft `pci_init()` auf und probt bekannte Controller. Baut keinen USB4-Tunnel. Bereits aktive Geräte werden durch erneutes `device_probe()` gewöhnlich nicht erneut initialisiert. Kein garantierter vollständiger Hotplug-Rescan. |
| `nvme scan` | Probt bereits bekannte NVMe-Controller und deren Namespaces. Es entdeckt keine SSD hinter einem noch nicht aufgebauten TB-Tunnel. |
| `nvme info`, `nvme part`, `load nvme ...` | Geräteanzeige, Partitionstabellen bzw. Dateilesen. Benötigen einen erreichbaren NVMe-Pfad. Erfolgreiches Lesen der internen SSD beweist keinen externen TB-Zugriff. |
| `boot_targets` | Reihenfolge der Mediensuche; normal `nvme usb`, Probe50 `nvme`. Dies ist kein PHY-Modus und kein USB4-Schalter. Leere Ziele sind nicht gleichbedeutend mit ausgeschalteter Suche. |
| `bootflow scan` | Sucht Startmöglichkeiten und aktiviert standardmäßig die dafür vorgesehenen Geräte-Suchfunktionen. Ohne `-b` wird nicht automatisch gebootet, Hardwareinitialisierung und Dateilesen sind trotzdem möglich. |
| `bootflow scan -b` | Sucht und versucht zu booten. Die NVMe-Suche ruft PCI-Initialisierung und NVMe-Scan auf; die USB-Suche kann `usb_init()` aufrufen, obwohl `preboot` leer ist. |
| `bootflow scan -H` / `-G` | In diesem Build implementiert: `-H` unterdrückt die speziellen Geräte-Suchfunktionen, `-G` globale Bootmethoden. Beides zusammen garantiert keine völlig passive Messung: vorhandene Geräte und Partitionen können weiter geprobt/gelesen werden. |
| `bootmeths` / `bootmeth order` | Wählt Bootmethoden wie EFI oder Extlinux. Ersetzt keine fehlende Transport-/Tunnelinitialisierung. |
| `bootefi`, EFI-Bootmanager | Übergabe an ein geladenes EFI-Programm bzw. Auswahl durch EFI-Variablen. Die vollständige EFI-Initialisierung probt Blockgeräte und lädt Variablen. Kein Apple-TB-Treiber wird dadurch bereitgestellt. |
| `booti`, `bootm` | Starten bereits verfügbare Kernel-/Bootimages. Lösen die fehlende Erreichbarkeit des Datenträgers nicht. |
| `bootmenu` | Stellt eine Menüauswahl dar; die Einträge führen die hinterlegten Befehle aus. Es ist weder Apples Power-Tasten-Auswahl noch GRUB. |
| `reset` | Neustart des Systems. Der Test verwendet ihn nach Abschluss ausdrücklich; er ist kein USB-Reset. |
| `atcm1 1 usb4pciec` | Unser expliziter, auf J274-Port1 begrenzter RAM-Diagnosepfad: PHY, ACIO, NHI-Kontrollverkehr, PCIe-C-Vorbereitung und Linkversuch. Kein fertiger generischer SSD-Bootpfad. |
| `usb4 start` | In diesem Build nicht vorhanden. |

Die regulären USB-/NVMe-/PCI-Befehle und unsere `atcm1`-Tests sind getrennte
Pfade. Die Diagnosemodi werden nicht automatisch von `bootflow` aufgerufen.
Ein bloßes Umbenennen von `usb start` oder Ergänzen von `usb4` zu
`boot_targets` würde diese Lücke nicht schließen.

## 3. Konkrete Auswirkungen von `usb start`

Der an `apple,t8103-dwc3` gebundene Treiber führt `dwc3_core_init()` aus.
Darin werden DWC3-Core-Reset sowie USB2-/USB3-PHY-Softreset gesetzt und wieder
freigegeben, mit zwei Warteabschnitten von je 100 ms. Anschließend werden
Betriebsart und xHCI eingerichtet. Das verändert Register und zeitliche
Abläufe, auch wenn PMGR vor/nachher dieselben aktiven Stromzustände meldet.

Der normale Apple-ATC-Wrapper besitzt hier leere PHY-Operationen und keine
Reset-assert/deassert-Operationen. Der bloße Aufruf generischer
PHY-/Reset-APIs bedeutet deshalb nicht, dass dieser Wrapper die vollständige
Apple-USB4-PHY-Initialisierung erledigt. Die generischen DWC3-Softresets finden
aber statt. Unser späterer Diagnosepfad verwendet bereits
`dwc3_m1_diag_init_preserve_phy()`; der frühe normale USB-Start verwendet diese
Ausnahme nicht.

Auch PCI-xHCI wird gestartet, einschließlich Bus-Master-Freigabe. Ein globales
`usb start` bedeutet daher mehr als eine USB-C-Buchse. Der Probe50-UART zeigt
`usb@502280000` und `xhci_pci`. Er zeigt keinen Start des Debug-Port0 als
U-Boot-USB-Host; das übergebene Laufzeit-DT ist dabei maßgeblich, nicht allein
das vorbereitete Eingabe-DT vor m1n1.

Massenspeichererkennung kann SCSI-Anfragen, Kapazitätsabfragen und durch das
Blockgeräte-Probing auch Partitionstabellen-Lesen auslösen. »Kein expliziter
Sektorlesebefehl« darf nicht pauschal mit »kein Datenträgerzugriff« gleichgesetzt
werden. Probe50 fand konkret null USB-Massenspeicher.

## 4. Fehlerauswertung und Persistenz

`do_usb_start()` gibt keinen Status zurück, und der CLI-Zweig für `usb start`
gibt danach 0 zurück. Deshalb ist `if usb start; then echo PASS; fi` allein
kein belastbarer Erfolgsnachweis. Entsprechendes gilt für die CLI-Zweige
`usb reset`/`usb stop`; `pci_init()` liefert ebenfalls keinen aggregierten
Fehlerstatus aller Controller. Künftige Tests müssen zusätzlich tatsächliche
Treiberzustände, Protokollfehler und erwartete Geräte prüfen.

Bei Probe50 bestätigen zwei Controlleranzeigen, vollständige Schnappschüsse
und Kontrollhashes den beobachteten Ablauf. Das Shell-PASS ist nur Zusatztext.

Die nicht persistente U-Boot-Umgebung ist von EFI-Variablen zu unterscheiden:
`CONFIG_EFI_VARIABLE_FILE_STORE=y` erlaubt deren Ablage in `ubootefi.var` auf
einer EFI-Systempartition. Vollständige EFI-/Bootmanager-Aufrufe können diese
Schicht nutzen; `ENV_IS_NOWHERE` ist kein globales Schreibverbot.

Der 60-s-Watchdog wird zyklisch bedient. Er ist kein garantiertes absolutes
Zeitlimit für einen Test, der weiterhin die Ereignisschleife bedient.
`CONFIG_BOOTCOUNT_LIMIT` und `CONFIG_BOOT_RETRY` sind aus. Unser planmäßiger
`reset` und der Host-Timeout sind davon getrennt; ein Host-Timeout allein
startet den Mac nicht neu.

## 5. Was Probe50 beweist und welche Prüfung folgt

Vor und nach dem expliziten USB-Start waren PCIe/CIO/CIO-PCIe/CIO-USB von Port1
ausgeschaltet. Nur historische PMGR-Gatingflags änderten sich. Damit ist in
diesem Lauf kein Abschalten eines aktiven geerbten Tunnels durch USB-Start
belegt. Unveränderte PMGR-Zustände schließen jedoch die oben beschriebenen
DWC3-/PHY-Resetwirkungen nicht aus. Die Aussage »USB-Start ist als Ursache
vollständig ausgeschlossen« wäre falsch.

Ein gezielter nächster Vergleich muss den normalen frühen DWC3-Start von
unserer anschließenden Neuinitialisierung trennen. Dazu sind vor/nach diesen
Schritten Messpunkte mit geprüftem Strom-/Resetstatus nötig. Der aktuelle
`atcm1`-Pfad verlangt noch einen bereits aktiven USB-Controller und meldet ihn
anschließend ab; `usb start` einfach wegzulassen führt deshalb zum Abbruch,
nicht zu einer sauberen Vergleichsprobe. Ein Einstieg ohne vorausgehendes
USB-Probing muss erst explizit implementiert und softwareseitig geprüft
werden. Das ist ein Ansatz, noch kein nachgewiesener Fix.

Zusätzlich sollten automatische PCI-/NVMe-Aufrufe als eigene Messphasen
sichtbar werden, ohne den internen Startpfad oder den Debug-Port blind zu
entfernen. Keine unveränderte Wiederholung von Probe50 ist nötig.

Für einen späteren regulären Start ist die Abhängigkeit dagegen klar:
Type-C/PHY → ACIO/NHI → Link/Router → PCIe-Tunnel → PCIe-Erkennung → NVMe →
Dateisystem/EFI/GRUB. Die Wahl zwischen internem NVMe, USB3 und USB4/TB kann
erst auf dieser Grundlage zuverlässig automatisch erfolgen.

Die Quellen, Konfigurationen und Protokolle sind durch SHA-256 im zugehörigen
Manifest festgehalten; eine dynamische Aufzeichnung jedes frühen Funktions-
aufrufs war nicht Bestandteil dieser Quellcodeanalyse.
