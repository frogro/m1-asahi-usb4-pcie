# Upstream submissions

The per-view cursor backport comes from GNOME MR5207, gnome-50 commit
4b852db14f1c8c882fbb7e58499ffe171c094d9d. Do not resubmit it as a new invention.
The following are distinct candidates; the GitHub packaging PR is not a GNOME MR.

## Runtime GPU-add topology notification

After a secondary GPU is registered while Mutter is running, its connector
state is already cached. The next hotplug event can therefore report no change,
leaving the monitor manager unaware of the new GPU. Patch 0001 emits a full KMS
resource change only after successful GPU registration and synchronous renderer/
cursor setup, and excludes headless startup. Mac mini M1 plus Radeon, both direct
and behind Dynabook, reached a working monitor automatically in local tests.

For upstream: rebase onto current GNOME source, verify whether a newer resource
notification already covers this path, and add the equivalent native hotplug
regression to upstream's test infrastructure. Supply patch 0001, not the Debian
packaging or machine logs.

## Connector link-status recovery

A connector can remain physically connected while the kernel reports its link
bad. Patch 0003 tracks that property as a topology change and resets it to Good
only during an active atomic modeset with ALLOW_MODESET. It does not force a
modeset on unrelated property-only commits. Local HDMI reconnect and screen
blank/wake checks pass; full suspend and every short-disconnect race were not
qualified. Upstream issue 4760 is related context, not proof of equivalence.

For upstream: review current atomic property handling and add connector-state
regression cases against that version before submission. Use patch 0003 alone.
No authenticated GNOME GitLab account was available during this integration;
neither of these two upstream MRs is claimed submitted.
