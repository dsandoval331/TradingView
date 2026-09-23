# Adapter implementation checkpoint

Initial governed research-revision adapter implementation.

Branch certification scope:
- exact historical SHA materialization in detached worktree
- exact HEAD verification
- isolated historical runner child process
- dual research/infrastructure SHA provenance
- current CCP regression suite

This checkpoint intentionally does not yet wire the adapter into the production dispatcher/worker. Production wiring follows only after this isolated adapter foundation passes PR certification.
