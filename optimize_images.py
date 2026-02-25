"""
optimize_images.py
──────────────────────────────────────────────────────────────────
Сжимает все .jpg / .jpeg / .png в проекте, конвертирует в WebP
и обновляет ссылки в .html файлах.

Что делает:
  1. Копирует оригиналы в папку backup_images/ (с сохранением структуры)
  2. Конвертирует каждое изображение в .webp (качество 82%)
  3. Удаляет оригинальный файл (оригинал уже в backup_images/)
  4. В каждом .html заменяет расширения .jpg / .jpeg / .png → .webp

Запуск:
  python optimize_images.py

Откат (если что-то пошло не так):
  Удали все .webp файлы и скопируй оригиналы из backup_images/ обратно.
"""

import os
import re
import shutil
from pathlib import Path

# ─── настройки ────────────────────────────────────────────────
QUALITY      = 82          # WebP качество 0–100  (82 = почти незаметная потеря)
BACKUP_DIR   = "backup_images"
IMG_EXTS     = {".jpg", ".jpeg", ".png"}
SKIP_DIRS    = {BACKUP_DIR, ".git", "node_modules", "__pycache__"}
# ──────────────────────────────────────────────────────────────

try:
    from PIL import Image
except ImportError:
    print("❌  Pillow не найден. Установи его командой:\n")
    print("       pip install Pillow\n")
    raise SystemExit(1)

ROOT = Path(__file__).parent.resolve()


def should_skip(path: Path) -> bool:
    """Пропускать файлы внутри служебных папок."""
    return any(part in SKIP_DIRS for part in path.parts)


def find_images() -> list[Path]:
    imgs = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS and not should_skip(p.relative_to(ROOT)):
            imgs.append(p)
    return imgs


def find_html_files() -> list[Path]:
    htmls = []
    for p in ROOT.rglob("*.html"):
        if not should_skip(p.relative_to(ROOT)):
            htmls.append(p)
    return htmls


def backup(src: Path):
    rel     = src.relative_to(ROOT)
    dst     = ROOT / BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)


def convert_to_webp(src: Path) -> Path:
    """Конвертирует файл в WebP, возвращает путь нового файла."""
    dst = src.with_suffix(".webp")
    with Image.open(src) as img:
        # RGBA нужен для PNG с прозрачностью
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")
        img.save(dst, "WEBP", quality=QUALITY, method=6)
    return dst


def patch_html_files(html_files: list[Path], renamed: dict[str, str]):
    """
    В каждом .html заменяет вхождения старых расширений на .webp.
    renamed: {'/относительный/путь.jpg': '/относительный/путь.webp'}
    """
    # Строим паттерн: любое из старых расширений (нечувствительно к регистру)
    pattern = re.compile(
        r'(["\'])([^"\']+?)(' + "|".join(re.escape(e) for e in IMG_EXTS) + r')(["\'])',
        re.IGNORECASE
    )

    for html_path in html_files:
        text = html_path.read_text(encoding="utf-8", errors="replace")
        new_text = pattern.sub(
            lambda m: m.group(1) + m.group(2) + ".webp" + m.group(4),
            text
        )
        if new_text != text:
            html_path.write_text(new_text, encoding="utf-8")
            print(f"  📄  Обновлён HTML: {html_path.relative_to(ROOT)}")


# ─── main ─────────────────────────────────────────────────────
def main():
    images = find_images()
    if not images:
        print("✅  Изображений для обработки не найдено.")
        return

    print(f"\n🔍  Найдено изображений: {len(images)}\n")

    total_before = 0
    total_after  = 0
    renamed      = {}

    for src in images:
        size_before = src.stat().st_size

        # 1. бэкап
        backup(src)

        # 2. конвертация
        try:
            dst = convert_to_webp(src)
        except Exception as e:
            print(f"  ⚠️   Ошибка при обработке {src.name}: {e}")
            continue

        size_after = dst.stat().st_size
        saving     = (1 - size_after / size_before) * 100

        total_before += size_before
        total_after  += size_after

        # 3. удаляем оригинал (он уже в backup)
        src.unlink()

        # 4. запоминаем переименование для патча HTML
        rel_src = str(src.relative_to(ROOT)).replace("\\", "/")
        rel_dst = str(dst.relative_to(ROOT)).replace("\\", "/")
        renamed[rel_src] = rel_dst

        tag = "✅" if saving > 5 else "➡️ "
        print(f"  {tag}  {src.name:40s}  "
              f"{size_before/1024:>7.1f} KB  →  {size_after/1024:>7.1f} KB  "
              f"({saving:+.1f}%)")

    # 5. патчим HTML
    html_files = find_html_files()
    if html_files and renamed:
        print(f"\n🔗  Обновляю ссылки в HTML-файлах...\n")
        patch_html_files(html_files, renamed)

    # 6. итоги
    total_saving = (1 - total_after / total_before) * 100 if total_before else 0
    print(f"\n{'─'*60}")
    print(f"  До:    {total_before/1024/1024:.2f} MB")
    print(f"  После: {total_after/1024/1024:.2f} MB")
    print(f"  Экономия: {total_saving:.1f}%")
    print(f"\n  💾  Оригиналы сохранены в: {BACKUP_DIR}/")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
