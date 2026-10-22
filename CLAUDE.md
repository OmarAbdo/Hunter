# Hunter

This project runs under doctrine. Its rules are enforced by hooks, git hooks and CI; this file only
tells you where things are.

- Before any change: `doctrine item start --kind <feature|fix|restore|refactor|chore> --title "..." --scope <paths>`.
- Features, fixes and restores: write the failing test, run `doctrine test`, then write the code.
- `doctrine check` must pass before you say anything works.
- The outcome: `doctrine metric record`. When the line stops, only restore items may change code.
- Done: `doctrine item done`, push the item branch, open a pull request. CI decides.

The outcome and the services are in `doctrine.toml`; the rule table is doctrine's, not this project's.
