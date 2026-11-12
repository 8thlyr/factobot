# factobot (Python)

Python client for the factobot daemon, the test-world harness (`factobot.harness`) and the playtest runner (`python -m factobot.playtest`), which runs any agent harness against a world in a sandbox. The Inspect AI tasks and scorer (`factobot.tasks`) are here too, shelved but kept with their tests (decision 46). `python -m factobot.report` writes a markdown and HTML leaderboard from run outputs.

```python
from factobot import Client

with Client() as client:  # FACTOBOT_SOCKET, or the default runtime-dir socket
    print(client.status()["game"]["tick"])
```

The wire protocol is specified in [`docs/protocol.md`](../docs/protocol.md).
