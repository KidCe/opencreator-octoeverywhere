# OctoEverywhere for OpenCreator

Remote access and cameras for the Creator 5 Pro with OpenCreator.

Independent preview. No official endorsement. Tests cover one printer.

## Install

Use the printer's built-in processor with OpenCreator, hard-float Python 3.11+, and Moonraker.
The printer must have internet access and the `oc-plugin` command.

1. Make sure that the printer is idle.
2. Back up the printer configuration.
3. Connect to the printer through SSH.
4. Run these commands:

```sh
oc-plugin install https://github.com/KidCe/opencreator-octoeverywhere.git --no-restart &&
sh /usr/data/opencreator/plugins/octoeverywhere/install.sh
```

5. Wait for successful setup.
6. Restart Moonraker in Fluidd.
7. Read the log:

```sh
tail -n 80 /usr/data/opencreator/octoeverywhere/logs/octoeverywhere.log
```

8. Open the account link from the log.
9. Connect your OctoEverywhere account.
10. Check remote status and the camera image.

Keep account links and identity files private.

## Update

Use these entries in Fluidd or Mainsail while the printer is idle:

| Entry | Updates |
| --- | --- |
| `octoeverywhere` | Official OctoEverywhere software |
| `oc-plugin-octoeverywhere` | This plugin |

Do not run the official OctoEverywhere installation scripts on this printer.

## Help

- [Setup and recovery](docs/OPERATIONS.md)
- [Test results and limits](VALIDATION.md)

## License and AI assistance

AGPL-3.0-only. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

OpenAI Codex provided substantial implementation, test, and documentation assistance.
