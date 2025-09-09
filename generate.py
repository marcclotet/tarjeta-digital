import os, csv, shutil
from jinja2 import Environment, FileSystemLoader
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw

# ===================== Config =====================
# Si ya tienes dominio/URL pública, rellénalo:
BASE_URL = "https://marcclotet.github.io/tarjeta-digital/"  # p.ej. "https://voucler.github.io/tarjeta-digital" o "https://cards.voucler.com"

ROOT = os.path.dirname(__file__)
TPL_DIR = os.path.join(ROOT, "templates")
ASSETS_LOCAL = os.path.join(ROOT, "assets")            # assets de trabajo
ASSETS_PHOTOS = os.path.join(ASSETS_LOCAL, "photos")   # fotos de personas
OUTPUT_DIR = os.path.join(ROOT, "output")              # salida de generación
DOCS_DIR = os.path.join(ROOT, "docs")                  # carpeta publicada (GitHub Pages)

FALLBACK_PHOTO = "placeholder.jpg"
CANDIDATE_EXTS = [".jpg", ".jpeg", ".png", ".webp"]

env = Environment(loader=FileSystemLoader(TPL_DIR))
tpl = env.get_template("card.html")

# ===================================================

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def listdir_ci(path):
    """Devuelve {nombre_lower: nombre_real} (case-insensitive)."""
    return {f.lower(): f for f in os.listdir(path)} if os.path.isdir(path) else {}

def find_photo_name(requested: str) -> str:
    """Encuentra la foto en assets/photos de forma tolerante a mayúsculas/extensión."""
    files_ci = listdir_ci(ASSETS_PHOTOS)
    if not requested:
        return files_ci.get(FALLBACK_PHOTO.lower(), "")
    req = requested.strip().lower()
    if req in files_ci:
        return files_ci[req]
    name, ext = os.path.splitext(req)
    has_ext = ext in CANDIDATE_EXTS
    if has_ext:
        for e in CANDIDATE_EXTS:
            alt = name + e
            if alt in files_ci:
                return files_ci[alt]
    else:
        for e in CANDIDATE_EXTS:
            alt = name + e
            if alt in files_ci:
                return files_ci[alt]
    return files_ci.get(FALLBACK_PHOTO.lower(), "")

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
    """Busca assets/logo2.(png|jpg|jpeg|webp)."""
    files_ci = listdir_ci(ASSETS_LOCAL)
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        k = f"logo2{ext}".lower()
        if k in files_ci:
            return os.path.join(ASSETS_LOCAL, files_ci[k])
    return ""

def create_qr_with_logo_and_clear_area(url, out_path, logo_path=None,
                                       box_size=10, border=4,
                                       clear_ratio=0.30, logo_scale=0.78):
    """
    Genera QR con error alto y hueco blanco central; pega logo centrado (si existe).
    """
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=box_size, border=border)
    qr.add_data(url); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    w, h = qr_img.size
    cw = ch = int(w * clear_ratio)
    cx, cy = (w - cw) // 2, (h - ch) // 2
    draw = ImageDraw.Draw(qr_img)
    radius = max(6, cw // 10)
    try:
        draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=radius, fill="white")
    except Exception:
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill="white")

    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            size = int(cw * logo_scale)
            logo = logo.resize((size, size), Image.LANCZOS)
            lx, ly = cx + (cw - size) // 2, cy + (ch - size) // 2
            qr_img.paste(logo, (lx, ly), mask=logo)
        except Exception as e:
            print(f"[ADVERTENCIA] Logo en QR: {e}")

    qr_img.save(out_path)

def render_card(row, logo2_path):
    slug = (row.get("slug") or "").strip()
    if not slug:
        raise ValueError("Falta 'slug' en alguna fila del CSV.")
    out_dir = os.path.join(OUTPUT_DIR, slug)
    ensure_dir(out_dir)

    # URL del perfil para el QR
    profile_url = f"{BASE_URL}/{slug}/index.html" if BASE_URL else f"./{slug}/index.html"

    # QR
    create_qr_with_logo_and_clear_area(
        url=profile_url,
        out_path=os.path.join(out_dir, "qr.png"),
        logo_path=logo2_path
    )

    # Foto
    requested_photo = (row.get("photo") or "").strip()
    real_photo_name = find_photo_name(requested_photo)
    if not real_photo_name:
        raise FileNotFoundError(f"No se encontró la foto '{requested_photo}' ni '{FALLBACK_PHOTO}'.")

    # Ruta desde output/<slug>/ hacia assets/photos/<real>
    photo_src = f"../../assets/photos/{real_photo_name}"

    # Render
    html = tpl.render(
        name=(row.get("name") or "").strip(),
        role=(row.get("role") or "").strip(),
        slug=slug,
        instagram=(row.get("instagram") or "").strip(),
        twitter=(row.get("twitter") or "").strip(),
        linkedin=(row.get("linkedin") or "").strip(),
        website=(row.get("website") or "").strip(),
        email=(row.get("email") or "").strip(),
        phone=(row.get("phone") or "").strip(),
        vcard_url=(row.get("vcard_url") or "").strip(),
        photo_src=photo_src
    )
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as h:
        h.write(html)

    print(f"[OK] {slug} → foto: {real_photo_name} | logo2 en QR: {'sí' if logo2_path else 'no'}")
    return slug

def copytree(src, dst):
    """shutil.copytree con dirs_exist_ok=True para Python <3.8 compat."""
    if os.path.isdir(src):
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target = os.path.join(dst, rel) if rel != "." else dst
            os.makedirs(target, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(target, f))

def publish_to_docs(slugs):
    """
    Copia output/<slug>/ → docs/<slug>/
    Copia assets/     → docs/assets/
    Corrige rutas en docs/<slug>/index.html  (../../assets/ → assets/)
    """
    ensure_dir(DOCS_DIR)

    # 1) Copiar/actualizar tarjetas
    for slug in slugs:
        src = os.path.join(OUTPUT_DIR, slug)
        dst = os.path.join(DOCS_DIR, slug)
        copytree(src, dst)

    # 2) Sincronizar assets completos
    assets_dst = os.path.join(DOCS_DIR, "assets")
    copytree(ASSETS_LOCAL, assets_dst)

    # 3) Corregir rutas en todos los index.html publicados
    for slug in slugs:
        idx = os.path.join(DOCS_DIR, slug, "index.html")
        if os.path.isfile(idx):
            with open(idx, encoding="utf-8") as f:
                html = f.read()
                # desde docs/<slug>/ a docs/assets/ → ../assets/
            html = html.replace("../../assets/", "../assets/")
            with open(idx, "w", encoding="utf-8") as f:
                f.write(html)

def main():
    ensure_dir(OUTPUT_DIR)
    rows = read_csv_rows(os.path.join(ROOT, "data", "people.csv"))
    logo2 = find_logo2_path()

    slugs_generated = []
    for row in rows:
        slug = render_card(row, logo2)
        slugs_generated.append(slug)

    # Publicación auto en docs/
    publish_to_docs(slugs_generated)
    print("Publicación en 'docs/' actualizada.")

if __name__ == "__main__":
    main()
    print("Listo. Revisa 'output/' y 'docs/'.")
