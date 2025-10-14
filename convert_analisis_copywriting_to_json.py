import os
import re
import json
from typing import Dict, List


def strip_tags(html: str) -> str:
    """Elimina etiquetas HTML básicas para facilitar el parseo.
    Nota: Simple pero suficiente para la estructura generada.
    """
    # Reemplazar <br> por saltos de línea para preservar separación
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Quitar todas las etiquetas
    return re.sub(r"<[^>]+>", "", html)


def parse_meta(html: str) -> Dict:
    """Extrae fecha, imágenes analizadas y modelo del bloque .meta."""
    meta: Dict = {
        "fecha": None,
        "imagenes_analizadas": None,
        "modelo": None,
    }
    # Regex sobre HTML crudo para mayor precisión
    m_fecha = re.search(r"<strong>\s*Fecha:\s*</strong>\s*([^<]+)<br>", html)
    m_imgs = re.search(r"<strong>\s*Imágenes analizadas:\s*</strong>\s*(\d+)<br>", html)
    m_modelo = re.search(r"<strong>\s*Modelo:\s*</strong>\s*([^<]+)", html)

    if m_fecha:
        meta["fecha"] = m_fecha.group(1).strip()
    if m_imgs:
        try:
            meta["imagenes_analizadas"] = int(m_imgs.group(1).strip())
        except ValueError:
            meta["imagenes_analizadas"] = m_imgs.group(1).strip()
    if m_modelo:
        meta["modelo"] = m_modelo.group(1).strip()

    return meta


def parse_content(content_html: str) -> Dict:
    """Parsea el bloque de contenido en estructura JSON."""
    text = strip_tags(content_html)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    data: Dict = {
        "viñetas": [],
        "faq": [],
        "detalles_tecnicos": {},
        "video_section": {},
    }

    section = None
    for line in lines:
        # Detectar encabezados estilo '### 1. Viñetas'
        if line.startswith("### "):
            low = line.lower()
            if "viñetas" in low:
                section = "viñetas"
                continue
            if "faq" in low:
                section = "faq"
                continue
            if "detalles" in low:
                section = "detalles"
                continue
            if "video" in low:
                section = "video"
                continue

        # Procesar items de cada sección
        if line.startswith("- "):
            item = line[2:].strip()
            if section == "viñetas":
                data["viñetas"].append(item)
            elif section == "faq":
                # Formato esperado: "¿Pregunta? Respuesta"
                m = re.match(r"^(.+\?)\s*(.+)$", item)
                if m:
                    data["faq"].append({"pregunta": m.group(1).strip(), "respuesta": m.group(2).strip()})
                else:
                    # Fallback: todo como respuesta sin pregunta detectada
                    data["faq"].append({"pregunta": None, "respuesta": item})
            elif section == "detalles":
                # Formato: "Clave: Valor"
                m = re.match(r"^([^:]+):\s*(.+)$", item)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    data["detalles_tecnicos"][key] = val
                else:
                    # Fallback: agregar como línea suelta
                    data["detalles_tecnicos"].setdefault("__otros__", []).append(item)
            elif section == "video":
                # Formato: "Title: ..." / "Body: ..."
                m = re.match(r"^([^:]+):\s*(.+)$", item)
                if m:
                    key = m.group(1).strip().lower()
                    val = m.group(2).strip()
                    if key == "title":
                        data["video_section"]["title"] = val
                    elif key == "body":
                        data["video_section"]["body"] = val
                    else:
                        data["video_section"][key] = val
                else:
                    data["video_section"].setdefault("__otros__", []).append(item)

    return data


def convert_file(input_path: str) -> Dict:
    """Convierte el HTML de análisis a JSON estructurado."""
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"No se encontró el archivo: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Extraer bloques
    # meta
    meta_block_match = re.search(r"<div class='meta'>(.*?)</div>", html, flags=re.DOTALL)
    meta_block = meta_block_match.group(1) if meta_block_match else ""
    meta = parse_meta(meta_block)

    # content
    content_block_match = re.search(r"<div class='content'>(.*?)</div>", html, flags=re.DOTALL)
    content_block = content_block_match.group(1) if content_block_match else ""
    contenido = parse_content(content_block)

    result = {
        "metadata": meta,
        "contenido": contenido,
        "fuente": os.path.basename(input_path),
    }
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convierte analisis_copywriting_openai.html a JSON y TXT")
    parser.add_argument("input", help="Ruta al archivo HTML analisis_copywriting_openai.html")
    args = parser.parse_args()

    data = convert_file(args.input)

    base_dir = os.path.dirname(os.path.abspath(args.input))
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    json_path = os.path.join(base_dir, f"{base_name}.json")
    txt_path = os.path.join(base_dir, f"{base_name}.txt")

    # Guardar JSON (UTF-8, indentado)
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    # Guardar TXT con el mismo contenido JSON
    with open(txt_path, "w", encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)

    print(f"✅ JSON generado: {json_path}")
    print(f"✅ TXT generado:  {txt_path}")


if __name__ == "__main__":
    main()