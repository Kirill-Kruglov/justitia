# Justitia explorable

Static browser replay for the Justitia study.

Generate data:

```bash
python3 model/emit_explorable.py
```

Serve locally from the repository root:

```bash
python3 -m http.server --directory web 8000
```

Open <http://localhost:8000/>.

The browser does not run the model. It only replays JSON trajectories emitted from the Python substrate.
