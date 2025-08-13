import os, csv
from jinja2 import Environment, FileSystemLoader
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw

# URL pública opcional (déjala vacía si aún no publicas)
BASE_URL = "https://marcclotet.github.io/tarjeta-digital"

ROOT = os.path.dirname(__file__)
env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")))
tpl = env.get_template("card.html")

ASSETS_DIR = os.path.join(ROOT, "assets", "photos")
FALLBACK = "placeholder.jpg"
CANDIDATE_EXTS = [".jpg", ".jpeg", ".png", ".webp"]

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def listdir_ci(path):
    """Devuelve {nombre_en_lower: nombre_real} para búsqueda case-insensitive."""
    return {f.lower(): f for f in os.listdir(path)} if os.path.isdir(path) else {}

def find_photo_name(requested: str) -> str:
    """
    Dado 'marc.jpeg' / 'Marc.JPG' / 'marc' encuentra el archivo real en assets/photos/
    (case-insensitive y probando extensiones comunes).
    """
    files_ci = listdir_ci(ASSETS_DIR)
    if not requested:
        return files_ci.get(FALLBACK.lower(), "")
    req_lower = requested.strip().lower()

    # Coincidencia directa
    if req_lower in files_ci:
        return files_ci[req_lower]

    name, ext = os.path.splitext(req_lower)
    has_ext = ext in CANDIDATE_EXTS

    # Si tiene extensión, prueba mismas base con otras extensiones
    if has_ext:
        for cand_ext in CANDIDATE_EXTS:
            alt = name + cand_ext
            if alt in files_ci: return files_ci[alt]
    else:
        # Si no tiene extensión, prueba todas
        for cand_ext in CANDIDATE_EXTS:
            alt = name + cand_ext
            if alt in files_ci: return files_ci[alt]

    return files_ci.get(FALLBACK.lower(), "")

def read_csv_rows(csv_path):
    """Lee CSV detectando delimitador (coma, ; o tab)."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        sample = f.read(2048); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',',';','\t'])
        except csv.Error:
            class SimpleDialect(csv.Dialect):
                delimiter = ','
                quotechar = '"'
                doublequote = True
                skipinitialspace = True
                lineterminator = '\n'
                quoting = csv.QUOTE_MINIMAL
            dialect = SimpleDialect()
        return list(csv.DictReader(f, dialect=dialect))

def find_logo2_path():
    """Busca assets/logo2.(png|jpg|jpeg|webp) sin distinguir mayúsculas."""
    base = os.path.join(ROOT, "assets")
    files_ci = listdir_ci(base)
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        key = f"logo2{ext}".lower()
        if key in files_ci:
            return os.path.join(base, files_ci[key])
    return ""  # opcional: sin logo2 no pasa nada

def create_qr_with_logo_and_clear_area(url, out_path, logo_path=None,
                                       box_size=10, border=4,
                                       clear_ratio=0.30, logo_scale=0.78):
    """
    Genera un QR con ERROR_CORRECT_H, abre un "hueco" blanco centrado y pone el logo centrado.
    - clear_ratio: tamaño del hueco respecto al ancho del QR (0.28–0.34 recomendado)
    - logo_scale: tamaño del logo respecto al hueco (0.7–0.85 recomendado)
    """
    # 1) QR base con alta corrección de errores
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=box_size, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    qr_w, qr_h = qr_img.size

    # 2) Hueco central
    cw = ch = int(qr_w * clear_ratio)
    cx, cy = (qr_w - cw) // 2, (qr_h - ch) // 2
    draw = ImageDraw.Draw(qr_img)
    radius = max(6, cw // 10)  # esquinas redondeadas
    try:
        draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=radius, fill="white")
    except Exception:
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill="white")

    # 3) Logo centrado (opcional)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            size = int(cw * logo_scale)
            logo = logo.resize((size, size), Image.LANCZOS)
            lx, ly = cx + (cw - size) // 2, cy + (ch - size) // 2
            qr_img.paste(logo, (lx, ly), mask=logo)
        except Exception as e:
            print(f"[ADVERTENCIA] No se pudo incrustar el logo en el QR: {e}")

    qr_img.save(out_path)

def main():
    csv_path = os.path.join(ROOT, "data", "people.csv")
    rows = read_csv_rows(csv_path)
    logo2 = find_logo2_path()

    for row in rows:
        slug = (row.get("slug") or "").strip()
        if not slug:
            raise ValueError("Falta la columna 'slug' o está vacía en alguna fila.")

        out_dir = os.path.join(ROOT, "output", slug)
        ensure_dir(out_dir)

        # URL del perfil (para el QR)
        profile_url = f"{BASE_URL}/{slug}/index.html" if BASE_URL else f"./{slug}/index.html"

        # QR con hueco y logo
        create_qr_with_logo_and_clear_area(
            url=profile_url,
            out_path=os.path.join(out_dir, "qr.png"),
            logo_path=logo2,
            box_size=10,
            border=4,
            clear_ratio=0.30,  # ajusta 0.28–0.34 si quieres más/menos hueco
            logo_scale=0.78    # ajusta 0.7–0.85 para tamaño del logo dentro del hueco
        )

        # Foto del perfil
        requested_photo = (row.get("photo") or "").strip()
        real_photo_name = find_photo_name(requested_photo)
        if not real_photo_name:
            raise FileNotFoundError(
                f"No se encontró la foto '{requested_photo}' ni '{FALLBACK}' en assets/photos."
            )
        photo_src = f"../../assets/photos/{real_photo_name}"

        # Render HTML
        html = tpl.render(
            name=(row.get("name") or "").strip(),
            role=(row.get("role") or "").strip(),
            slug=slug,
            instagram=(row.get("instagram") or "").strip(),
            twitter=(row.get("twitter") or "").strip(),
            linkedin=(row.get("linkedin") or "").strip(),
            website=(row.get("website") or "").strip(),
            vcard_url=(row.get("vcard_url") or "").strip(),
            photo_src=photo_src
        )
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as h:
            h.write(html)

        print(f"[OK] {slug} → foto: {real_photo_name} | logo2 en QR: {'sí' if logo2 else 'no'}")

if __name__ == "__main__":
    main()
    print("Listo. Revisa la carpeta 'output/'.")
