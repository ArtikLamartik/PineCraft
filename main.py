import pygame
import sys
import math
import os

pygame.init()
info = pygame.display.Info()
screen_width, screen_height = info.current_w, info.current_h
screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
pygame.display.set_caption("PineCraft")
clock = pygame.time.Clock()
TILE_SIZE = 64
CHUNK_SIZE = 16
CHUNK_PX = CHUNK_SIZE * TILE_SIZE
RENDER_DISTANCE = 3
SEED = 1024
WALK_SPEED = 0.04
SPRINT_SPEED = 0.07
ROTATION_SPEED = 0.15
player_angle = 0.0
player_grid_x = 0
player_grid_y = 0
player_pixel_x = 0.0
player_pixel_y = 0.0
target_grid_x = 0
target_grid_y = 0
loaded_chunks = {}

class PlayerAnimator:
    def __init__(self, base_path, fallback_color, tile_size, fps=10):
        self.tile_size = tile_size
        self.fps = fps
        self.frame_duration = 1024 // fps
        self.idle_frame = load_texture(f"{base_path}_walk_0.png", fallback_color)
        self.walk_frames = []
        frame_idx = 0
        while True:
            path = f"{base_path}_walk_{frame_idx}.png"
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.walk_frames.append(pygame.transform.scale(img, (tile_size, tile_size)))
                    frame_idx += 1
                except:
                    break
            else:
                break
        if not self.walk_frames:
            self.walk_frames = [self.idle_frame.copy()]
        self.current_frame = 0
        self.last_update = 0
        self.is_moving = False
        self.idle_transition_counter = 0
        self.idle_transition_delay = 5
        
    def update(self, is_moving, speed_multiplier=1.0):
        self.is_moving = is_moving
        now = pygame.time.get_ticks()
        effective_duration = self.frame_duration / speed_multiplier
        if is_moving and now - self.last_update > effective_duration:
            self.current_frame = (self.current_frame + 1) % len(self.walk_frames)
            self.last_update = now

    def get_frame(self, angle):
        if self.is_moving:
            base = self.walk_frames[self.current_frame]
        else:
            valid_idle_frames = [0, 4, 8]
            if self.current_frame not in valid_idle_frames:
                self.idle_transition_counter += 1
                if self.idle_transition_counter >= self.idle_transition_delay:
                    self.current_frame = (self.current_frame + 1) % len(self.walk_frames)
                    self.idle_transition_counter = 0
            base = self.walk_frames[self.current_frame]
        return pygame.transform.rotate(base, -angle)

def load_texture(path, fallback_color=(46, 139, 87)):
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))
        except Exception:
            pass
    surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
    surf.fill(fallback_color)
    return surf

grass_top_texture = load_texture("textures/blocks/grass_top.png")
grass_top_flowers_blue_texture = load_texture("textures/blocks/grass_top_flowers_blue.png")
grass_top_flowers_purple_texture = load_texture("textures/blocks/grass_top_flowers_purple.png")
grass_top_flowers_red_texture = load_texture("textures/blocks/grass_top_flowers_red.png")
grass_top_flowers_yellow_texture = load_texture("textures/blocks/grass_top_flowers_yellow.png")
player_animator = PlayerAnimator(
    base_path="textures/player/player",
    fallback_color=(255, 100, 100),
    tile_size=TILE_SIZE,
    fps=10
)
grass_rotated = {
    0:   grass_top_texture,
    90:  pygame.transform.rotate(grass_top_texture, -90),
    180: pygame.transform.rotate(grass_top_texture, 180),
    270: pygame.transform.rotate(grass_top_texture, 90),
}

def mulberry32(seed):
    def rng():
        nonlocal seed
        seed = (seed + 0x6D2B79F5) & 0xFFFFFFFF
        t = seed
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF) & 0xFFFFFFFF
        t = t ^ (t >> 14)
        return (t & 0xFFFFFFFF) / 4294967296
    return rng

def hash_coords(x, y):
    h = SEED ^ ((x * 374761393) & 0xFFFFFFFF) ^ ((y * 668265263) & 0xFFFFFFFF)
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)

def chunk_key(cx, cy):
    return (cx, cy)

def create_chunk_surface(cx, cy):
    surf = pygame.Surface((CHUNK_PX, CHUNK_PX))
    flower_textures = [
        grass_top_flowers_blue_texture,
        grass_top_flowers_purple_texture,
        grass_top_flowers_red_texture,
        grass_top_flowers_yellow_texture
    ]
    rot_angles = {0: 0, 90: -90, 180: 180, 270: 90}
    for ty in range(CHUNK_SIZE):
        for tx in range(CHUNK_SIZE):
            world_x = cx * CHUNK_SIZE + tx
            world_y = cy * CHUNK_SIZE + ty
            rng = mulberry32(hash_coords(world_x + 7, world_y + 13))
            rand_val = rng()
            if rand_val < 0.01:
                rot_key = [0, 90, 180, 270][int(rng() * 4)]
                rot_angle = rot_angles[rot_key]
                flower_choice = int(rng() * 4)
                base_tile = flower_textures[flower_choice]
                tile = pygame.transform.rotate(base_tile, rot_angle)
            elif rand_val < 0.5:
                rot = [0, 90, 180, 270][int(rng() * 4)]
                tile = grass_rotated[rot]
            else:
                tile = grass_top_texture
            surf.blit(tile, (tx * TILE_SIZE, ty * TILE_SIZE))
    return surf

