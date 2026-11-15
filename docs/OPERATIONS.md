# Setup and recovery

Use all installation and service commands while the printer is idle.

The reviewed OpenCreator plugin updater can also restart Klipper.
The separate OctoEverywhere updater requests only a Moonraker restart.

## Setup

The installer downloads official OctoEverywhere source and Python packages.
It uses a separate Python environment.
It keeps OpenCreator's native Pillow package.
It does not restart services.

Setup requires the same Python base as Moonraker.
It rejects printing, paused, unknown, and unavailable printer states.

Use `GET /server/octoeverywhere` to check the process and update status.
Then check the connection and camera through your OctoEverywhere account.
A running process alone does not confirm a cloud connection.

If the account link is absent, check the log for network, DNS, and TLS errors.

## Update from version 0.1

1. Install the new plugin.
2. Run `install.sh`.
3. Reboot the idle printer once.

The reboot replaces the old Moonraker component in memory.
Setup keeps the existing account, configuration, and previous Python environment.

## Transfer an existing identity

Use this option only for the same printer and account.
The destination must be a new, empty runtime directory.

```sh
sh /usr/data/opencreator/plugins/octoeverywhere/install.sh \
  --migrate-from /path/to/previous-runtime
```

Setup copies only the identity file.

## Custom setup

Use `install.sh --help` to see the options.

| Option | Function |
| --- | --- |
| `--moonraker-url` | Select a loopback HTTP address. |
| `--frontend-port` | Select the local web interface port. |
| `--runtime` | Select a separate runtime directory. |
| `--rebuild` | Make a new Python environment. |

For a custom runtime, also set `runtime_directory` in a later, user-owned Moonraker include.
Do not edit generated plugin configuration.
The `oc-plugin sync` command replaces it.

For a local source folder, use:

```sh
oc-plugin install /path/to/plugin --no-restart
```

Then run the setup script.
Local copies have no plugin update entry.
OctoEverywhere updates remain available.

## Disable or remove

Use one of these commands:

```sh
oc-plugin disable octoeverywhere
oc-plugin enable octoeverywhere
oc-plugin remove octoeverywhere
```

On Moonraker restart, the disabled plugin stops its child process and removes its OctoEverywhere update entry.
Account files remain in `/usr/data/opencreator/octoeverywhere`.

## Recover

For a failed software update, use Moonraker recovery while the printer is idle.
Then check remote status and the camera.

Git rollback does not restore Python packages.
For Python or native-library changes, use `install.sh --rebuild` when compatible packages are available.

To restore a previous runtime manifest:

1. Stop Moonraker.
2. Restore the required `runtime-before-setup-*.json` as `runtime.json`.
3. Start Moonraker.
4. Check remote status and the camera.

Keep previous runtime directories until all checks pass.

## Security

Use a trusted private network.
The plugin uses Moonraker's access policy.
It adds no public port.

The runtime directory uses mode 700.
Setup-created private files use mode 600.
Logs have size limits.
