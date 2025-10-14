#!/usr/bin/env python3
import os
import re
import json
import argparse
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv


load_dotenv()


ABSENCE_PHRASES = {
    "no observado en imágenes",
    "no disponible",
    "no disponible en imágenes",
    "sin dato",
}

# NOTA: SEC5_BODY_DESIRED ha sido eliminado.
# Ahora sec5_body usa el contenido generado por OpenAI (video_body) en lugar de texto hardcodeado.
# Texto anterior (para referencia):
# "Sumérgete en una experiencia de armado que combina creatividad y relajación. "
# "Con una altura de 33.5 cm, este ramo se convierte en el centro de atención de cualquier habitación.\n\n"
# "Detalles como los pétalos realistas y el jarrón elegante elevan su valor de exhibición. "
# "Ideal para coleccionistas y entusiastas de la decoración temática."


def markdown_to_rich_text_json(text: str) -> Dict:
    """Convierte una línea de texto Markdown a estructura JSON de rich_text_field.
    Soporta **negritas** aplicando {"bold": true} en los segmentos.
    """
    # Normalizar saltos de línea múltiples en espacio simple dentro de párrafos
    line = text.replace("\r", "").replace("\n", " ").strip()
    parts = re.split(r"(\*\*)", line)
    nodes: List[Dict] = []
    bold = False
    for p in parts:
        if p == "**":
            bold = not bold
            continue
        if not p:
            continue
        node: Dict = {"type": "text", "value": p}
        if bold:
            node["bold"] = True
        nodes.append(node)
    return {"type": "root", "children": [{"type": "paragraph", "children": nodes}]}


