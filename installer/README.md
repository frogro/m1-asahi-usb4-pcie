# Externes Ubuntu Asahi frisch installieren — Testversion

Der Installer bereitet eine **Neuinstallation** auf einem ausgewählten USB-Laufwerk vor. Er klont kein vorhandenes System. Die erste Version unterstützt **Ubuntu Asahi Desktop 26.04 auf Mac mini M1 (J274/T8103)**, gestartet vom ursprünglichen internen Ubuntu Asahi. Fedora Asahi Remix ist noch nicht installierbar; dessen Image-, Paket- und Bootintegration muss separat validiert werden. Asahi Linux ist das übergeordnete Projekt, keine zusätzliche dritte Distribution dieses Installers.

**Status:** Logik-, GRUB-, Image- und DTB-Prüfungen bestanden. Zusätzlich wurde auf dem Mac eine isolierte frische Ubuntu-Image-Datei eingerichtet, mit dem Kernelarchiv ergänzt und eine passende Initramfs erfolgreich erzeugt; siehe [Prüfergebnis](image-validation.json). Eine vollständige Installation mit diesem neuen Installer und ihr erster Hardwarestart stehen aus. Der bisher getestete direkte USB-Bootweg dient als Vorlage, ersetzt diesen Test aber nicht. Keine Garantie für alle USB-Gehäuse, Docks oder andere Apple-Modelle.

## Automatische Build-Auswahl

