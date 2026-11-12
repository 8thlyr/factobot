You control a character in a game of Factorio through the `fac` command. Start with `fac --help`.

Your inventory has what you need to start research. Power a lab with steam and research `automation`:

1. Build an offshore pump on the shore of the nearest water, a boiler and a steam engine, connected so the engine runs, and a small electric pole that brings the power to a lab.
2. Fuel the boiler and put the science packs in the lab.
3. Queue `automation` and wait until the lab is working on it.

When the lab is working and research shows progress, answer with one line of JSON: {"lab": [x, y], "research": "<name>", "progress": <number>}.
