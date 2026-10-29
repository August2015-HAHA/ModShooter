import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import pygame

PLAYER_SIZE = 30
PLAYER_SPEED = 10
DASH_DISTANCE = 120
DASH_COOLDOWN_MS = 1000
DOUBLE_TAP_INTERVAL_MS = 300
PROJECTILE_SPEED = 20
ENEMY_SPAWN_INTERVAL_MS = 1000
WIN_SCORE = 10
CLUSTER_CHANCE_PER_LEVEL = 0.15
MAX_CLUSTER_CHANCE = 0.75
STARTING_HEALTH = 3
ENEMY_DEFINITIONS_DIR = Path(__file__).with_name("enemies")
LEVEL_DEFINITIONS_DIR = Path(__file__).with_name("levels")

PLAYER_COLOR = (0, 255, 65)
PROJECTILE_COLOR = PLAYER_COLOR
BOSS_SHOT_COLOR = (255, 120, 80)
MESSAGE_COLOR = (57, 255, 20)
MESSAGE_FONT_SIZE = 74


@dataclass(frozen=True)
class EnemyType:
    type_id: str
    display_name: str
    size: int
    health: int
    speed: float
    color: tuple[int, int, int]
    movement: str
    unlock_level: int
    spawn_chance: float
    spawn_chance_per_level: float
    max_spawn_chance: float
    spawn_priority: int
    clusterable: bool = True
    segments: int = 1
    sway_distance: int = 0
    segment_phase_offset: float = 0.3
    wave_speed: float = 0.08
    attack_speed: float = 0.0
    attack_interval: int = 0
    attack_size: int = 0


@dataclass(frozen=True)
class LevelDefinition:
    level: int
    name: str
    target_score: int
    spawn_interval_ms: int
    enemy_weights: dict[str, float]
    boss: bool


def health_color(health, max_health):
    health_ratio = health / max_health
    if health_ratio > 0.66:
        return (0, 230, 80)
    if health_ratio > 0.33:
        return (255, 210, 0)
    return (255, 55, 55)


class FileEnemy:
    def __init__(self, definition, x, y, screen_width):
        self.definition = definition
        self.health = definition.health
        self.max_health = definition.health
        self.speed = definition.speed
        self.phase = 0.0
        self.y = y
        self.direction = 1
        self.shot_timer = definition.attack_interval
        available_width = max(0, screen_width - definition.size)
        phase_spread_ratio = 2 * math.sin(
            (definition.segments - 1) * definition.segment_phase_offset / 2
        )
        max_sway = available_width / (2 * (1 + phase_spread_ratio))
        self.sway_distance = min(definition.sway_distance, int(max_sway))
        min_x, max_x = enemy_x_bounds(definition, screen_width)
        self.base_x = max(min_x, min(x, max_x))
        self.segments = [
            pygame.Rect(
                x, y + index * definition.size, definition.size, definition.size
            )
            for index in range(definition.segments)
        ]
        self._update_segments()

    @property
    def rect(self):
        return self.segments[0].unionall(self.segments[1:])

    def _update_segments(self):
        for index, segment in enumerate(self.segments):
            if self.definition.movement == "weave":
                segment.x = round(
                    self.base_x
                    + math.sin(
                        self.phase
                        - index * self.definition.segment_phase_offset
                    )
                    * self.sway_distance
                )
                segment.y = self.y + index * self.definition.size
            else:
                segment.x = self.base_x + index * self.definition.size
                segment.y = self.y

    def update(self):
        if self.definition.movement == "boss":
            return
        self.y += self.speed
        if self.definition.movement == "weave":
            self.phase += self.definition.wave_speed
        self._update_segments()

    def collides_with(self, rect):
        return any(segment.colliderect(rect) for segment in self.segments)

    def is_hit_by(self, projectile):
        return any(projectile.colliderect(segment) for segment in self.segments)

    def take_hit(self):
        self.health -= 1
        if len(self.segments) > 1:
            self.segments.pop()

    def draw(self, screen):
        for segment in self.segments:
            pygame.draw.rect(screen, self.definition.color, segment)
        draw_health_bar(
            screen,
            self.rect,
            self.health,
            self.max_health,
            health_color(self.health, self.max_health),
        )


