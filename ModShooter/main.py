import pygame

from game_actions import (
    MESSAGE_COLOR,
    MESSAGE_FONT_SIZE,
    PLAYER_COLOR,
    PROJECTILE_COLOR,
    STARTING_HEALTH,
    BOSS_SHOT_COLOR,
    DASH_COOLDOWN_MS,
    DOUBLE_TAP_INTERVAL_MS,
    ENEMY_TYPES,
    create_boss,
    create_enemy,
    create_player,
    dash_player,
    draw_enemy,
    fire_projectile,
    get_level_definition,
    move_player,
    spawn_enemy,
    update_enemies,
    update_boss,
    update_boss_shots,
    update_projectiles,
)

pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("My Game")
clock = pygame.time.Clock()
rect = create_player(screen.get_width(), screen.get_height())
rect2s = []
enemies = []
boss = None
boss_shots = []
enemy_spawn_event = pygame.event.custom_type()
font = pygame.font.SysFont("consolas", MESSAGE_FONT_SIZE, bold=True)
hud_font = pygame.font.SysFont("consolas", 28, bold=True)
running = True
score = 0
level = 1
level_config = get_level_definition(level)
pygame.time.set_timer(enemy_spawn_event, level_config.spawn_interval_ms)
boss = create_boss(screen.get_width()) if level_config.boss else None
health = STARTING_HEALTH
next_dash_available_ms = 0
last_direction_tap_ms = {pygame.K_a: None, pygame.K_d: None}
console_open = False
console_input = ""
console_messages = ["Type 'help' to see commands."]
test_stage = False


def execute_console_command(command):
    global boss, score, test_stage

    parts = command.strip().lower().split()
    if not parts:
        return "Enter a command, or type 'help'."

    name = parts[0]
    if name == "help":
        enemy_names = "|".join(
            enemy_type for enemy_type in ENEMY_TYPES if enemy_type != "boss"
        )
        return f"Commands: test, play, summon {enemy_names}|boss, help"
    if name == "test":
        test_stage = True
        score = 0
        enemies.clear()
        rect2s.clear()
        boss_shots.clear()
        boss = None
        return "Test stage enabled; random enemies are disabled."
    if name in ("play", "exit"):
        test_stage = False
        score = 0
        if level_config.boss and (boss is None or boss.health <= 0):
            boss = create_boss(screen.get_width())
        return "Test stage disabled; normal play resumed."
    if name == "summon":
        if len(parts) != 2:
            enemy_names = "|".join(
                enemy_type for enemy_type in ENEMY_TYPES if enemy_type != "boss"
            )
            return f"Usage: summon {enemy_names}|boss"
        kind = parts[1]
        if kind == "boss":
            if boss is not None and boss.health > 0:
                return "A boss is already active."
            boss = create_boss(screen.get_width())
        elif kind in ENEMY_TYPES:
            sample = create_enemy(kind, 0, 0, screen.get_width())
            x = (screen.get_width() - sample.rect.width) // 2
            enemies.append(create_enemy(kind, x, 60, screen.get_width()))
        else:
            enemy_names = ", ".join(ENEMY_TYPES)
            return f"Unknown enemy type. Try: {enemy_names}."
        return f"Summoned {kind}."
    return f"Unknown command: {name}. Type 'help' for commands."


