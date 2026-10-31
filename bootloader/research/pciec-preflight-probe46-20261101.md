# Probe46: identify the rejected PCIe-C preflight field

Probe45 returned EINVAL before native PCIe-C initialization. This revision
only adds logging of resource lookup results, validated resource addresses
and sizes, property presence and byte length, and differing tunable triples.
Validation, input tunables, MMIO sequence, timeouts and reset remain unchanged.
No missing or changed property is substituted or accepted silently.

M1 build and patch reconstruction passed. Every other source file matches
the frozen Probe45 manifest. Its 73 sandbox tests, 178-position fault injection,
and ASan/UBSan checks remain prior evidence for the unchanged preparation
logic, not proof of live DT compatibility or successful hardware initialization.

If preflight fails again, initialization remains blocked. If it passes, the
existing bounded Probe45 comparison runs. No external disk is accessed.

## Hardware result

The debug resource address and size matched. The first property
`apple,tunable-debug` was present but contained 24 bytes rather than the
expected 12. The input DT has 12 bytes; the boot-stage handoff changed it.
Preflight rejected the length before new PCIe-C initialization. No link
comparison was performed. Both internal control hashes matched and the
planned reset was observed. See result JSON for recovery verification.

The next run removes the injected input properties and retains every runtime
check. A successful validation would demonstrate that the boot stage supplies
the expected values without manual duplication.
