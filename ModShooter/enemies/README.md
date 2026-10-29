# Custom enemies

Add a JSON `.enemy` file to this folder, then restart the game. Every definition,
including the boss, uses the exact same fields. Change field values to customize
stats and behavior; do not add or remove fields. The file name can be anything;
the `id` becomes the name used by the developer console command `summon <id>`.

Example:

```json
{
  "id": "armored",
  "name": "Armored",
  "size": 42,
  "health": 5,
  "speed": 1.5,
  "color": [180, 50, 255],
  "movement": "fall",
  "unlock_level": 1,
  "spawn_priority": 3,
  "clusterable": false,
  "segments": 1,
  "sway_distance": 0,
  "segment_phase_offset": 0.3,
  "wave_speed": 0.08,
  "spawn": {
    "chance": 0.0,
    "chance_per_level": 0.05,
    "max_chance": 0.3
  },
  "attack": {
    "speed": 0,
    "interval": 0,
    "size": 0
  }
}
```

`id`, `name`, `size`, `health`, `speed`, `color`, and `movement` identify the
enemy. `color` is three RGB values from 0 to 255. `movement` is `fall`, `weave`,
or `boss`. For `weave`, `segments` is the number of touching squares in the
vertical chain; `sway_distance`, `segment_phase_offset`, and `wave_speed` tune
its motion. These fields are still present for every type, even if unused.
`unlock_level` controls when an enemy first appears in random spawns. Bosses use
the `attack` stats for projectile speed,
frame interval, and projectile size. Non-boss types set all three attack values
to zero.

The `spawn` object always has `chance`, `chance_per_level`, and `max_chance`.
Spawn selection checks eligible non-boss enemies in ascending `spawn_priority`
order. `chance` is the base probability, increased by `chance_per_level` each
level up to `max_chance`. `clusterable` controls whether regular spawning can
create touching pairs. Keep the built-in `enemy.enemy` file as the fallback and
`boss.enemy` as the boss definition.
