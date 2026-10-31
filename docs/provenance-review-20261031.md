# Herkunftsprüfung vom 31. Oktober 2026

Dies ist eine KI-unterstützte, begrenzte Quellenprüfung, keine Bescheinigung eines lückenlosen Reinraumprozesses und keine Zusage einer Upstream-Annahme.

## Nachweisbarer Stand

- Die Kernelbasis ist öffentlich verfügbarer UbuntuAsahi/Linux-Code mit erhaltener Lizenzierung und festgehaltenem Commit. Dateien unter `drivers/*/apple` sind Linux-Treiber für Apple-Hardware; dieser Pfad bedeutet nicht, dass proprietärer Apple-Treibercode übernommen wurde.
- `docs/bringup.md` beschreibt aus Aufzeichnungen gewonnene Registerbedeutungen und Initialisierungsreihenfolgen. Linux erstellt eigene DMA-Zuordnungen und Puffer; macOS-DMA-Adressen werden nicht wiederverwendet.
- Die konsolidierte PCIe-C-Serie dokumentiert Übernahmen/Anpassungen öffentlicher DjDeveloperr-Patches. Die eGPU-Serie dokumentiert Joshua Warrens linux-aurora PR188, Originalautoren und unveränderte bzw. angepasste Teile.
- Die lokalen m1n1-Notizen dokumentieren das Starten von macOS und die Beobachtung von Hardware-/Firmwarekommunikation. Eine Erwähnung von `kernelcache.macho` als geladenem Gast ist allein kein Nachweis einer Disassemblierung.
- In den geprüften Repository-Dokumenten und 61 lokalen Herkunfts-/Übergabenotizen fand sich kein Beleg für eine Disassemblierung oder Dekompilierung proprietärer Apple-Treiber als Quelle dieser Patches. Eine Stichwortprüfung beweist jedoch nicht, dass dies in keiner früheren Sitzung geschah. Eine vollständige Prüfung sämtlicher Werkzeugaufrufe und der Herkunft aller Fremdpatches ist offen.
- Proprietäre Gerätefirmware wird für die Installation ausschließlich lokal vom vorhandenen Mac verwendet. Sie ist von neu geschriebenem Treibercode zu unterscheiden und wird nicht zusammen mit dem öffentlichen Kernelarchiv verteilt. Die mitgelieferte AVD-Firmware stammt aus dem gesondert dokumentierten Asahi-AVD-Quellprojekt.

## Abgleich mit den Projektregeln

Gravity erlaubt Hardwarebeobachtungen und Register-/Datentracing als Grundlage neuer Implementierungen. Die Regeln verlangen zusätzlich komponentenbezogene Trennung von Personen/Agenten mit Einsicht in proprietäre Implementierungen, nachvollziehbare Aufzeichnungen und offengelegte KI-Nutzung. Bei übernommenem Code anderer Reverse-Engineering-Projekte reicht ein öffentlicher GitHub-Link allein nicht als Nachweis dieses Prozesses.

Die bisherige Dokumentation stützt daher die Aussage **„öffentliche Linux-/Asahi-Quellen plus beobachtete Hardwareschnittstellen“**. Sie reicht nicht für **„alle Gravity-Reinraumbedingungen abschließend nachgewiesen“**. Ein menschlicher Review der Herkunft und des tatsächlichen Codes bleibt nötig; es werden keine menschlichen Reviews oder DCO-Sign-offs erfunden. Neue KI-unterstützte Commits kennzeichnen dies explizit.

Asahis eigene Richtlinie unterscheidet sich: Sie schließt materielle KI-generierte Beiträge aus, einschließlich KI-Auswertung von m1n1-Traces. Ein technisch funktionierender oder bei Gravity möglicherweise zulässiger Patch ist deshalb nicht automatisch bei Asahi einreichbar. Dieses Repository ist ein unabhängiger experimenteller Fork, keine offizielle Asahi- oder Gravity-Veröffentlichung.

## Quellen

- [Golem: Gravity Linux](https://www.golem.de/news/gravity-linux-ki-hilfe-soll-linux-schneller-auf-moderne-apple-cpus-bringen-2609-213482.html)
- [Gravity Reverse Engineering Policy](https://gravitylinux.org/policies/reverse-engineering/)
- [Gravity LLM Use and Clean-Room Policy](https://gravitylinux.org/policies/llm/)
- [Asahi Generative AI Policy](https://asahilinux.org/llm-policy/)
- [Eigene Hardwareherkunft](bringup.md)
- [eGPU-Herkunft](../consolidated/egpu179/PROVENANCE.txt)
