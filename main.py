# A program to convert Scratch .sb3 files to Python code

from src.imports import *
from src.sb3_to_pygame import generate_from_project_json
import shutil
import sys


def extract_zip_files(directory, output_path):
    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)
    for f in Path(directory).glob('*.sb3'):
        with zipfile.ZipFile(f, 'r') as archive:
            archive.extractall(path=output_path)
            print(f"Extracted contents from '{f.name}' to '{output_path}' directory.")


def open_scratch_code(file_path):
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    json_object = None
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as json_file:
                json_object = json.load(json_file)
            break
        except UnicodeDecodeError:
            continue
    if json_object is None:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as json_file:
            json_object = json.load(json_file)

    # normalize and rewrite the project.json with consistent encoding/format
    Path(file_path).write_text(json.dumps(json_object, indent=4, separators=(',', ':')), encoding='utf-8')
    return json_object


def copy_assets_to_output(project, extracted_dir, output_dir):
    img_dir = output_dir / 'img'
    sfx_dir = output_dir / 'sfx'
    img_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir.mkdir(parents=True, exist_ok=True)

    for target in project.get('targets', []):
        for costume in target.get('costumes', []):
            md5ext = costume.get('md5ext')
            if md5ext:
                src = Path(extracted_dir) / md5ext
                dst = img_dir / md5ext
                if src.exists():
                    shutil.copy2(src, dst)
        for sound in target.get('sounds', []):
            md5ext = sound.get('md5ext')
            if md5ext:
                src = Path(extracted_dir) / md5ext
                dst = sfx_dir / md5ext
                if src.exists():
                    shutil.copy2(src, dst)


if __name__ == '__main__':
    # 1) Extract any .sb3 files into ./extracted_files
    extract_zip_files('./scratch_files', './extracted_files')

    project_path = Path('extracted_files') / 'project.json'
    if not project_path.exists():
        print('No project.json found in extracted_files; make sure an .sb3 was present.')
        sys.exit(1)

    # 2) Load / normalize project.json
    scratch_code = open_scratch_code(str(project_path))
    print('Loaded project.json (top-level targets:', len(scratch_code.get('targets', [])), ')')

    # 3) Create scratch output folder and copy assets
    output_dir = Path('scratch')
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_assets_to_output(scratch_code, Path('extracted_files'), output_dir)

    # 4) Generate pygame script into scratch/converted_game.py
    out_file = output_dir / 'converted_game.py'
    generate_from_project_json(str(project_path), str(out_file))
    print(f'Converted Scratch project to {out_file}')