Installer und interner Updater wählen standardmäßig den **neuesten veröffentlichten,
kompatiblen Gesamtkernel mit erfolgreichem Build**. Es wird keine feste eGPU-Revision
mehr automatisch vorausgesetzt. Der aktuelle angebotene Stand ist unter
[Latest](https://github.com/frogro/m1-asahi-usb4-pcie/releases/latest) sichtbar.

Der Veröffentlichungsworkflow prüft den erfolgreichen Kernel-Lauf auf `main`,
Konfigurationsvergleich, Archivprüfsummen und den Inhalt des Pakets: Kernel,
Module einschließlich AMDGPU, J274-DTB und AVD-Firmware. Erst danach veröffentlicht
er `installer-manifest.json` und das Release. Nur der neueste Build erhält das
GitHub-Label **Latest**; das erneute Veröffentlichen eines älteren Laufs stuft
Latest nicht zurück. Fehlgeschlagene oder unvollständige Builds bleiben Entwürfe.
Ein erfolgreicher Build ersetzt keine Hardwaretests; die Release-Titel benennen
diese Grenze ausdrücklich.

Beide Programme prüfen zusätzlich den zugehörigen GitHub-Actions-Lauf und den
SHA-256-Digest des angebotenen Archivs. Bei Netzfehlern, widersprüchlichen Daten
oder fehlenden kompatiblen Releases wird **vor Änderungen abgebrochen**. Es gibt
keinen stillen Rückfall auf einen eingebauten alten Kernel. Der aktuelle
Installationsvertrag `j274-egpu-v1` umfasst ARM64/J274, die vollständige
`7.2.12-usb4sd4-egpuN`-Serie und die Kernelbasis
`f7734f4c91c0f47d9e762786968057bec99a0788`. Eine andere Basis, Architektur oder
Bootschnittstelle benötigt eine erneute Installer-Anpassung.

Für einen reproduzierbaren Lauf kann ein konkreter freigegebener Build gewählt werden:

```sh
python3 asahi-external-install.py --plan --kernel-tag kernel-build-41155087907-1
python3 update.py --plan --kernel-tag kernel-build-41155087907-1
```

Denselben Schalter bei `--install` beziehungsweise `--prepare` verwenden, um genau
diesen Stand zu installieren. Ohne Pin kann ein späterer Vorbereitungslauf einen
neueren Build auswählen als der vorherige reine Plan. Die ausgewählte Version,
der Commit und die Prüfsumme werden vor der Bestätigung angezeigt und im lokalen
Manifest gespeichert. Innerhalb eines Installationslaufs wird nicht neu aufgelöst.

Das frische Rootfs bleibt das offizielle `ubuntu-desktop-26.04-20260528.zip` mit
festgelegtem SHA-256. Dieser Hash ist keine zusätzliche Herstellersignatur.
Die Initramfs wird für den ausgewählten Kernel auf dem Ziel erzeugt; Module und
DTB stammen aus demselben geprüften Archiv. Mesa und Anwendungen stammen aus dem
Distributionsimage. Das bisherige [Image-Prüfergebnis](image-validation.json)
bezieht sich ausdrücklich auf **egpu2**, nicht automatisch auf spätere Builds.

## Erst nur ansehen

```bash
wget https://raw.githubusercontent.com/frogro/m1-asahi-usb4-pcie/main/installer/install.py -O asahi-external-install.py
python3 asahi-external-install.py --plan
python3 asahi-external-install.py --list-disks
```

Ohne `--install` erfolgt keine Installation. Vor Ausführung mit Administratorrechten den heruntergeladenen Code prüfen; für reproduzierbare Abrufe kann `main` durch einen festen Repository-Commit ersetzt werden.

Die Auswahl zeigt die vom Gehäuse gemeldete Bezeichnung, Größe, Seriennummer und Gerätedatei. Ein Gehäuse, das sich als **MP400** meldet, erscheint als **MP400**, auch wenn darin eine Samsung-SSD steckt. Eingehängte Laufwerke, Swap, interne NVMe, Device-Mapper/RAID, Geräte ohne Seriennummer und Laufwerke unter 32 GiB sind gesperrt. Ein nur über Thunderbolt erreichbares NVMe-Laufwerk ist kein freigegebenes USB-Bootziel.

## Späterer Installationstest

Im **ursprünglichen internen Ubuntu Asahi** starten. Mindestens 6 GiB freier Platz für Downloads, mindestens 32 GiB auf dem externen Ziel. Auf der internen ESP muss zusätzlich Platz für die Boot-Bundle-Sicherung und eine temporäre Schreibdatei vorhanden sein (hier rund 12 MiB). Das Ziellaufwerk direkt am USB-C-Port des Mac betreiben; die bisherigen Tests belegen keinen allgemeinen U-Boot-Start über Dock oder Thunderbolt-Tunnel.

Benötigte Werkzeuge, sofern noch nicht vorhanden:

```bash
sudo apt-get install python3 gdisk dosfstools e2fsprogs util-linux udev rsync zstd kmod device-tree-compiler dracut-core grub-common grub2-common
sudo python3 asahi-external-install.py --install
```

Der Dialog wählt Betriebssystem und Laufwerk, erfragt einen **neuen** Benutzer und ein **neues** Passwort und verlangt vor dem Löschen `ERASE <Seriennummer>`. Erst danach werden GPT, eine 512-MiB-ESP, eine 3-GiB-Bootpartition und die Rootpartition erstellt. Das komplette gewählte Laufwerk wird dabei neu eingerichtet. Keine bestehenden Partitionen werden bewahrt.

Keine Übernahme von Benutzern, Passwörtern, SSH-Schlüsseln, Netzwerkpasswörtern oder persönlichen Dateien. Kopiert werden ausschließlich die lokal vorhandene Gerätefirmware und die originale m1n1-Bootdatei als Rückwegsicherung. AVD-Firmware und Audio-UCM-Ergänzungen kommen aus dem Kernelarchiv. SSH-Zugriff wird nicht vom Host geklont. Es erfolgt kein automatischer Neustart.

## GRUB-Konfiguration und Device Tree

Beispiel des angezeigten Titels:

```text
Ubuntu Asahi 7.2.12-usb4sd4-egpu2 - MP400 (12345678)
```

Der Installer schreibt einen eigenen Generator nach `/etc/grub.d/42_asahi_external_<Root-UUID>`. Er verwendet:

- `search --fs-uuid` für die **neu erzeugte Bootpartition**;
- `Image-<Release>` und `initrd.img-<derselben Release>` auf genau dieser Partition;
- `root=UUID=<neue Root-UUID>`; dieselben UUIDs stehen in der neuen `fstab`;
- die getesteten PCIe-Ressourcenreservierungen, AMDGPU-, Display-/Audio- und begrenzten Fehler-Rückstartparameter;
- einen Aktivierungsmarker für den zum Kernel passenden J274-Device-Tree.

Die genaue Vorlage steht in `grub_entry()` in [install.py](install.py). Modelltexte werden vor Verwendung in GRUB bereinigt. Vor Freigabe werden GRUB-Syntax, die tatsächlich erzeugte Menüdefinition, Kernel-/Initramfs-Hashes, Modulversion und DTB kontrolliert.

**Kernel und Initramfs bleiben ausschließlich extern.** Die vorhandenen m1n1- und U-Boot-Programmteile bleiben unverändert. Für den ersten Test wird nur der eingebettete J274-DTB der internen `m1n1/boot.bin` einmalig gegen den passenden Build-DTB ersetzt. Ein bloßes `devicetree` im GRUB-Menü würde die benötigte m1n1-Vorbereitung nicht ersetzen.

Nach abgeschlossener Vorbereitung zeigt der Installer diese Befehle mit der tatsächlichen UUID:

```bash
sudo asahi-external-boot --check <Root-UUID>
sudo asahi-external-boot --arm <Root-UUID>
# Erst anschließend selbst neu starten.
```

Die originale interne Ubuntu-Auswahl bleibt Standard. Der externe Eintrag ist in dieser Testversion **nur nach `--arm` startfähig**. Nach dem Boot stellt ein früher Initramfs-Hook das Original-Bundle für den nächsten Start wieder her. Ein dauerhaft frei auswählbarer externer Menüeintrag mit zugleich geprüftem internem Rückweg ist ein nachfolgender Integrationstest, keine bereits zugesicherte Funktion.

Zum Abbrechen einer vorbereiteten Auswahl aus dem internen Ubuntu:

```bash
sudo asahi-external-boot --disarm <Root-UUID>
```

Sicherung: `/var/lib/asahi-external/<Root-UUID>/boot-original.bin`, zusätzlich beim Aktivieren `/boot/efi/m1n1/boot-before-external.bin`. Das ist **kein garantierter automatischer Rückweg bei einem Fehler vor dem Start der Initramfs**. Ein fremd geändertes Boot-Bundle wird nicht überschrieben. Bei einem abgebrochenen Installationslauf bleibt das Ziel gegebenenfalls unvollständig; dessen Manifest meldet `incomplete`, und es wird kein startfähiger Menüeintrag freigegeben.

## Prüfungen und noch ausstehende Tests

```bash
python3 -m unittest discover -s installer -p 'test_*.py' -v
python3 installer/install.py --plan
```

Getestet: gesperrte System-/Swap-/USB-Laufwerke, Gerätewechsel, GRUB-Injection-Abwehr, UUID-/Kernel-Zuordnung, GRUB-Syntax, Erhalt von Ubuntus `/lib → /usr/lib`, fest eingebaute gegenüber modularen Treibern, defekte Downloadhashes, Rückwegsbedingungen sowie eindeutiger DTB-Austausch unter Erhalt aller anderen Bundle-Bytes. Das Originalimage wurde separat schreibgeschützt auf leeres Benutzerverzeichnis, fehlende persönliche Benutzer, dracut/Asahi-Firmware-Unterstützung und alte UUIDs untersucht. Der DTB-Austausch wurde zusätzlich mit dem vorhandenen Original-Bundle und dem echten neuen Build-DTB im Speicher geprüft.

Noch offen: vollständiger Installer-Durchlauf auf einem ausdrücklich gewählten freien Medium, neuer Benutzerlogin, automatischer Rückweg, Neustart, Netzwerk, AVD sowie USB4/eGPU/Display und Suspend im so frisch installierten System. Die Firmwareausnahme ist maschinengebunden; das fertige Laufwerk wird nicht als beliebig zwischen Macs austauschbar beworben.

Die Installations-Mounts und chroot-Mounts laufen in einem privaten Mount-Namensraum, damit sie nicht in laufende Desktop-/Dienst-Namensräume gelangen.

## Vorhandenes internes System: zusätzlichen Kernel vorbereiten

[update.py](update.py) ist ein **separater experimenteller Updateweg** für ein bereits installiertes Ubuntu Asahi oder Fedora Asahi Remix. Er ergänzt denselben automatisch ausgewählten Gesamtkernel samt passenden Modulen und DTB, erzeugt die Initramfs mit dem vorhandenen System und fügt einen eigenen GRUB-Eintrag hinzu. Er führt weder eine Neuinstallation noch ein `apt`-/`dnf`-Distributionsupgrade aus. Benutzer, Passwörter, `/home` und Netzwerkeinstellungen werden nicht ersetzt. Die Kontodateien werden vor/nach der Vorbereitung anhand von Hashes verglichen. Die mitgelieferte AVD-Firmware und DCP-Audio-UCM-Dateien werden aktualisiert; vorhandene Exemplare werden gesichert.

**Validierungsstand:** Versionsschutz, Dateisicherung/Rücknahme und GRUB-Logik sind automatisiert geprüft. Am 31. Oktober 2026 wurde der Updateweg aus dem internen Ubuntu 26.04.1 auf einem Mac mini M1 ausgeführt: neuer Kernel von der internen Rootpartition gestartet, SSH und bedienbares Mac-HDMI bestätigt, originale Bootdatei im Initramfs wiederhergestellt, bisheriger Standard erhalten. Dies ist **keine vollständige Funktionsfreigabe**: Der erste PCIe-Tunnel-Host-Probe lief in einen Timeout; nach einem einzelnen manuellen Reprobe wurde die RX 6900 XT sichtbar, ihre PSP-Initialisierung scheiterte anschließend mit `-22`. Die Fedora-Boot-/SELinux-Integration ist weiterhin nicht auf Hardware getestet. Fedora-Neuinstallation bleibt ebenfalls ausgeschlossen.

Voraussetzungen dieser ersten Version: Mac mini M1/J274, direkt eingebundenes internes NVMe-Root mit ext4 oder Btrfs, separates ext4-`/boot`, vorhandenes Asahi-m1n1/GRUB und lokale Gerätefirmware. Verschlüsseltes Root/LVM und andere Partitionierungsvarianten sind noch nicht unterstützt. Benötigt werden Python ab 3.12, dracut/lsinitrd, kmod, zstd, tar, device-tree-compiler und die GRUB-Werkzeuge der jeweiligen Distribution; Fedora benötigt außerdem `restorecon`. Mindestens 3 GiB frei auf Root und Platz für die Boot-Bundle-Sicherung auf der ESP.

Sind mindestens 450 MiB in `/boot` frei, werden die neuen Startdateien dort abgelegt. Andernfalls nutzt der Installer `/var/lib/asahi-kernel-update/<Release>/boot` auf der internen Rootpartition; GRUB erhält deren UUID und den passenden Dateipfad (bei Btrfs einschließlich Subvolume). Die Dateien bleiben vollständig auf der internen SSD. **Alte Kernel und Testdateien in `/boot` werden nicht gelöscht.** Der Plan zeigt den gewählten Speicherort. Der zusätzliche GRUB-Generator wird nach den vorhandenen Generatoren einsortiert, und die bisherige Reihenfolge wird geprüft. Ein leeres `next_entry=` nach einem früheren einmaligen Start ist keine noch ausstehende Bootauswahl.

Beide Skripte in dasselbe Verzeichnis laden und zunächst nur den Plan ansehen:

```bash
mkdir -p asahi-kernel-manager
cd asahi-kernel-manager
wget https://raw.githubusercontent.com/frogro/m1-asahi-usb4-pcie/main/installer/install.py
wget https://raw.githubusercontent.com/frogro/m1-asahi-usb4-pcie/main/installer/update.py
python3 update.py --plan
```

Für den späteren bewussten Installationstest nach Codeprüfung:

```bash
sudo python3 update.py --prepare
# Der Dialog verlangt PREPARE; bis hierhin kein Neustart und keine Boot-Aktivierung.
sudo asahi-kernel-update --arm
# Erst dann selbst neu starten.
# Nach erfolgreichem Start Kernel, Root und Boot-Rückweg prüfen und dokumentieren:
sudo asahi-kernel-update --verify-running
```

Der bisherige Standardkernel bleibt ausgewählt. Menü-Reihenfolge und Standardauswahl werden nach dem GRUB-Neuaufbau überprüft. Der zusätzliche Kernel ist nur nach der einmaligen Aktivierung startfähig; der Initramfs-Hook stellt das originale Boot-Bundle wieder her. Zum Abbrechen vor dem Neustart: `sudo asahi-kernel-update --cancel-boot`. Dies entfernt keine vorbereiteten Kerneldateien und nimmt keine Firmwareaktualisierung zurück. Sicherungen und Manifest liegen unter `/var/lib/asahi-kernel-update/<Release>/`. Die oben beschriebene Grenze des Rückwegs vor dem Initramfs-Start gilt auch hier.

`--verify-running` bestätigt ausschließlich den passenden laufenden Kernel, die Root-/Boot-Zuordnung, unveränderte Startdateien und die wiederhergestellte Bootdatei. Es prüft weder eGPU-Berechnungen noch Hotplug, Displayausgänge oder Suspend und stuft entsprechende Journalfehler nicht als bestanden ein.

Der Abgleich am 31. Oktober mit dem protokollierten erfolgreichen USB-Start und den erhaltenen SanDisk-GRUB-Einträgen ergab identische funktionale Kernelparameter. Ziel-UUID, Dateipfade und Kernelrelease unterscheiden sich erwartungsgemäß; das vorbereitete m1n1-Bundle stimmt per SHA-256 mit der USB-Referenz überein. Die interne Initramfs ist neu erzeugt und nicht identisch mit der damaligen USB-Initramfs samt gerätespezifischen Autorisierungs-/Reprobe-Hooks. Daraus folgt keine Bestätigung identischen PCIe-Initialisierungsverhaltens. GRUB-Syntax und tatsächlich gestartete interne Rootpartition sind geprüft; 10.573 ausgelieferte Dateien wurden ohne Abweichung mit dem festgelegten Releasearchiv verglichen. Der physische SanDisk wurde für diesen Abgleich nicht erneut eingehängt.

### Wenn bereits ein neuerer Kernel installiert ist

Der Installer portiert unsere Patches **nicht automatisch auf diesen neueren Kernel**. Er bietet den geprüften Build `7.2.12-usb4sd4-egpu2` zusätzlich an. Erkennt er eine höhere Linux-Basisversion unter den installierten oder laufenden Kerneln, stoppt `--prepare` vor Änderungen. Nur für einen ausdrücklich gewollten Paralleltest lässt sich das mit `--prepare --allow-older` freigeben; der bisherige Standard bleibt auch dann erhalten.

Eine bereits vorhandene exakt gleichnamige Release wird niemals blind überschrieben. Unterschiedliche Distributions-/Test-Suffixe bei gleicher Linux-Basisversion lassen sich nicht zuverlässig als neuer/älter einordnen; sie bleiben getrennte Builds. Eine neuere Versionsnummer allein beweist weder, dass unsere Funktionen enthalten sind, noch dass ein älterer Testkernel mit sämtlichen inzwischen aktualisierten Benutzerprogrammen kompatibel ist. Eine Portierung auf eine neuere Basis braucht einen eigenen Build und Tests.

## Vorbereitete Updateversionen bleiben fest zugeordnet

`--arm`, `--cancel-boot` und `--verify-running` fragen GitHub nicht ab. Sie verwenden
ausschließlich die gespeicherte Vorbereitung. Bei mehreren Vorbereitungen ist die
Version mit `--release VERSION` anzugeben; `--verify-running` verwendet standardmäßig
die tatsächlich laufende Kernelversion. Beispiel:

```sh
sudo asahi-kernel-update --arm --release 7.2.12-usb4sd4-egpu2
sudo asahi-kernel-update --cancel-boot --release 7.2.12-usb4sd4-egpu2
sudo asahi-kernel-update --verify-running
```

Neue Vorbereitungen bekommen eigene GRUB-IDs, versionierte Rückwegsdateien und
Dracut-Module. Ein Modul wird nur für seine zugehörige Kernelversion eingebunden.
Die bisherige generische Rückwegsversion bleibt erhalten, wird aber aus der neuen
Initramfs ausgeschlossen. Bestehende Kernel und ihre Initramfs werden nicht
überschrieben. Ältere Vorbereitungen ohne Versions-ID bleiben weiterhin über ihren
gespeicherten Stand prüfbar. Der Standardstart wird weiterhin nicht automatisch geändert.
