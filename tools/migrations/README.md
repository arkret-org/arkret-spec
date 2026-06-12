Historical one-shot migration helpers live here.

These scripts are kept for auditability and emergency replay only. They are
not part of the normal spec maintenance path. Day-to-day protocol changes
should use:

```bash
python tools/artifact_pipeline.py generate
python tools/artifact_pipeline.py check
```

When adding a new one-shot migration, put it in this directory from the start
and document the exact spec/artifact revision it targets in the script header.
