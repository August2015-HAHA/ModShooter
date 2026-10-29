# Special levels

Add a JSON `.lvl` file to this folder and restart the game. The `level` number
selects the round to customize. Every `.lvl` file must use the same fields:

```json
{
  "level": 3,
  "name": "Power Surge",
  "target_score": 10,
  "spawn_interval_ms": 850,
  "enemy_weights": {
    "enemy": 1,
    "powerful": 4
  },
  "boss": false
}
```

`enemy_weights` are relative weights for random spawns on that level. They may
name any registered `.enemy` type that has unlocked by that level; bosses are
started separately and cannot be listed here. `target_score` controls how many
points are needed to finish the round, and `spawn_interval_ms` sets the delay
between spawn events. Set `boss` to `true` for a boss round. Levels without a
matching `.lvl` file use the normal defaults, including a boss every fifth
level.

The `.lvl` extension contains JSON text, just like `.enemy` files. Restart the
game after editing or adding definitions to load the changes.
