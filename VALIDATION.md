# Test results

## Device tests — 2026-11-03

Tests used one Creator 5 Pro with plugin 0.2.0-rc.1.

| Software | Version |
| --- | --- |
| OpenCreator | `7f7e8cb3d13cf0f24786d7e473aa6a2c23318d48` |
| Python | 3.13.9, MIPS hard-float |
| Moonraker API | 1.5.0 |
| Pillow | 12.3.0 |

| Check | Result |
| --- | --- |
| Unit tests on the printer | All 24 passed. |
| Setup in an empty directory | Installed OctoEverywhere 5.4.1. No account connection test. |
| Repeated setup | Kept the existing runtime. |
| Update from plugin 0.1 | Kept the account and previous runtime. |
| OctoEverywhere update | Updated 5.4.0 to 5.4.1 through Moonraker. |
| Dependency recovery | Passed. The engine started after recovery. |
| Native Pillow import | Passed. |
| Upstream Git checkout | Valid and clean after the update. |
| Cloud connection | Existing account showed Idle and temperature data. |
| Camera | Cloud snapshot passed. Remote Fluidd showed about 7 frames per second. |
| Disable and enable | Stopped the old child process. Started a new process and update entry. |
| Klippy process | PID 1295 stayed unchanged during update and service tests. |
| Configuration and identity | File hashes stayed unchanged. |
| Moonraker | No warnings or failed components after the update. |
| Software reboot | Plugin, updater, and Klippy became ready in 39.8 seconds. |
| Shell syntax | Passed. |

The first activation failed because Moonraker kept the old component in memory.
A full Moonraker process restart loaded the new component.
Later soft restarts passed.

The printer stayed idle during these tests.
No motion, heating, extrusion, or print-start commands were sent.
Private recovery files remain outside the release package.

## Publication checks — 2026-11-15

| Check | Result |
| --- | --- |
| Windows, Python 3.11 | 22 tests passed. Two Linux-only tests skipped. |
| GitHub Linux, Python 3.11 and 3.13 | All 24 tests passed on each version. |
| Public Git clone | Plugin manifest and source hashes passed. |
| Release ZIP | Source hashes and file list passed. |

The first GitHub run found a fixed-path assumption in a test.
The corrected test supplies its own path for `nice`.
Runtime code stayed unchanged.
Publication did not change the printer.

## Tests still required

- New account connection on a second physical printer.
- Physical power removal and restoration.
- Installation from the final public Git URL on a printer.
- Physical printing, motion commands, and failure detection.
- Other printers and OpenCreator variants.
- Future Python, Moonraker, and OctoEverywhere versions.

## Prototype 0.1

Tests on 2026-11-03 covered setup, account transfer, cloud access, cameras, service commands, and software reboot.
All 11 prototype unit tests passed on Windows and the printer.
The later 0.2 tests above are the release evidence.
