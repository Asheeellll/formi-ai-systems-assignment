# Crash Recovery Evidence

- Test: forced termination with taskkill /T /F during startup
- Recovery: same simulator and persistent SQLite database
- Recovery exit code: 0
- SQLite integrity: ok
- Stored events: 297026
- Duplicate event IDs: 0
- Processed chunks: 393
- Final simulation minute: 11520/11520
- Completed successfully: True

## Limitations

The controller was killed during startup, not during an approval or configuration change.
This does not prove exactly-once external API effects.
