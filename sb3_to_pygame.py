import json
from pathlib import Path

# Minimal SB3 -> Pygame converter for a few opcodes (event_whenkeypressed, motion_turnleft)

SCRATCH_KEY_TO_PYGAME = {
    'space': 'pygame.K_SPACE',
    'left arrow': 'pygame.K_LEFT',
    'right arrow': 'pygame.K_RIGHT',
    'up arrow': 'pygame.K_UP',
    'down arrow': 'pygame.K_DOWN',
}


def extract_event_handlers(blocks):
    handlers = {}
    for bid, b in blocks.items():
        if b.get('topLevel') and b.get('opcode') == 'event_whenkeypressed':
            key = b.get('fields', {}).get('KEY_OPTION', [None])[0]
            seq = resolve_block_sequence(b.get('next'), blocks)
            handlers[key] = seq
    return handlers


def resolve_block_sequence(start_id, blocks):
    seq = []
    cur = start_id
    while cur:
        b = blocks.get(cur)
        if not b:
            break
        seq.append(b)
        cur = b.get('next')
    return seq


def block_to_statements(block):
    op = block.get('opcode')
    if op == 'motion_turnleft':
        # inputs: DEGREES -> [1, [4, "180"]]
        deg = 0
        inp = block.get('inputs', {}).get('DEGREES')
        if inp and isinstance(inp, list) and len(inp) >= 2:
            val = inp[1]
            # val may be [4, "180"] or a number
            if isinstance(val, list) and len(val) >= 2:
                try:
                    deg = int(float(val[1]))
                except Exception:
                    deg = 0
            else:
                try:
                    deg = int(float(val))
                except Exception:
                    deg = 0
        return [f"sprite.turn_left({deg})"]

    # Unknown opcode -> comment
    return [f"# unsupported opcode: {op}"]


def convert_svg_to_png(svg_path, png_path):
    try:
        import cairosvg
    except Exception:
        return False
    try:
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return True
    except Exception:
        return False


