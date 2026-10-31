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
