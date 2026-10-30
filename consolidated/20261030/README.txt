Konsolidierte Apple-M1-TB/USB4-Serie: SSD + Dock-Video, ohne eGPU
Stand: 30.10.2026

ERGEBNIS
26 geordnete RFC-Patches führen die PCIe/NVMe-Arbeit vom 29.10. und die
Dock-Video-Arbeit bis Test128 auf einer gemeinsamen Quellbasis zusammen.
Dies ist die Gesamtserie; die frühere dock-video-patchseries-Ablage war nur
Teil B. Die alten Quellsicherungen wurden nicht überschrieben.

ENTHALTEN
- Apple PCIe-C-Anbindung und die für SSDs getestete Speicherzugriffsreihenfolge.
- DART, MSI, CD321x-Modussteuerung und generische Zuordnung nativer PCIe-Ports.
- Topologieereignisse/Hotplug einschließlich des frühen PCI-OF-Backports.
- PHY/Crossbar, USB4-Display-Tunnel, DCP/DRM und automatischer DP-Wiederaufbau.
- Statischer Mac-mini-M1-Device-Tree für beide PCIe-Ports und den gemessenen
  Dock-Displaypfad. Keine zur Laufzeit erzeugten NHI-Testknoten erforderlich.
- Konfiguration, bisherige Bootparameter, Herkunft und Validierungsprotokolle.

Der reguläre Linux-NVMe-Treiber bleibt unverändert. TB/USB4-Unterstützung ist
Bestandteil der Serie und der benannten UbuntuAsahi-Basis. Es fehlen keine
zusätzlichen SSD-Patches nur deshalb, weil der NVMe-Treiber selbst unverändert ist.

AUSDRÜCKLICH SEPARAT
Keine Änderungen an AMDGPU, TTM, Radeon-Audio oder FFmpeg. eGPU-spezifische
Arbeiten sind ausgeschlossen; allgemeine PCIe-Anbindung bleibt enthalten.
Suspend/Resume bleibt wie vereinbart zurückgestellt, die Sperre bleibt bestehen.
Reset-ACK-Semantik bleibt ein dokumentierter Diagnosepunkt. Die bewährte
Testbedingung ist in config/tested-storage-boot-parameters.txt erhalten.

BASIS UND ANWENDUNG
Ziel: UbuntuAsahi/linux, f7734f4c91c0f47d9e762786968057bec99a0788
Quellpaket: linux-asahi-arm-7.2 7.2.0-1001.1~26.04.1 (Linux 7.2.12).
Der lokale Git-Verlauf enthält eine rekonstruierte, reduzierte Quellpaketbasis,
keine vollständige originale Git-Abstammung. Deshalb ist integration.bundle
für die Offline-Prüfung gedacht, nicht als direkt hochzuladender Fork-Verlauf.

Auf einem sauberen vollständigen Checkout am obigen echten Commit:
    python3 apply-to-checkout.py /pfad/zum/linux-checkout
    python3 apply-to-checkout.py /pfad/zum/linux-checkout --apply

Der erste Aufruf prüft Commit, Ausgangsdateien und Patch-Prüfsummen. Der zweite
legt danach einen lokalen Branch an und wendet die Serie an. Er installiert
nichts und führt keinen Push aus. Ein neuer Fork war zur Vorbereitung nicht nötig.
Die 22-Patch-Basis wurde bereits auf dem vollständigen echten Git-Checkout
angewendet. Alle 26 Patches sind erneut auf derselben Originalbasis angewendet: Ergebnisbaum
und sämtliche Dateiprüfsummen stimmen. Der Gesamtbuild erhält eine eigene Versionskennung.

VERIFIKATION
- Alle 26 Patches frisch angewendet; Ergebnisbaum exakt gleich dem Quellbranch.
- Alle 381 Einträge der breiteren alten Quellsicherung abgeglichen: keine
  unerklärten Abweichungen. Früh enthaltene Korrekturen wurden mit übernommen.
- Kconfig/olddefconfig auf vollständigem Ubuntu-Quellpaket bestanden. Ein in
  der Video-Verpackung eingeführter Abhängigkeitskreis wurde dabei korrigiert.
