@AGENTS.md

## Claude Code notes

- Build and test through `./ci/*`; from macOS they delegate BuildStream work into the
  `myos-builder` Lima VM. Never run `bst` directly on macOS.
- Kernel builds and full image builds take a long time: run them in the background and
  keep working (or wait for the completion notification) instead of polling.
- Use plan mode for changes that cut across the boot chain, disk layout, junction bumps or
  milestone scope; these are where the spec's invariants are easiest to break.
- When you deviate from or interpret `docs/spec.md`, add an entry to `docs/decisions.md`
  in the same change.
- Component updates happen through `./ci/integrate`, not by editing refs. Don't pass
  `--commit` unless asked. A failed cycle is a result to report (it names the inputs that
  changed), not something to hide by pinning; propose a pin and let the user decide.
- Do not commit or push unless asked. Do not delete or recreate the `myos-builder` VM
  without asking: it holds the BuildStream cache.