while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            console_open = not console_open
        elif console_open and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                command = console_input
                console_messages.append(f"> {command}")
                console_messages.append(execute_console_command(command))
                console_messages = console_messages[-8:]
                console_input = ""
            elif event.key == pygame.K_BACKSPACE:
                console_input = console_input[:-1]
            elif event.unicode.isprintable():
                console_input += event.unicode
        elif (
            not console_open
            and event.type == pygame.KEYDOWN
            and event.key in last_direction_tap_ms
        ):
            now = pygame.time.get_ticks()
            previous_tap = last_direction_tap_ms[event.key]
            if (
                previous_tap is not None
                and now - previous_tap <= DOUBLE_TAP_INTERVAL_MS
                and now >= next_dash_available_ms
            ):
                direction = -1 if event.key == pygame.K_a else 1
                if dash_player(rect, direction, screen.get_rect()):
                    next_dash_available_ms = now + DASH_COOLDOWN_MS
                last_direction_tap_ms[event.key] = None
            else:
                last_direction_tap_ms[event.key] = now
        elif console_open:
            continue
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            fire_projectile(rect2s, rect)
        elif (
            event.type == enemy_spawn_event
            and not test_stage
            and not console_open
        ):
            spawn_enemy(
                enemies,
                screen.get_width(),
                level,
                level_config.enemy_weights or None,
            )

    if not console_open:
        keys = pygame.key.get_pressed()
        move_player(rect, keys)
        score += update_projectiles(rect2s, enemies, boss)
        escaped, damage = update_enemies(enemies, rect, screen.get_height())
        score = max(0, score - escaped)
        update_boss(boss, boss_shots, rect, screen.get_width())
        health -= damage + update_boss_shots(
            boss_shots, rect, screen.get_width(), screen.get_height()
        )

    if not console_open and health <= 0:
        screen.fill((0, 0, 0))
        text = font.render("Game Over", True, MESSAGE_COLOR)
        screen.blit(text, (screen.get_width() // 2 - text.get_width() // 2, screen.get_height() // 2 - text.get_height() // 2))
        pygame.display.flip()
        pygame.time.wait(2000)
        break
    elif (
        not console_open
        and not test_stage
        and score >= level_config.target_score
        and (not level_config.boss or boss is None or boss.health <= 0)
    ):
        running = False
        screen.fill((0, 0, 0))
        text = font.render(f"{level_config.name} Complete!", True, MESSAGE_COLOR)
        screen.blit(text, (screen.get_width() // 2 - text.get_width() // 2, screen.get_height() // 2 - text.get_height() // 2))
        pygame.display.flip()
        pygame.time.wait(2000)
        level += 1
        level_config = get_level_definition(level)
        pygame.time.set_timer(enemy_spawn_event, level_config.spawn_interval_ms)
        score = 0
        enemies.clear()
        rect2s.clear()
        boss_shots.clear()
        boss = create_boss(screen.get_width()) if level_config.boss else None
        running = True

    screen.fill((0, 0, 0))
    pygame.draw.rect(screen, PLAYER_COLOR, rect)
    for rect2 in rect2s:
        pygame.draw.rect(screen, PROJECTILE_COLOR, rect2)
    for enemy in enemies:
        draw_enemy(screen, enemy)
    if boss is not None and boss.health > 0:
        draw_enemy(screen, boss)
    for shot in boss_shots:
        pygame.draw.rect(screen, BOSS_SHOT_COLOR, shot.rect)
    dash_remaining = max(
        0, next_dash_available_ms - pygame.time.get_ticks()
    )
    dash_status = (
        "DASH READY (DOUBLE-TAP A/D)"
        if dash_remaining == 0
        else f"DASH: {dash_remaining / 1000:.1f}s"
    )
    status_text = hud_font.render(f"HP: {health}  Score: {score}", True, MESSAGE_COLOR)
    screen.blit(status_text, (10, 10))
    dash_text = hud_font.render(dash_status, True, MESSAGE_COLOR)
    screen.blit(dash_text, (10, 42))
    if boss is not None and boss.health > 0:
        boss_text = hud_font.render("BOSS", True, MESSAGE_COLOR)
        screen.blit(
            boss_text,
            (screen.get_width() - boss_text.get_width() - 10, 10),
        )
    if test_stage:
        test_text = hud_font.render("TEST STAGE", True, MESSAGE_COLOR)
        screen.blit(
            test_text,
            (screen.get_width() - test_text.get_width() - 10, 42),
        )
    if console_open:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))
        console_lines = [
            "DEVELOPER CONSOLE  (ESC to close)",
            *console_messages,
            f"> {console_input}_",
        ]
        y = 20
        for line in console_lines:
            line_surface = hud_font.render(line, True, MESSAGE_COLOR)
            screen.blit(line_surface, (20, y))
            y += 36
    pygame.display.flip()
    boss_status = " - BOSS" if boss is not None and boss.health > 0 else ""
    pygame.display.set_caption(
        f"My Game - {level_config.name} - Score: {score}{boss_status}"
    )
    clock.tick(60)

pygame.quit()