- Betroffene PCIe-, PCI-OF-, MSI-, DART-, USB4-, Type-C-, PHY-, Crossbar- und
  Apple-DRM-Übersetzungseinheiten mit GCC 15 im selben Quellbaum gebaut.
- Mac-mini-DTB gebaut; 90 SSD-Topologieprüfungen sowie 13 Display-Eigenschaften
  und vier Display-Referenzbeziehungen bestanden.
- git diff --check bestanden. Checkpatch ist noch nicht sauber: vorhandene
  Diagnose-/Stilfragen und fehlende lokale DCO-Signoffs sind offen dokumentiert.

GRENZEN
Noch kein vollständiger vmlinux-Link, kein vollständiges Modulpaket und kein
Hardwareboot dieser konsolidierten Serie. Die früheren SSD- und Displaytests
belegen die Ausgangsstände, nicht schon den gemeinsamen neuen Build.
Wegen der PCI-Strukturänderung müssen später Kernel und Module gemeinsam neu
gebaut werden; einzelne Module nicht mit dem regulären Kernel mischen.
Keine Aussage zu allgemeinem MST/Mehrmonitorbetrieb, allen Apple-Modellen,
unvorbereitetem eGPU-Abziehen oder vollständigem Dock-Suspend.
Die temporäre Buildumgebung benötigte die Beseitigung einer identischen
soc.rs/soc/bus.rs-Dublette des rekonstruierten Quellpakets; dies ist als
Buildumgebungsdetail dokumentiert und kein zusätzlich exportierter Kernelpatch.

HERKUNFT
Originalautoren und vorhandene Trailer der unverändert übernommenen MSI- und
EPIC-Patches sind erhalten. Anpassungen nennen die zugrunde liegenden Arbeiten;
Originalreferenzen stehen unter provenance/. Eigene Signoffs/Reviews wurden
nicht erfunden. Lokale Konsolidierung und Anpassungen sind KI-unterstützt.

NÄCHSTER SCHRITT
Später den vollständigen passenden Kernel samt Modulen bauen und den bereits
vereinbarten kombinierten SSD-/Dock-Video-Regressionslauf durchführen. Die
bestehenden SSD-Funktionen werden dabei kontrolliert, nicht neu entwickelt.
Anschließend Diagnosebezeichnungen, Bindings/Stil und Einreichungsform bereinigen.
Der installierte Kernel, Bootloader und die Verkabelung wurden nicht verändert.
Es wurde kein PR erstellt und nichts veröffentlicht.

AKTUALISIERUNG DP128 / usb4sd2
Die vier ergänzten Patches 23--26 erhalten die alten 22 Patchdateien unverändert:
23: Gemeinsame ATCPHY bleibt beim USB-PIPE-Stopp im USB4/TBT-Modus aktiv.
24: Vollständige Display-Abmeldung vor CIO-Abschaltung, neue Verbindung erst
    nach bestätigter Firmware-/Provider-Freigabe; alle Start-/Stopp-Einstiege
    einschließlich des Storage-Diagnosepfads werden serialisiert.
25: Externer DCP-Audioendpunkt nur für J274 im Device Tree aktiviert.
26: Ergebnis, Aktivierung und Grenzen dokumentiert.

DP127 und DP128: je ein physischer Gesamt-Dock-Zyklus; Bild, OWC-Leseprüfsumme
und Dock-Ethernet zurück. DP128 zusätzlich hörbarer DP-Ton vorher und nachher.
Während des Abziehens lief keine Audiowiedergabe. Die OWC hing am USB-Port;
dies ist kein zusätzlicher PCIe-NVMe-Nachweis. Die vorhandene frühe IOMMU-
Probe-Warnung ist nicht als gelöst deklariert. Vollständiger kombinierter
Kernelboot, Suspend, ACK-Sonderfall und eGPU bleiben außerhalb dieses Ergebnisses.

Audio benötigt weiterhin den bestehenden Parameter appledrm.hdmi_audio=1.
Siehe config/tested-display-audio-options.txt. Keine globale Audio-Vorgabe und
keine eGPU-Treiberänderung. Die Dateien werden nicht automatisch installiert.
Der neue vollständige Build heißt 7.2.12-usb4sd2; usb4sd1 bleibt ein älterer Stand.
