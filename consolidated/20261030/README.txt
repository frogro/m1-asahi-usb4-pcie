Konsolidierte Apple-M1-TB/USB4-Serie: SSD, Dock-Video/Audio und Suspend
Stand: 30.10.2026; 29 RFC-Patches; Kernelkennung 7.2.12-usb4sd3

UMFANG
Die bisherigen 26 Patches bleiben bytegleich erhalten. Die Gesamtserie umfasst
Apple PCIe-C, DART/MSI, CD321x, native Portzuordnung und PCIe-Hotplug sowie
PHY/Crossbar, USB4-Display-Tunnel, DCP/DRM, Dock-Hotplug und optionales DCP-Audio.
Der statische Device Tree beschreibt die getestete Mac-mini-M1-J274-Topologie.
Der reguläre Linux-NVMe-Treiber und die Firmware bleiben unverändert.

Drei Ergänzungen schließen daran an:
27: ATCPHY erhält den Strombereich aktiver USB4/TBT-Verbindungen in s2idle.
28: ACIO verwaltet seine Strombereiche automatisch; NHI stoppt Steuer-DMA vor
    DART-Suspend und startet sie nach DART-Resume. Nach geordnetem Abschalten
    wird die Strombereichs-Sperre wieder freigegeben.
29: Beschreibung dieses Verhaltens, der Messungen und der verbleibenden Grenzen.
Es gibt keinen vom Nutzer auszuwählenden Diagnosemodus für diese Entscheidung.
Tieferer Schlaf/Ruhezustand mit aktiver Verbindung und Wiederherstellung nach
vollständigem Controller-Stromverlust sind weiterhin nicht implementiert.

AUSGESCHLOSSEN
Keine experimentellen AMDGPU-, TTM-, Radeon-Audio-, UART- oder Watchdog-Patches.
Keine neue Reset-ACK-Fehlerklassifikation oder Unterdrückung von ACK-Fehlern.
Die bestehenden gemessenen Storage-Bootparameter bleiben in config/ erhalten.
DCP-Audio bleibt über appledrm.hdmi_audio=1 optional aktivierbar.

BASIS UND ANWENDUNG
UbuntuAsahi/linux f7734f4c91c0f47d9e762786968057bec99a0788 (Linux 7.2.12).
Auf einem sauberen vollständigen Checkout dieses Commits:
    python3 apply-to-checkout.py /pfad/zum/linux-checkout
    python3 apply-to-checkout.py /pfad/zum/linux-checkout --apply
Commit, Ausgangsdateien, Patchdateien und Enddateien werden geprüft. Der zweite
Aufruf erzeugt einen Branch und wendet die 29 Patches an, ohne Installation.
series ist die maßgebliche Liste; series-with-suspend enthält dieselbe Liste.
suspend-followup/ bewahrt die drei ursprünglichen Ergänzungen samt Evidenz.
Die ältere Quellpaket-Rekonstruktion in base-provenance.json ist historische
Herkunftsdokumentation; nicht als originale Git-Abstammung hochladen. Die neue
Gesamtprüfung verwendet den echten UbuntuAsahi-Git-Commit.

VALIDIERUNG
Die frische Anwendung aller 29 Patches auf dem Originalcommit, der Vergleich
mit dem vorbereiteten Quellbaum und die Prüfung der Ausgangs-/Enddateien sind
in validation/usb4sd3-replay.json und usb4sd3-full-replay.log dokumentiert.
Die neuen Änderungen betreffen drei C-Dateien und eine Dokumentationsdatei;
Kconfig, Device Tree, NVMe, AMDGPU und TTM bleiben gegenüber usb4sd2 unverändert.
Betroffene Übersetzungseinheiten wurden kompiliert. Die vorherige 26er-Serie
bestand Konfigurations-, Compile-, DT- und Topologieprüfungen sowie den vollen
GitHub-Kernel-/Modulbau. Dessen Job scheiterte erst am Upload einer leeren
Diagnosedatei; dafür liegt im Workflow eine Korrektur vor.

Test154: spätes/noirq-PM-Probelaufen erfolgreich.
Test155: echter s2idle, Aufwecken per Taste, HDMI und drei Leseprüfsummen korrekt.
Test156: ACIO-Ab-/Anmeldung gibt Strombereich frei; SSD und Prüfsummen zurück.
Test157: echter s2idle mit normalem parallelem Geräte-PM, HDMI/Prüfsummen korrekt.
Jeweils Yottamaster-NVMe 1 GiB, OWC über USB/UAS 1 GiB, SD 64 MiB; ausgehängt/RO.
Diese Läufe nutzten passende Diagnosemodule mit derselben neuen PM-Logik. Sie
ersetzen nicht den noch ausstehenden Hardwareboot des gesamten 29er-Kernels.
Der bekannte DCP-PMU-Diagnoseeintrag bleibt dokumentiert. Details und Grenzen
stehen in suspend-followup/README.txt; der Gesamtjournalstand wird nicht als
vollständig fehlerfrei bezeichnet.

BUILD UND OFFENE PRÜFUNGEN
GitHub baut Image, alle konfigurierten Module und DTBs unter usb4sd3 neu. Die
Konfigurationsprüfung bricht bei Verlust bestehender Ubuntu-Funktionen ab.
Es gibt keinen gespeicherten Objekt-/Compiler-Cache; daher kein inkrementeller
Compilelauf. Ergebnisse landen in einem privaten Release-Entwurf. Keine
Installation, kein Eingriff in Bootloader, installierte Module oder Firmware.
Der usb4sd2-Stand bleibt in Git und im bisherigen Release erhalten.

Nach dem Bau folgen gemeinsamer Hardwareboot und Regression: SSDs, Dock-
Video/Audio, Hotplug und Suspend/Resume. Schlaf mit aktiver Dock-Bildausgabe,
nativer USB4-NVMe, Gerätewechsel im Schlaf, Schreiben nach Resume und
Leistungsaufnahme benötigen weitere Messungen. Allgemeiner MST-/Mehrmonitor-
Betrieb, andere Apple-Modelle und eGPU sind durch diese Tests nicht abgedeckt.
Bindings/Stil, Diagnosebezeichnungen und DCO/Einreichungsform sind weiterhin
Reviewarbeit; diese Ablage ist kein upstream akzeptierter Patchsatz.

HERKUNFT
Originalautoren und vorhandene Trailer übernommener Patches sind erhalten;
Referenzen stehen unter provenance/. Eigene Signoffs/Reviews werden nicht
erfunden. Lokale Anpassungen und Konsolidierung sind KI-unterstützt.
