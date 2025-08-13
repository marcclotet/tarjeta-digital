import os
from PIL import Image

ROOT = os.path.dirname(__file__)
SRC = os.path.join(ROOT, "assets", "logo2.png")  # tu logo base
OUT_DIR = os.path.join(ROOT, "docs")

# Tamaños recomendados para PWA
SIZES = [192, 512]

# Color de fondo beige (RGB)
BG_COLOR = (237, 227, 207)

if not os.path.exists(SRC):
    raise FileNotFoundError(f"No se encuentra el logo en {SRC}")

# Abrir logo base
img = Image.open(SRC).convert("RGBA")

# Generar cada tamaño
for size in SIZES:
    canvas = Image.new("RGBA", (size, size), BG_COLOR + (255,))

    # Redimensionar logo manteniendo proporciones
    ratio = min((size * 0.6) / img.width, (size * 0.6) / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    logo_resized = img.resize(new_size, Image.LANCZOS)

    # Centrar en el lienzo
    pos = ((size - logo_resized.width) // 2, (size - logo_resized.height) // 2)
    canvas.paste(logo_resized, pos, logo_resized)

    # Guardar
    out_path = os.path.join(OUT_DIR, f"icon-{size}x{size}.png")
    canvas.save(out_path, format="PNG")
    print(f"[OK] Icono generado: {out_path}")

print("Listo. Tus iconos están en la carpeta docs/.")