def update_chunks():
    player_chunk_x = math.floor(player_grid_x / CHUNK_SIZE)
    player_chunk_y = math.floor(player_grid_y / CHUNK_SIZE)
    needed = set()
    for dy in range(-RENDER_DISTANCE, RENDER_DISTANCE + 1):
        for dx in range(-RENDER_DISTANCE, RENDER_DISTANCE + 1):
            cx = player_chunk_x + dx
            cy = player_chunk_y + dy
            key = chunk_key(cx, cy)
            needed.add(key)
            if key not in loaded_chunks:
                loaded_chunks[key] = (create_chunk_surface(cx, cy), cx, cy)
    to_remove = [k for k in loaded_chunks if k not in needed]
    for k in to_remove:
        del loaded_chunks[k]

keys_pressed = set()

def process_input():
    dx, dy = 0, 0
    is_sprinting = pygame.K_LSHIFT in keys_pressed or pygame.K_RSHIFT in keys_pressed
    if pygame.K_UP in keys_pressed or pygame.K_w in keys_pressed:    dy -= 1
    if pygame.K_DOWN in keys_pressed or pygame.K_s in keys_pressed:  dy += 1
    if pygame.K_LEFT in keys_pressed or pygame.K_a in keys_pressed:  dx -= 1
    if pygame.K_RIGHT in keys_pressed or pygame.K_d in keys_pressed: dx += 1
    if dx != 0 and dy != 0:
        length = math.sqrt(dx * dx + dy * dy)
        dx /= length
        dy /= length
    return dx, dy, is_sprinting

font = pygame.font.SysFont("Courier New", 14)
last_chunk_update = (None, None)
update_chunks()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN:
            keys_pressed.add(event.key)
            if event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
        if event.type == pygame.KEYUP:
            keys_pressed.discard(event.key)
        input_dx, input_dy, is_sprinting = process_input()
    speed = SPRINT_SPEED if is_sprinting else WALK_SPEED
    player_pixel_x += input_dx * speed * TILE_SIZE
    player_pixel_y += input_dy * speed * TILE_SIZE
    player_grid_x = math.floor(player_pixel_x / TILE_SIZE)
    player_grid_y = math.floor(player_pixel_y / TILE_SIZE)
    if (player_grid_x, player_grid_y) != last_chunk_update:
        last_chunk_update = (player_grid_x, player_grid_y)
        update_chunks()
    cam_x = -(player_pixel_x - screen_width / 2 + TILE_SIZE / 2)
    cam_y = -(player_pixel_y - screen_height / 2 + TILE_SIZE / 2)
    screen.fill((0, 0, 0))
    for key, (surf, cx, cy) in loaded_chunks.items():
        world_px = cx * CHUNK_PX
        world_py = cy * CHUNK_PX
        screen.blit(surf, (world_px + cam_x, world_py + cam_y))
    if abs(input_dx) > 0.1 or abs(input_dy) > 0.1:
        raw_angle = math.degrees(math.atan2(input_dy, input_dx)) + 90
        target_angle = round(raw_angle / 45) * 45
        target_angle %= 360
    else:
        target_angle = player_angle
    angle_diff = (target_angle - player_angle + 180) % 360 - 180
    player_angle += angle_diff * ROTATION_SPEED
    player_angle %= 360
    is_moving = (abs(input_dx) > 0.1 or abs(input_dy) > 0.1)
    player_animator.update(is_moving, speed_multiplier=1.0 if not is_sprinting else SPRINT_SPEED/WALK_SPEED)
    rotated_player = player_animator.get_frame(player_angle)
    player_rect = rotated_player.get_rect(center=(
        player_pixel_x + cam_x + TILE_SIZE / 2,
        player_pixel_y + cam_y + TILE_SIZE / 2
    ))
    screen.blit(rotated_player, player_rect)
    chunk_x = math.floor(player_grid_x / CHUNK_SIZE)
    chunk_y = math.floor(player_grid_y / CHUNK_SIZE)
    lines = [
        f"World:  {player_grid_x}, {player_grid_y}",
        f"Chunk:  {chunk_x}, {chunk_y}",
    ]
    hud_bg = pygame.Surface((180, 52), pygame.SRCALPHA)
    hud_bg.fill((0, 0, 0, 180))
    screen.blit(hud_bg, (10, 10))
    for i, line in enumerate(lines):
        text = font.render(line, True, (0, 255, 0))
        screen.blit(text, (20, 18 + i * 18))
    pygame.display.flip()
    clock.tick(60)