def markdown_to_rich_text_json_paragraphs(text: str, enforce_two: bool = False) -> Dict:
    """Convierte texto Markdown en rich_text_field con múltiples párrafos.
    - Divide por saltos de línea dobles (\n\n) para separar párrafos.
    - Dentro de cada párrafo, colapsa saltos de línea simples a espacios.
    - Si enforce_two=True y solo hay un párrafo, intenta dividir en dos por oraciones.
    """
    cleaned = text.replace("\r", "")
    paras = [p.strip() for p in re.split(r"\n{2,}", cleaned.strip()) if p.strip()]
    if enforce_two and len(paras) < 2 and paras:
        # Intentar dividir el único párrafo en dos por oraciones.
        sentences = re.split(r"(?<=[\.!?])\s+", paras[0])
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) >= 2:
            mid = max(1, len(sentences) // 2)
            paras = [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
    children: List[Dict] = []
    for para in paras:
        # Reutilizar lógica de negritas y texto del helper existente
        line = para.replace("\n", " ")
        parts = re.split(r"(\*\*)", line)
        nodes: List[Dict] = []
        bold = False
        for p in parts:
            if p == "**":
                bold = not bold
                continue
            if not p:
                continue
            node: Dict = {"type": "text", "value": p}
            if bold:
                node["bold"] = True
            nodes.append(node)
        children.append({"type": "paragraph", "children": nodes})
    # Si no se detectaron párrafos, retornar un root con párrafo vacío
    if not children:
        children = [{"type": "paragraph", "children": [{"type": "text", "value": ""}]}]
    return {"type": "root", "children": children}


def parse_openai_markdown(content_md: str) -> Dict:
    """Parsea el contenido Markdown en secciones estructuradas: viñetas, faq respuestas, detalles, video."""
    # Separar por encabezados ###
    # Usamos regex para capturar secciones 1..4
    sections = {}
    pattern = re.compile(r"^###\s+(\d+)\.\s+([^\n]+)\n", re.MULTILINE)
    indices = []
    for m in pattern.finditer(content_md):
        indices.append((m.start(), m.group(1), m.group(2)))
    indices.append((len(content_md), None, None))

    for i in range(len(indices) - 1):
        start, num, title = indices[i]
        end, _, _ = indices[i + 1]
        body = content_md[start:end]
        sections[num] = {"title": title, "body": body}

    # Viñetas: líneas que comienzan con "- " en sección 1
    bullets: List[str] = []
    sec1 = sections.get("1", {}).get("body", "")
    for line in sec1.splitlines():
        if line.strip().startswith("- "):
            bullets.append(line.strip()[2:].strip())

    # FAQ: tomar respuestas, ignorando preguntas (líneas con "- **Pregunta**")
    faq_answers: List[str] = []
    sec2 = sections.get("2", {}).get("body", "")
    # Patrón: Bullet de pregunta seguido por líneas de respuesta (posible indentación o doble espacio para salto)
    faq_blocks = re.split(r"\n-\s+\*\*", sec2)
    # faq_blocks[0] es preámbulo antes del primer bullet; los siguientes empiezan con texto de pregunta
    for blk in faq_blocks[1:]:
        # Separar la pregunta de la respuesta y tomar solo la respuesta.
        # Casos soportados:
        # 1) "Pregunta**\nRespuesta"
        # 2) "Pregunta**: Respuesta" (misma línea tras ":")
        # 3) "Pregunta** - Respuesta" (guion tras cierre bold)
        # 4) "Pregunta:** Respuesta" (dos puntos dentro del bold, respuesta tras cerrar **)
        # 5) "Pregunta**  Respuesta" (espacio tras cierre bold)
        parts = re.split(r"\*\*\s*\n", blk, maxsplit=1)
        if len(parts) == 2:
            answer = parts[1]
        else:
            parts = re.split(r"\*\*\s*[:\-–—]\s*", blk, maxsplit=1)
            if len(parts) == 2:
                answer = parts[1]
            else:
                parts = re.split(r"\*\*\s+", blk, maxsplit=1)
                answer = parts[1] if len(parts) == 2 else blk
        # Limpiar respuesta: unir líneas con espacios y recortar
        answer = re.sub(r"\s+", " ", answer).strip()
        if answer:
            faq_answers.append(answer)

    # Detalles Técnicos: key-value por líneas "- **Campo:** Valor"
    # Soporta tanto **Campo**: como **Campo:** (: dentro o fuera de **)
    details: Dict[str, Optional[str]] = {}
    sec3 = sections.get("3", {}).get("body", "")
    for line in sec3.splitlines():
        # Probar primero con : dentro de ** → **Campo:**
        m = re.match(r"^-\s+\*\*([^*]+?):\*\*\s*(.+)$", line.strip())
        if not m:
            # Si no match, probar con : fuera de ** → **Campo**:
            m = re.match(r"^-\s+\*\*([^:*]+)\*\*:\s*(.+)$", line.strip())
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            details[key] = val

    # Video Section: Title y Body
    video_title = None
    video_body_lines: List[str] = []
    sec4 = sections.get("4", {}).get("body", "")
    first_bullet_processed = False

    for line in sec4.splitlines():
        # Ignorar encabezados dentro de la sección de video, por ejemplo '### 4. ...'
        if line.strip().startswith("###"):
            continue

        # Procesar líneas que empiecen con "- "
        if line.strip().startswith("- "):
            # PRIMERO: Verificar si contiene patrón de título (soporta 3 formatos)
            # Formato 1: **Title:** (: dentro)  → **Title:**
            # Formato 2: **Title**: (: fuera)  → **Title**:
            # Formato 3: **Title**:  (: pegado) → **Title**:
            if re.search(r"\*\*[Tt]itle", line.strip()):
                # Probar formato 1: : dentro de ** → **Title:**
                mt = re.search(r"\*\*[Tt]itle[^:]*:\*\*\s*(.+)$", line.strip(), re.IGNORECASE)
                if not mt:
                    # Probar formato 2 y 3: : fuera de ** → **Title**: o **Title**:
                    mt = re.search(r"\*\*[Tt]itle\*\*\s*:\s*(.+)$", line.strip(), re.IGNORECASE)
                if mt:
                    video_title = mt.group(1).strip()
                    first_bullet_processed = True  # Marcar que ya procesamos el primer bullet
            else:
                # Verificar si es un bullet completamente en negritas (posible título)
                # Patrón: - **texto** (sin más texto después)
                bold_only_match = re.match(r"^-\s+\*\*(.+?)\*\*\s*$", line.strip())
                if bold_only_match and not first_bullet_processed:
                    extracted_text = bold_only_match.group(1).strip()
                    # Verificar que no sea una palabra reservada
                    is_reserved_word = re.search(r'(?i)(body|title|título|video):', extracted_text)
                    if not is_reserved_word:
                        # Primer bullet completamente en negritas = TÍTULO
                        video_title = extracted_text
                        first_bullet_processed = True
                else:
                    # Verificar si es línea de body marcador (ignorar cualquier variante de **Body**)
                    # Soporta **Body**, **Body:**, **Body:** (: dentro o fuera)
                    if re.search(r"^\*\*[Bb]ody[^*]*\*\*", line.strip()):
                        # Marcar que empezamos a capturar el body (línea de marcador, ignorar)
                        pass
                    else:
                        # Bullet normal = parte del BODY
                        # Limpiar múltiples niveles de bullets (espacios + guiones)
                        content = line.strip()
                        while content.startswith('- '):
                            content = content[2:].strip()

                        if content:
                            # Filtrar líneas que no deben ir al body
                            if not re.search(r'\*\*[Tt]itle[^*]*\*\*', content) and \
                               not re.search(r'\*\*[Vv]ideo[^*]*\*\*', content) and \
                               not re.search(r'^\*\*[Bb]ody[^*]*\*\*', content):
                                video_body_lines.append(content)
        else:
            # Líneas sin bullet pero dentro del body
            if video_body_lines is not None and line.strip():
                # También limpiar estas líneas de posibles patterns no deseados
                content = line.strip()
                if not re.search(r'\*\*[Tt]itle[^*]*\*\*', content) and \
                   not re.search(r'\*\*[Vv]ideo[^*]*\*\*', content) and \
                   not re.search(r'^\*\*[Bb]ody[^*]*\*\*', content):
                    video_body_lines.append(content)

    video_body = "\n".join(video_body_lines).strip() if video_body_lines else None

    return {
        "bullets": bullets,
        "faq_answers": faq_answers,
        "details": details,
        "video_title": video_title,
        "video_body": video_body,
    }


def normalize_numeric(value: Optional[str], integer: bool = False) -> Optional[str]:
    if value is None:
        return None
    v = value.strip().lower()
    if not v or v in ABSENCE_PHRASES:
        return None
    # Extraer número
    m = re.search(r"(-?\d+(?:[\.,]\d+)?)", v)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    if integer:
        try:
            return str(int(float(num)))
        except Exception:
            return None
    return num


def fetch_metafields_ids(shop: str, access_token: str, product_id: int) -> List[Dict]:
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-07")
    url = f"https://{shop}.myshopify.com/admin/api/{api_version}/metafields.json"
    params = {"owner_id": str(product_id), "owner_resource": "product", "limit": "250"}
    headers = {"Accept": "application/json", "X-Shopify-Access-Token": access_token}
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json().get("metafields", [])


def build_id_map(metafields: List[Dict]) -> Dict[str, int]:
    """Construye un mapa de key -> id. Prefiere namespace 'custom' cuando hay duplicados."""
    ids_by_key: Dict[str, Tuple[int, str]] = {}
    for m in metafields:
        key = m.get("key")
        mid = m.get("id")
        ns = m.get("namespace") or ""
        if not key or not mid:
            continue
        if key not in ids_by_key:
            ids_by_key[key] = (mid, ns)
        else:
            # preferir 'custom'
            prev_id, prev_ns = ids_by_key[key]
            if prev_ns != "custom" and ns == "custom":
                ids_by_key[key] = (mid, ns)
    return {k: v[0] for k, v in ids_by_key.items()}


def generate_put_updates(ids_map: Dict[str, int], parsed: Dict) -> List[Dict]:
    updates: List[Dict] = []

    # Viñetas: vineta_1..vineta_5 (rich_text_field -> json_string)
    for idx in range(5):
        if idx < len(parsed["bullets"]):
            key = f"vineta_{idx + 1}"
            if key in ids_map:
                rtf = markdown_to_rich_text_json(parsed["bullets"][idx])
                updates.append({"id": ids_map[key], "value": json.dumps(rtf, separators=(",", ":")), "value_type": "json_string"})

    # FAQ: faq_2..faq_4 (usar respuestas, rich_text_field -> json_string)
    for idx in range(3):
        if idx < len(parsed["faq_answers"]):
            key = f"faq_{idx + 2}"
            if key in ids_map:
                rtf = markdown_to_rich_text_json(parsed["faq_answers"][idx])
                updates.append({"id": ids_map[key], "value": json.dumps(rtf, separators=(",", ":")), "value_type": "json_string"})

    # Detalles técnicos: number_decimal / number_integer
    details = parsed["details"]
    mapping_numeric = {
        "ancho": (False, "string"),
        "longitud": (False, "string"),
        "alto": (False, "string"),
        "piezas": (True, "integer"),
    }
    for field, (is_int, value_type) in mapping_numeric.items():
        if field in ids_map:
            val = normalize_numeric(details.get(field), integer=is_int)
            if val is not None:
                updates.append({"id": ids_map[field], "value": val, "value_type": value_type})

    # Escala: single_line_text_field -> string
    if "escala" in ids_map:
        escala_val = details.get("escala")
        if escala_val and escala_val.strip().lower() not in ABSENCE_PHRASES:
            v = escala_val.strip()
            updates.append({"id": ids_map["escala"], "value": v, "value_type": "string"})

    # Video Section: sec5_title (single_line_text_field -> string), sec5_body (rich_text_field -> json_string)
    if "sec5_title" in ids_map and parsed.get("video_title"):
        updates.append({"id": ids_map["sec5_title"], "value": parsed["video_title"].strip(), "value_type": "string"})
    if "sec5_body" in ids_map and parsed.get("video_body"):
        # Usar el contenido generado por OpenAI (video_body) en lugar de texto hardcodeado
        rtf_body = markdown_to_rich_text_json_paragraphs(parsed["video_body"], enforce_two=True)
        updates.append({"id": ids_map["sec5_body"], "value": json.dumps(rtf_body, separators=(",", ":")), "value_type": "json_string"})

    return updates


def execute_put_updates(shop: str, access_token: str, updates: List[Dict]) -> List[Dict]:
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-07")
    headers = {"Content-Type": "application/json", "Accept": "application/json", "X-Shopify-Access-Token": access_token}
    results: List[Dict] = []
    for upd in updates:
        mid = upd["id"]
        url = f"https://{shop}.myshopify.com/admin/api/{api_version}/metafields/{mid}.json"
        payload = {"metafield": {"id": upd["id"], "value": upd["value"], "value_type": upd["value_type"]}}
        try:
            resp = requests.put(url, headers=headers, json=payload, timeout=60)
            ok = resp.status_code < 300
            body = None
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}
            results.append({"id": mid, "status": resp.status_code, "ok": ok, "response": body})
        except requests.RequestException as e:
            results.append({"id": mid, "status": 0, "ok": False, "error": str(e)})
    return results


def build_missing_metafields_inputs(product_gid: str, ids_map: Dict[str, int], parsed: Dict) -> List[Dict]:
    """Construye entradas para metafieldsSet para claves que no existen en ids_map."""
    inputs: List[Dict] = []

    # Viñetas
    for idx in range(5):
        key = f"vineta_{idx + 1}"
        if key not in ids_map and idx < len(parsed["bullets"]):
            rtf = markdown_to_rich_text_json(parsed["bullets"][idx])
            inputs.append({
                "ownerId": product_gid,
                "namespace": "custom",
                "key": key,
                "type": "rich_text_field",
                "value": json.dumps(rtf, separators=(",", ":")),
            })

    # FAQ
    for idx in range(3):
        key = f"faq_{idx + 2}"
        if key not in ids_map and idx < len(parsed["faq_answers"]):
            rtf = markdown_to_rich_text_json(parsed["faq_answers"][idx])
            inputs.append({
                "ownerId": product_gid,
                "namespace": "custom",
                "key": key,
                "type": "rich_text_field",
                "value": json.dumps(rtf, separators=(",", ":")),
            })

    # Detalles técnicos
    details = parsed["details"]
    if "ancho" not in ids_map:
        v = normalize_numeric(details.get("ancho"), integer=False)
        if v is not None:
            inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "ancho", "type": "number_decimal", "value": v})
    if "longitud" not in ids_map:
        v = normalize_numeric(details.get("longitud"), integer=False)
        if v is not None:
            inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "longitud", "type": "number_decimal", "value": v})
    if "alto" not in ids_map:
        v = normalize_numeric(details.get("alto"), integer=False)
        if v is not None:
            inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "alto", "type": "number_decimal", "value": v})
    if "piezas" not in ids_map:
        v = normalize_numeric(details.get("piezas"), integer=True)
        if v is not None:
            inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "piezas", "type": "number_integer", "value": v})

    if "escala" not in ids_map:
        escala_val = details.get("escala")
        if escala_val and escala_val.strip().lower() not in ABSENCE_PHRASES:
            inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "escala", "type": "single_line_text_field", "value": escala_val.strip()})

    # Video
    if "sec5_title" not in ids_map and parsed.get("video_title"):
        inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "sec5_title", "type": "single_line_text_field", "value": parsed["video_title"].strip()})
    if "sec5_body" not in ids_map and parsed.get("video_body"):
        rtf_body = markdown_to_rich_text_json_paragraphs(parsed["video_body"], enforce_two=True)
        inputs.append({"ownerId": product_gid, "namespace": "custom", "key": "sec5_body", "type": "rich_text_field", "value": json.dumps(rtf_body, separators=(",", ":"))})

    return inputs