def load_enemy_definitions(directory=ENEMY_DEFINITIONS_DIR):
    definitions = {}
    required_fields = {
        "id", "name", "size", "health", "speed", "color", "movement",
        "unlock_level", "spawn_priority", "clusterable", "segments",
        "sway_distance", "segment_phase_offset", "wave_speed", "spawn", "attack",
    }

    for path in sorted(directory.glob("*.enemy")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not load enemy definition '{path}': {error}") from error

        if not isinstance(data, dict):
            raise ValueError(f"Enemy definition '{path}' must contain a JSON object.")
        if set(data) != required_fields:
            missing_fields = required_fields - data.keys()
            extra_fields = data.keys() - required_fields
            details = []
            if missing_fields:
                details.append(f"missing: {', '.join(sorted(missing_fields))}")
            if extra_fields:
                details.append(f"unexpected: {', '.join(sorted(extra_fields))}")
            raise ValueError(
                f"Enemy definition '{path}' must use the shared schema "
                f"({'; '.join(details)})."
            )
        type_id = data["id"]
        if (
            not isinstance(type_id, str)
            or             not type_id.isidentifier()
            or type_id != type_id.lower()
        ):
            raise ValueError(f"Enemy definition '{path}' has an invalid id.")
        if type_id in definitions:
            raise ValueError(f"Duplicate enemy id '{type_id}' in '{path}'.")

        movement = data.get("movement", "fall")
        if not isinstance(movement, str) or movement not in ("fall", "weave", "boss"):
            raise ValueError(
                f"Enemy definition '{path}' has unsupported movement '{movement}'."
            )
        color = data["color"]
        if (
            not isinstance(color, list)
            or len(color) != 3
            or any(type(channel) is not int or not 0 <= channel <= 255 for channel in color)
        ):
            raise ValueError(
                f"Enemy definition '{path}' color must be three integers from 0 to 255."
            )

        size = data["size"]
        health = data["health"]
        speed = data["speed"]
        segments = data["segments"]
        if type(size) is not int or size <= 0:
            raise ValueError(f"Enemy definition '{path}' size must be a positive integer.")
        if type(health) is not int or health <= 0:
            raise ValueError(f"Enemy definition '{path}' health must be a positive integer.")
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or speed <= 0
        ):
            raise ValueError(f"Enemy definition '{path}' speed must be positive.")
        if not math.isfinite(speed):
            raise ValueError(f"Enemy definition '{path}' speed must be finite.")
        if type(segments) is not int or segments <= 0:
            raise ValueError(f"Enemy definition '{path}' segments must be a positive integer.")
        if movement == "weave" and segments < 2:
            raise ValueError(f"Enemy definition '{path}' needs at least 2 weave segments.")
        sway_distance = data["sway_distance"]
        if type(sway_distance) is not int or sway_distance < 0:
            raise ValueError(
                f"Enemy definition '{path}' sway_distance must be a non-negative integer."
            )
        segment_phase_offset = data["segment_phase_offset"]
        wave_speed = data["wave_speed"]
        for field_name, value in (
            ("segment_phase_offset", segment_phase_offset),
            ("wave_speed", wave_speed),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    f"Enemy definition '{path}' {field_name} must be a finite non-negative number."
                )
        clusterable = data["clusterable"]
        if type(clusterable) is not bool:
            raise ValueError(f"Enemy definition '{path}' clusterable must be true or false.")

        spawn = data["spawn"]
        attack = data["attack"]
        if not isinstance(spawn, dict) or set(spawn) != {
            "chance", "chance_per_level", "max_chance"
        }:
            raise ValueError(
                f"Enemy definition '{path}' spawn must contain chance, "
                "chance_per_level, and max_chance."
            )
        if not isinstance(attack, dict) or set(attack) != {
            "speed", "interval", "size"
        }:
            raise ValueError(
                f"Enemy definition '{path}' attack must contain speed, interval, and size."
            )
        name = data["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Enemy definition '{path}' name must be a non-empty string.")
        unlock_level = data["unlock_level"]
        spawn_chance = spawn["chance"]
        chance_per_level = spawn["chance_per_level"]
        max_chance = spawn["max_chance"]
        spawn_priority = data["spawn_priority"]
        for field_name, value in (
            ("unlock_level", unlock_level),
            ("spawn_priority", spawn_priority),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(
                    f"Enemy definition '{path}' {field_name} must be a positive integer."
                )
        for field_name, value in (
            ("spawn.chance", spawn_chance),
            ("spawn.chance_per_level", chance_per_level),
            ("spawn.max_chance", max_chance),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= value <= 1
            ):
                raise ValueError(
                    f"Enemy definition '{path}' {field_name} must be from 0 to 1."
                )
        attack_speed = attack["speed"]
        attack_interval = attack["interval"]
        attack_size = attack["size"]
        if (
            isinstance(attack_speed, bool)
            or not isinstance(attack_speed, (int, float))
            or not math.isfinite(attack_speed)
            or attack_speed < 0
        ):
            raise ValueError(
                f"Enemy definition '{path}' attack.speed must be a finite non-negative number."
            )
        if type(attack_interval) is not int or attack_interval < 0:
            raise ValueError(
                f"Enemy definition '{path}' attack.interval must be a non-negative integer."
            )
        if type(attack_size) is not int or attack_size < 0:
            raise ValueError(
                f"Enemy definition '{path}' attack.size must be a non-negative integer."
            )
        if movement == "boss" and (
            attack_speed <= 0 or attack_interval <= 0 or attack_size <= 0
        ):
            raise ValueError(
                f"Boss definition '{path}' needs positive attack speed, interval, and size."
            )
        if movement != "boss" and any(
            (attack_speed, attack_interval, attack_size)
        ):
            raise ValueError(
                f"Non-boss enemy definition '{path}' must use zero attack stats."
            )
        definition = EnemyType(
            type_id=type_id,
            display_name=name,
            size=size,
            health=health,
            speed=float(speed),
            color=tuple(color),
            movement=movement,
            unlock_level=unlock_level,
            spawn_chance=spawn_chance,
            spawn_chance_per_level=chance_per_level,
            max_spawn_chance=max_chance,
            spawn_priority=spawn_priority,
            clusterable=clusterable,
            segments=segments,
            sway_distance=sway_distance,
            segment_phase_offset=segment_phase_offset,
            wave_speed=wave_speed,
            attack_speed=float(attack_speed),
            attack_interval=attack_interval,
            attack_size=attack_size,
        )
        definitions[type_id] = definition

    if "enemy" not in definitions:
        raise ValueError(f"Enemy definitions in '{directory}' need an 'enemy' fallback.")
    if "boss" not in definitions or definitions["boss"].movement != "boss":
        raise ValueError(f"Enemy definitions in '{directory}' need a boss .enemy definition.")
    for type_id, definition in definitions.items():
        if (type_id == "boss") != (definition.movement == "boss"):
            raise ValueError(
                f"Enemy definition '{type_id}' must use movement='boss' only for the boss type."
            )
    return definitions


class BossShot:
    def __init__(self, x, y, velocity, size):
        self.rect = pygame.Rect(x, y, size, size)
        self.velocity = velocity


def create_player(screen_width, screen_height):
    return pygame.Rect(
        (screen_width - PLAYER_SIZE) // 2,
        screen_height - PLAYER_SIZE,
        PLAYER_SIZE,
        PLAYER_SIZE,
    )


def create_boss(screen_width):
    definition = ENEMY_TYPES["boss"]
    x = (screen_width - definition.size) // 2
    return create_enemy("boss", x, 45, screen_width)


def enemy_x_bounds(definition, screen_width):
    if definition.movement != "weave":
        return 0, screen_width - definition.size
    available_width = max(0, screen_width - definition.size)
    phase_spread_ratio = 2 * math.sin(
        (definition.segments - 1) * definition.segment_phase_offset / 2
    )
    max_sway = available_width / (2 * (1 + phase_spread_ratio))
    sway_distance = min(definition.sway_distance, int(max_sway))
    tail_offset = math.ceil(sway_distance * phase_spread_ratio)
    margin = min(sway_distance + tail_offset, available_width // 2)
    return margin, available_width - margin


def create_enemy(enemy_type, x, y, screen_width):
    definition = ENEMY_TYPES[enemy_type]
    return FileEnemy(definition, x, y, screen_width)


ENEMY_TYPES = load_enemy_definitions()
BOSS_INTERVAL_LEVELS = ENEMY_TYPES["boss"].unlock_level


def load_level_definitions(directory=LEVEL_DEFINITIONS_DIR):
    definitions = {}
    required_fields = {
        "level",
        "name",
        "target_score",
        "spawn_interval_ms",
        "enemy_weights",
        "boss",
    }

    for path in sorted(directory.glob("*.lvl")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not load level definition '{path}': {error}") from error

        if not isinstance(data, dict) or set(data) != required_fields:
            raise ValueError(
                f"Level definition '{path}' must contain exactly: "
                f"{', '.join(sorted(required_fields))}."
            )

        level_number = data["level"]
        if type(level_number) is not int or level_number < 1:
            raise ValueError(f"Level definition '{path}' level must be a positive integer.")
        if level_number in definitions:
            raise ValueError(f"Duplicate level number {level_number} in '{path}'.")
        name = data["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Level definition '{path}' name must be a non-empty string.")
        target_score = data["target_score"]
        spawn_interval = data["spawn_interval_ms"]
        if type(target_score) is not int or target_score < 1:
            raise ValueError(
                f"Level definition '{path}' target_score must be a positive integer."
            )
        if type(spawn_interval) is not int or spawn_interval < 1:
            raise ValueError(
                f"Level definition '{path}' spawn_interval_ms must be a positive integer."
            )
        if type(data["boss"]) is not bool:
            raise ValueError(f"Level definition '{path}' boss must be true or false.")

        weights = data["enemy_weights"]
        if not isinstance(weights, dict) or not weights:
            raise ValueError(
                f"Level definition '{path}' enemy_weights must be a non-empty object."
            )
        for enemy_id, weight in weights.items():
            if enemy_id not in ENEMY_TYPES or ENEMY_TYPES[enemy_id].movement == "boss":
                raise ValueError(
                    f"Level definition '{path}' references unknown spawn enemy '{enemy_id}'."
                )
            if (
                isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or not math.isfinite(weight)
                or weight <= 0
            ):
                raise ValueError(
                    f"Level definition '{path}' enemy weight for '{enemy_id}' "
                    "must be a positive number."
                )
            if level_number < ENEMY_TYPES[enemy_id].unlock_level:
                raise ValueError(
                    f"Level definition '{path}' uses '{enemy_id}' before its unlock level."
                )

        definitions[level_number] = LevelDefinition(
            level=level_number,
            name=name,
            target_score=target_score,
            spawn_interval_ms=spawn_interval,
            enemy_weights=weights,
            boss=data["boss"],
        )
    return definitions


LEVEL_DEFINITIONS = load_level_definitions()


def get_level_definition(level_number):
    special = LEVEL_DEFINITIONS.get(level_number)
    if special is not None:
        return special
    return LevelDefinition(
        level=level_number,
        name=f"Level {level_number}",
        target_score=WIN_SCORE,
        spawn_interval_ms=ENEMY_SPAWN_INTERVAL_MS,
        enemy_weights={},
        boss=level_number % BOSS_INTERVAL_LEVELS == 0,
    )


def move_player(player, keys):
    if keys[pygame.K_d]:
        player.x += PLAYER_SPEED
    if keys[pygame.K_a]:
        player.x -= PLAYER_SPEED


def dash_player(player, direction, screen_rect):
    if direction not in (-1, 1):
        return False

    player.x += direction * DASH_DISTANCE
    player.clamp_ip(screen_rect)
    return True


def fire_projectile(projectiles, player):
    projectiles.append(player.copy())


def spawn_enemy(enemies, screen_width, level, enemy_weights=None):
    selected_type = "enemy"
    if enemy_weights:
        selected_type = random.choices(
            list(enemy_weights), weights=list(enemy_weights.values()), k=1
        )[0]
    else:
        for enemy_type, definition in sorted(
            ENEMY_TYPES.items(), key=lambda item: item[1].spawn_priority
        ):
            if enemy_type == "enemy" or definition.movement == "boss" or level < definition.unlock_level:
                continue
            chance = min(
                definition.spawn_chance
                + definition.spawn_chance_per_level * level,
                definition.max_spawn_chance,
            )
            if random.random() < chance:
                selected_type = enemy_type
                break

    definition = ENEMY_TYPES[selected_type]
    cluster_chance = min(CLUSTER_CHANCE_PER_LEVEL * level, MAX_CLUSTER_CHANCE)
    sample = create_enemy(selected_type, 0, 0, screen_width)
    if definition.clusterable and random.random() < cluster_chance:
        enemy_width = sample.rect.width
        cluster_x = random.randint(0, screen_width - enemy_width * 2)
        enemies.append(
            create_enemy(selected_type, cluster_x, -sample.rect.height, screen_width)
        )
        enemies.append(
            create_enemy(
                selected_type,
                cluster_x + enemy_width,
                -sample.rect.height,
                screen_width,
            )
        )
    else:
        min_x, max_x = enemy_x_bounds(definition, screen_width)
        enemy_x = random.randint(min_x, max_x)
        enemies.append(
            create_enemy(selected_type, enemy_x, -sample.rect.height, screen_width)
        )


def update_projectiles(projectiles, enemies, boss=None):
    score_increase = 0
    for projectile in projectiles[:]:
        projectile.y -= PROJECTILE_SPEED
        if projectile.bottom <= 0:
            projectiles.remove(projectile)
            continue
        for enemy in enemies[:]:
            if enemy.is_hit_by(projectile):
                projectiles.remove(projectile)
                enemy.take_hit()
                if enemy.health <= 0:
                    enemies.remove(enemy)
                    score_increase += 1
                break
        else:
            if boss is not None and boss.health > 0 and projectile.colliderect(boss.rect):
                projectiles.remove(projectile)
                boss.health -= 1
                if boss.health <= 0:
                    score_increase += WIN_SCORE
    return score_increase


def update_boss(boss, boss_shots, player, screen_width):
    if boss is None or boss.health <= 0:
        return

    boss.base_x += boss.speed * boss.direction
    boss._update_segments()
    if boss.rect.left <= 0:
        boss.base_x = 0
        boss.direction = 1
        boss._update_segments()
    elif boss.rect.right >= screen_width:
        boss.base_x = screen_width - boss.definition.size
        boss.direction = -1
        boss._update_segments()

    boss.shot_timer -= 1
    if boss.shot_timer <= 0:
        shot_start = pygame.Vector2(boss.rect.centerx, boss.rect.bottom)
        target = pygame.Vector2(player.centerx, player.centery)
        direction = target - shot_start
        if direction.length_squared() > 0:
            velocity = direction.normalize() * boss.definition.attack_speed
            boss_shots.append(
                BossShot(
                    boss.rect.centerx - boss.definition.attack_size // 2,
                    boss.rect.bottom,
                    velocity,
                    boss.definition.attack_size,
                )
            )
        boss.shot_timer = boss.definition.attack_interval


def update_boss_shots(boss_shots, player, screen_width, screen_height):
    damage = 0
    for shot in boss_shots[:]:
        shot.rect.x += round(shot.velocity.x)
        shot.rect.y += round(shot.velocity.y)
        if shot.rect.colliderect(player):
            boss_shots.remove(shot)
            damage += 1
        elif (
            shot.rect.bottom < 0
            or shot.rect.top > screen_height
            or shot.rect.right < 0
            or shot.rect.left > screen_width
        ):
            boss_shots.remove(shot)
    return damage


def draw_enemy(screen, enemy):
    if hasattr(enemy, "draw"):
        enemy.draw(screen)
        return

    color = health_color(enemy.health, enemy.max_health)
    pygame.draw.rect(screen, color, enemy.rect)
    draw_health_bar(screen, enemy.rect, enemy.health, enemy.max_health, color)


def draw_health_bar(screen, rect, health, max_health, color):
    bar_rect = pygame.Rect(rect.x, rect.y - 7, rect.width, 4)
    pygame.draw.rect(screen, (70, 70, 70), bar_rect)
    health_width = round(bar_rect.width * health / max_health)
    if health_width > 0:
        pygame.draw.rect(
            screen, color, (bar_rect.x, bar_rect.y, health_width, bar_rect.height)
        )


def update_enemies(enemies, player, screen_height):
    escaped = 0
    damage = 0
    for enemy in enemies[:]:
        enemy.update()
        if enemy.collides_with(player):
            enemies.remove(enemy)
            damage += 1
        elif enemy.rect.top >= screen_height:
            enemies.remove(enemy)
            escaped += 1
    return escaped, damage