def generate_pygame_script(project, out_path):
    targets = project.get('targets', [])
    # pick first non-stage sprite for `sprite` variable
    sprite_block_target = None
    sprite_name = 'Sprite'
    for t in targets:
        if not t.get('isStage'):
            sprite_block_target = t
            sprite_name = t.get('name', 'Sprite')
            break

    blocks = {}
    if sprite_block_target:
        blocks = sprite_block_target.get('blocks', {})

    handlers = extract_event_handlers(blocks)

    lines = []
    lines.append('import pygame')
    lines.append('import sys')
    lines.append('from pathlib import Path')
    lines.append('ROOT_DIR = Path(__file__).resolve().parent')
    lines.append("ASSETS_DIR = 'extracted_files'")
    lines.append('')
    lines.append('def load_image(path):')
    lines.append('    import os')
    lines.append('    path = Path(path)')
    lines.append('    if not path.is_absolute():')
    lines.append('        path = ROOT_DIR / path')
    lines.append('    try:')
    lines.append("        if str(path).lower().endswith('.svg'):")
    lines.append('            try:')
    lines.append('                import cairosvg')
    lines.append('                png_path = path.with_suffix(\'.png\')')
    lines.append('                if not os.path.exists(png_path):')
    lines.append('                    cairosvg.svg2png(url=str(path), write_to=str(png_path))')
    lines.append('                return pygame.image.load(str(png_path)).convert_alpha()')
    lines.append('            except Exception:')
    lines.append('                pass')
    lines.append('        return pygame.image.load(str(path)).convert_alpha()')
    lines.append('    except Exception:')
    lines.append('        surf = pygame.Surface((48,48), pygame.SRCALPHA)')
    lines.append('        surf.fill((255,0,255,128))')
    lines.append('        return surf')
    lines.append('')
    lines.append('def load_sound(path):')
    lines.append('    path = Path(path)')
    lines.append('    if not path.is_absolute():')
    lines.append('        path = ROOT_DIR / path')
    lines.append('    try:')
    lines.append('        return pygame.mixer.Sound(str(path))')
    lines.append('    except Exception:')
    lines.append('        return None')
    lines.append('')
    lines.append('')
    lines.append('class Sprite:')
    lines.append('    def __init__(self):')
    lines.append('        self.x = 0')
    lines.append('        self.y = 0')
    lines.append('        self.direction = 90')
    lines.append('')
    lines.append('    def turn_left(self, deg):')
    lines.append('        self.direction = (self.direction - deg) % 360')
    lines.append('        print(f"turned left {deg} -> direction={self.direction}")')
    lines.append('')
    lines.append('def main():')
    lines.append('    pygame.init()')
    lines.append('    screen = pygame.display.set_mode((480,360))')
    lines.append('    pygame.display.set_caption("Python Scratch")')
    lines.append('    clock = pygame.time.Clock()')
    # gather assets from project for this sprite
    costumes = []
    sounds = []
    if sprite_block_target:
        for c in sprite_block_target.get('costumes', []):
            md5ext = c.get('md5ext')
            name = c.get('name')
            center_x = c.get('rotationCenterX', 0)
            center_y = c.get('rotationCenterY', 0)
            if md5ext:
                costumes.append((name, md5ext, center_x, center_y))
        for s in sprite_block_target.get('sounds', []):
            md5ext = s.get('md5ext')
            name = s.get('name')
            if md5ext:
                sounds.append((name, md5ext))

    # emit asset loading code
    if costumes:
        lines.append("    images = {}")
        for name, md5ext, _, _ in costumes:
            asset_path = f"img/{md5ext}"
            lines.append(f"    images['{name}'] = load_image(r'{asset_path}')")
    else:
        lines.append('    images = {}')

    if sounds:
        lines.append("    sounds = {}")
        for name, md5ext in sounds:
            asset_path = f"sfx/{md5ext}"
            lines.append(f"    sounds['{name}'] = load_sound(r'{asset_path}')")
    else:
        lines.append('    sounds = {}')

    lines.append(f'    sprite = Sprite()  # {sprite_name}')
    lines.append('')
    lines.append('    while True:')
    lines.append('        for event in pygame.event.get():')
    lines.append('            if event.type == pygame.QUIT:')
    lines.append('                pygame.quit()')
    lines.append('                sys.exit()')
    lines.append('            if event.type == pygame.KEYDOWN:')
    # build key handling
    if handlers:
        for key, seq in handlers.items():
            pg_key = SCRATCH_KEY_TO_PYGAME.get(key, None)
            if not pg_key:
                # try direct mapping for single char like 'a'
                if key and len(key) == 1:
                    pg_key = f'pygame.K_{key.lower()}'
                else:
                    pg_key = None

            if pg_key:
                lines.append(f'                if event.key == {pg_key}:')
            else:
                lines.append(f'                # key "{key}" not mapped to pygame constant')
                lines.append(f'                if False:')

            for b in seq:
                for stmt in block_to_statements(b):
                    lines.append('                    ' + stmt)
    else:
        lines.append('                pass')

    lines.append('')
    lines.append("        screen.fill((255,255,255))")
    # if we have a costume, blit it
    if sprite_block_target and sprite_block_target.get('costumes'):
        first_costume_name = sprite_block_target.get('costumes')[0].get('name')
        lines.append(f"        if '{first_costume_name}' in images:")
        lines.append(f"            img = images['{first_costume_name}']")
        lines.append('            # rotate image according to sprite.direction (degrees)')
        lines.append('            rotated = pygame.transform.rotozoom(img, 90 - sprite.direction, 1)')
        lines.append('            rect = rotated.get_rect(center=(240 + sprite.x,180 - sprite.y))')
        lines.append('            screen.blit(rotated, rect)')

    lines.append('        pygame.display.flip()')
    lines.append('        clock.tick(60)')
    lines.append('')
    lines.append("if __name__ == '__main__':")
    lines.append('    main()')

    out_path = Path(out_path)
    out_path.write_text('\n'.join(lines), encoding='utf-8')
    return out_path


def generate_from_project_json(project_json_path, output_py_path):
    p = Path(project_json_path)
    project = json.loads(p.read_text(encoding='utf-8'))
    return generate_pygame_script(project, output_py_path)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        generate_from_project_json(sys.argv[1], sys.argv[2])
        print('Generated', sys.argv[2])
    else:
        print('Error: missing arguments')
        print('Usage: python sb3_to_pygame.py project.json out.py')