def metafields_set(shop: str, access_token: str, inputs: List[Dict]) -> Dict:
    """Ejecuta la mutación metafieldsSet en lotes de 25."""
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-07")
    url = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"
    headers = {"Content-Type": "application/json", "Accept": "application/json", "X-Shopify-Access-Token": access_token}

    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id key namespace type value }
        userErrors { field message }
      }
    }
    """

    def chunks(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i:i+size]

    all_results = {"updated": [], "errors": []}
    for batch in chunks(inputs, 25):
        payload = {"query": mutation, "variables": {"metafields": batch}}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        try:
            data = resp.json()
        except Exception:
            all_results["errors"].append({"status": resp.status_code, "raw": resp.text})
            continue
        if "errors" in data and data["errors"]:
            all_results["errors"].extend(data["errors"])
        result = data.get("data", {}).get("metafieldsSet", {})
        if result.get("userErrors"):
            all_results["errors"].extend(result["userErrors"])
        if result.get("metafields"):
            all_results["updated"].extend(result["metafields"])
    return all_results


def ensure_metafield_definitions(shop: str, access_token: str, definitions: List[Dict]) -> Dict:
    """Crea definiciones de metafields necesarias para PRODUCT/namespace custom.
    Ignora errores de duplicado y agrega detalles de errores para diagnóstico.
    """
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-07")
    url = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"
    headers = {"Content-Type": "application/json", "Accept": "application/json", "X-Shopify-Access-Token": access_token}

    mutation = """
    mutation metafieldDefinitionCreate($definition: MetafieldDefinitionInput!) {
      metafieldDefinitionCreate(definition: $definition) {
        createdDefinition { id key namespace type ownerType }
        userErrors { field message }
      }
    }
    """

    results = {"created": [], "errors": []}
    for d in definitions:
        payload = {"query": mutation, "variables": {"definition": d}}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        try:
            data = resp.json()
        except Exception:
            results["errors"].append({"status": resp.status_code, "raw": resp.text})
            continue
        if data.get("errors"):
            results["errors"].extend(data["errors"])  # GraphQL-level errors
        out = data.get("data", {}).get("metafieldDefinitionCreate", {})
        if out.get("userErrors"):
            # Muchos de estos pueden ser "already exists"; los mantenemos para diagnóstico
            results["errors"].extend(out["userErrors"])
        if out.get("createdDefinition"):
            results["created"].append(out["createdDefinition"])
    return results


def main():
    parser = argparse.ArgumentParser(description="Genera y ejecuta PUTs de metafields a partir de Markdown de OpenAI")
    parser.add_argument("--product-id", type=int, required=True, help="ID numérico del producto")
    parser.add_argument("--input-json", type=str, required=True, help="Ruta al JSON de entrada con 'content' en Markdown")
    parser.add_argument("--shop", type=str, default=os.getenv("SHOPIFY_SHOP"), help="Subdominio de la tienda Shopify")
    parser.add_argument("--token", type=str, default=os.getenv("SHOPIFY_ACCESS_TOKEN"), help="Access token de Shopify")
    parser.add_argument("--ids-json", type=str, default=None, help="Ruta a JSON con mapa key->id; si no se provee, se consultará por REST")
    parser.add_argument("--out-json", type=str, default=None, help="Ruta para guardar los updates generados")
    args = parser.parse_args()

    if not args.shop or not args.token:
        raise SystemExit("Debes proporcionar SHOPIFY_SHOP y SHOPIFY_ACCESS_TOKEN vía args o .env")

    with open(args.input_json, "r", encoding="utf-8") as f:
        openai_input = json.load(f)
    content_md = openai_input.get("content") or ""
    if not content_md.strip():
        raise SystemExit("El JSON de entrada no contiene 'content' con Markdown")

    parsed = parse_openai_markdown(content_md)

    if args.ids_json:
        with open(args.ids_json, "r", encoding="utf-8") as f:
            ids_map = json.load(f)
            if not isinstance(ids_map, dict):
                raise SystemExit("El archivo ids-json debe contener un objeto {key: id}")
    else:
        metafields = fetch_metafields_ids(args.shop, args.token, args.product_id)
        ids_map = build_id_map(metafields)

        # Asegurar definiciones de metafields para PRODUCT/namespace custom
        defs = []
        def add_def(key: str, type_: str, name: Optional[str] = None):
            defs.append({
                "name": name or key,
                "namespace": "custom",
                "key": key,
                "type": type_,
                "ownerType": "PRODUCT",
                "visibleToStorefront": False,
            })

        for k in [f"vineta_{i}" for i in range(1,6)]:
            add_def(k, "rich_text_field", name=f"Viñeta {k[-1]}")
        for k in [f"faq_{i}" for i in range(2,5)]:
            add_def(k, "rich_text_field", name=f"FAQ {k[-1]}")
        add_def("ancho", "number_decimal", name="Ancho")
        add_def("longitud", "number_decimal", name="Longitud")
        add_def("alto", "number_decimal", name="Alto")
        add_def("piezas", "number_integer", name="Piezas")
        add_def("escala", "single_line_text_field", name="Escala")
        add_def("sec5_title", "single_line_text_field", name="Sec5 Title")
        add_def("sec5_body", "rich_text_field", name="Sec5 Body")

        def_results = ensure_metafield_definitions(args.shop, args.token, defs)
        print(f"Definiciones creadas: {len(def_results.get('created', []))}, errores: {len(def_results.get('errors', []))}")
        if def_results.get("errors"):
            print("Detalles errores definiciones:")
            for e in def_results["errors"]:
                print(json.dumps(e, ensure_ascii=False))

        # Crear valores que falten via metafieldsSet
        product_gid = f"gid://shopify/Product/{args.product_id}"
        missing_inputs = build_missing_metafields_inputs(product_gid, ids_map, parsed)
        if missing_inputs:
            print(f"Creando {len(missing_inputs)} metafields ausentes via metafieldsSet...")
            mf_results = metafields_set(args.shop, args.token, missing_inputs)
            print(f"metafieldsSet resultados: updated={len(mf_results.get('updated', []))}, errors={len(mf_results.get('errors', []))}")
            if mf_results.get("errors"):
                print("Detalles errores metafieldsSet:")
                for e in mf_results["errors"]:
                    print(json.dumps(e, ensure_ascii=False))
            # Reconsultar IDs después de crear
            metafields = fetch_metafields_ids(args.shop, args.token, args.product_id)
            ids_map = build_id_map(metafields)

    updates = generate_put_updates(ids_map, parsed)

    if args.out_json:
        out_path = args.out_json
    else:
        out_path = os.path.join(os.getcwd(), f"put_updates_{args.product_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(updates, f, ensure_ascii=False, indent=2)
    print(f"Generados {len(updates)} updates en {out_path}")

    # Limpieza automática: borrar put_updates_* vacío
    if not updates:
        try:
            os.remove(out_path)
            print(f"Archivo de updates vacío eliminado: {out_path}")
        except OSError as e:
            print(f"Advertencia: no se pudo eliminar {out_path}: {e}")

    # Ejecutar PUTs y generar resultados solo si hay updates
    if updates:
        results = execute_put_updates(args.shop, args.token, updates)
        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"Actualizados {ok_count}/{len(results)} metafields")
        # Guardar resultados
        out_res = out_path.replace(".json", "_results.json")
        with open(out_res, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Resultados guardados en {out_res}")
    else:
        print("Sin updates; se omite ejecución de PUTs y archivo de resultados.")


if __name__ == "__main__":
    main()