#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv






# Cargar variables de entorno desde .env si existe
load_dotenv()

app = FastAPI(title="Shopify Productos API", version="0.1.0")


def get_env_credentials() -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Obtiene credenciales y tienda desde variables de entorno."""
    api_key = os.getenv("SHOPIFY_API_KEY")
    password = os.getenv("SHOPIFY_PASSWORD")
    shop = os.getenv("SHOPIFY_SHOP")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
    return api_key, password, shop, access_token


def parse_next_page_info(link_header: Optional[str]) -> Optional[str]:
    """Extrae page_info del header Link de Shopify para paginación cursor-based.

    Ejemplo de header:
    <https://example.myshopify.com/admin/api/2024-10/products.json?limit=250&page_info=eyJ...>; rel="next"
    """
    if not link_header:
        return None
    # Buscar el enlace con rel="next"
    matches = re.findall(r"<([^>]+)>;\s*rel=\"next\"", link_header)
    if not matches:
        return None
    next_url = matches[0]
    # Extraer page_info del query string
    page_info_match = re.search(r"[?&]page_info=([^&]+)", next_url)
    if page_info_match:
        return page_info_match.group(1)
    return None


def map_product(product: Dict) -> Dict:
    """Estructura los datos relevantes del producto en un formato claro."""
    variants = []
    for v in product.get("variants", []):
        variants.append({
            "id": v.get("id"),
            "title": v.get("title"),
            "sku": v.get("sku"),
            "price": v.get("price"),
            "compare_at_price": v.get("compare_at_price"),
            "weight": v.get("weight"),
            "weight_unit": v.get("weight_unit"),
            "inventory_quantity": v.get("inventory_quantity"),
            "barcode": v.get("barcode"),
        })

    images = []
    for img in product.get("images", []):
        images.append({
            "id": img.get("id"),
            "src": img.get("src"),
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
        })

    options = []
    for opt in product.get("options", []):
        options.append({
            "id": opt.get("id"),
            "name": opt.get("name"),
            "values": opt.get("values", []),
        })

    return {
        "id": product.get("id"),
        "title": product.get("title"),
        "body_html": product.get("body_html"),
        "vendor": product.get("vendor"),
        "product_type": product.get("product_type"),
        "status": product.get("status"),
        "tags": product.get("tags"),
        "handle": product.get("handle"),
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "published_at": product.get("published_at"),
        "variants": variants,
        "images": images,
        "options": options,
    }


def fetch_all_products(shop: str, api_key: Optional[str], password: Optional[str], access_token: Optional[str]) -> List[Dict]:
    """Recupera todos los productos de la tienda con paginación cursor-based (page_info)."""
    if not shop:
        raise HTTPException(status_code=400, detail="Debes especificar el subdominio de la tienda (shop).")

    # Permitir configurar la versión del Admin API via .env; por defecto usar una versión estable
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")
    base_endpoint = f"https://{shop}.myshopify.com/admin/api/{api_version}/products.json"
    params: Dict[str, str] = {"limit": "250"}
    headers: Dict[str, str] = {"Accept": "application/json"}
    auth: Optional[Tuple[str, str]] = None

    # Preferir token de acceso si existe; si no, usar API key y password (apps privadas)
    if access_token:
        headers["X-Shopify-Access-Token"] = access_token
    elif api_key and password:
        auth = (api_key, password)
    else:
        raise HTTPException(status_code=400, detail="Faltan credenciales de Shopify. Configura SHOPIFY_ACCESS_TOKEN o SHOPIFY_API_KEY y SHOPIFY_PASSWORD.")

    all_products: List[Dict] = []
    next_page_info: Optional[str] = None

    while True:
        if next_page_info:
            params["page_info"] = next_page_info
        else:
            params.pop("page_info", None)

        try:
            resp = requests.get(base_endpoint, headers=headers, params=params, auth=auth, timeout=60)
        except requests.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Error de red al contactar Shopify: {e}")

        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Autenticación con Shopify fallida. Verifica las credenciales.")
        if resp.status_code >= 400:
            # Propagar mensaje detallado
            try:
                err = resp.json()
            except Exception:
                err = {"error": resp.text}
            raise HTTPException(status_code=resp.status_code, detail={"message": "Error en Shopify", "response": err})

        data = resp.json()
        products = data.get("products", [])
        all_products.extend(products)

        link_header = resp.headers.get("Link")
        next_page_info = parse_next_page_info(link_header)
        if not next_page_info:
            break

    return all_products


def graphql_admin_query(shop: str, api_key: Optional[str], password: Optional[str], access_token: Optional[str], query: str, variables: Optional[Dict] = None) -> Dict:
    """Ejecuta una consulta GraphQL en el Admin API de Shopify.

    Soporta autenticación con token (`X-Shopify-Access-Token`) o basic auth (API key/password).
    """
    if not shop:
        raise HTTPException(status_code=400, detail="Debes especificar el subdominio de la tienda (shop).")

    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")
    endpoint = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"

    headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    auth: Optional[Tuple[str, str]] = None

    if access_token:
        headers["X-Shopify-Access-Token"] = access_token
    elif api_key and password:
        auth = (api_key, password)
    else:
        raise HTTPException(status_code=400, detail="Faltan credenciales de Shopify. Configura SHOPIFY_ACCESS_TOKEN o SHOPIFY_API_KEY y SHOPIFY_PASSWORD.")

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, auth=auth, timeout=60)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error de red al contactar Shopify (GraphQL): {e}")

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Autenticación con Shopify fallida (GraphQL). Verifica las credenciales y permisos.")
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"error": resp.text}
        raise HTTPException(status_code=resp.status_code, detail={"message": "Error en Shopify (GraphQL)", "response": err})

    data = resp.json()
    if "errors" in data and data["errors"]:
        # Propagar errores de GraphQL con detalle
        raise HTTPException(status_code=400, detail={"message": "Errores GraphQL", "errors": data["errors"]})
    return data.get("data", {})


def _normalize_metafield_value(value: Optional[object], mtype: str) -> Optional[str]:
    """Normaliza el valor al formato requerido por Shopify GraphQL para el tipo indicado.

    Retorna una cadena lista para usar en `metafieldsSet` o None si el valor es inválido/nulo.
    """
    if value is None:
        return None

    # Tipos numéricos: convertir a cadena, omitir vacíos/NaN
    if mtype in {"number_integer", "number_decimal"}:
        try:
            # Permitir strings numéricas
            if isinstance(value, str):
                v = value.strip()
                if not v:
                    return None
                # validar que es número
                float(v)
                return v
            # ints/floats
            if isinstance(value, (int, float)):
                return str(value)
            # otros (ej. Decimal)
            return str(value)
        except Exception:
            return None

    # Booleanos: "true"/"false"
    if mtype == "boolean":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "false"}:
                return v
        return None

    # URL: cadena no vacía
    if mtype == "url":
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    # Texto de una/múltiples líneas
    if mtype in {"single_line_text_field", "multi_line_text_field"}:
        if isinstance(value, str):
            v = value.strip()
            return v if v else None
        # Convertir otros tipos a cadena
        v = str(value).strip()
        return v if v else None

    # Rich text: debe ser JSON serializado
    if mtype == "rich_text_field":
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, separators=(",", ":"))
            except Exception:
                return None
        if isinstance(value, str):
            v = value.strip()
            if not v:
                return None
            # Si ya parece JSON, usar como está; de lo contrario, envolver como párrafo simple
            if v.startswith("{") or v.startswith("["):
                return v
            # Envolver texto plano como rich text mínimo
            minimal = {
                "type": "root",
                "children": [{"type": "paragraph", "children": [{"text": v}]}],
            }
            return json.dumps(minimal, separators=(",", ":"))
        return None

    # Por defecto: tratar como texto
    v = str(value).strip()
    return v if v else None


def _chunk_list(items: List[Dict], size: int = 25) -> List[List[Dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


@app.get("/")
def root() -> Dict:
    return {
        "name": "Shopify Productos API",
        "version": "0.1.0",
        "endpoints": [
            "GET /productos",
            "GET /productos_ui",
            "GET /metaobjects",
            "GET /productos_metaobjects",
            "GET /metaobjects_ui",
            "GET /productos_metaobjects_ui",
            "GET /productos_metafields",
            "GET /productos_metafields_ui",
            "POST /productos_metafields_upsert",
        ],
        "env": {
            "SHOPIFY_SHOP": bool(os.getenv("SHOPIFY_SHOP")),
            "SHOPIFY_API_KEY": bool(os.getenv("SHOPIFY_API_KEY")),
            "SHOPIFY_PASSWORD": bool(os.getenv("SHOPIFY_PASSWORD")),
            "SHOPIFY_ACCESS_TOKEN": bool(os.getenv("SHOPIFY_ACCESS_TOKEN")),
            "SHOPIFY_API_VERSION": os.getenv("SHOPIFY_API_VERSION", "2024-10"),
        },
        "usage": "Invoca GET /productos?shop=<subdominio> si no configuraste SHOPIFY_SHOP en .env. Para una vista HTML ordenada, visita /productos_ui. Para metaobjetos por tipo: /metaobjects?type=<tipo>. Para metaobjetos referenciados por producto: /productos_metaobjects?product_id=<id>",
    }


@app.get("/productos")
def listar_productos(shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)")) -> JSONResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    productos_raw = fetch_all_products(target_shop, api_key, password, access_token)
    productos_mapped = [map_product(p) for p in productos_raw]

    result = {
        "shop": target_shop,
        "count": len(productos_mapped),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "products": productos_mapped,
    }

    return JSONResponse(content=result)


def _price_min(product: Dict) -> float:
    prices = []
    for v in product.get("variants", []):
        try:
            if v.get("price") is not None:
                prices.append(float(v.get("price")))
        except (ValueError, TypeError):
            continue
    return min(prices) if prices else 0.0


def _sort_key(product: Dict, sort_by: str) -> Tuple:
    if sort_by == "price":
        return (_price_min(product), product.get("title", ""))
    if sort_by == "vendor":
        return (product.get("vendor", ""), product.get("title", ""))
    # default title
    return (product.get("title", ""),)


@app.get("/productos_ui")
def productos_ui(
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
    sort_by: str = Query(default="title", description="Criterio de orden: title|price|vendor"),
) -> HTMLResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    productos_raw = fetch_all_products(target_shop, api_key, password, access_token)
    productos_mapped = [map_product(p) for p in productos_raw]

    # Ordenar
    productos_sorted = sorted(productos_mapped, key=lambda p: _sort_key(p, sort_by))

    # Render HTML simple y ordenado
    rows = []
    for p in productos_sorted:
        price_min = _price_min(p)
        rows.append(
            f"<tr>"
            f"<td>{p.get('id','')}</td>"
            f"<td>{p.get('title','')}</td>"
            f"<td>{p.get('vendor','')}</td>"
            f"<td>{p.get('product_type','')}</td>"
            f"<td>{p.get('status','')}</td>"
            f"<td>{len(p.get('variants', []))}</td>"
            f"<td>{price_min:.2f}</td>"
            f"<td>{p.get('created_at','')}</td>"
            f"</tr>"
        )

    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Productos · {target_shop}</title>
        <style>
            body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
            h1 {{ margin-bottom: 8px; }}
            .meta {{ color: #666; margin-bottom: 16px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background: #f7f7f7; text-align: left; }}
            tr:nth-child(even) {{ background: #fafafa; }}
            .controls {{ margin-bottom: 12px; }}
            .controls a {{ margin-right: 8px; }}
        </style>
    </head>
    <body>
        <h1>Productos de {target_shop}</h1>
        <div class=\"meta\">Total: {len(productos_sorted)} · Orden: {sort_by}</div>
        <div class=\"controls\">
            Ordenar:
            <a href=\"/productos_ui?sort_by=title\">por título</a>
            <a href=\"/productos_ui?sort_by=vendor\">por vendor</a>
            <a href=\"/productos_ui?sort_by=price\">por precio</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Título</th>
                    <th>Vendor</th>
                    <th>Tipo</th>
                    <th>Status</th>
                    <th>Variantes</th>
                    <th>Precio mínimo</th>
                    <th>Creado</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p class=\"meta\">También disponible en JSON: <code>/productos</code></p>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.post("/productos_metafields_upsert")
def productos_metafields_upsert(
    payload: Dict = Body(..., description="JSON con product_id y lista de updates"),
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
) -> JSONResponse:
    """
    Crea/actualiza metafields de un producto usando la mutación `metafieldsSet`.

    Body esperado:
    {
      "product_id": 1234567890,
      "updates": [
        {"namespace": "custom", "key": "vineta_1", "type": "rich_text_field", "value": {…}},
        {"namespace": "custom", "key": "ancho", "type": "number_decimal", "value": 12.5},
        …
      ]
    }
    - Omite automáticamente valores nulos/vacíos.
    - Agrupa en lotes de 25 por límite de Shopify.
    """
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="El cuerpo debe ser un objeto JSON.")

    product_id = payload.get("product_id")
    updates = payload.get("updates") or []

    if not product_id or not isinstance(product_id, int):
        raise HTTPException(status_code=400, detail="Debes especificar product_id (entero numérico).")
    if not isinstance(updates, list):
        raise HTTPException(status_code=400, detail="'updates' debe ser una lista de objetos.")

    owner_id = f"gid://shopify/Product/{product_id}"

    # Construir entradas válidas
    metafields_inputs: List[Dict] = []
    skipped: List[Dict] = []
    for u in updates:
        if not isinstance(u, dict):
            skipped.append({"reason": "item no es objeto", "item": u})
            continue
        ns = (u.get("namespace") or "").strip()
        key = (u.get("key") or "").strip()
        mtype = (u.get("type") or "").strip()
        raw_value = u.get("value")
        if not ns or not key or not mtype:
            skipped.append({"reason": "namespace/key/type faltantes", "item": u})
            continue
        norm = _normalize_metafield_value(raw_value, mtype)
        if norm is None:
            skipped.append({"reason": "valor nulo/vacío/inválido", "item": {"namespace": ns, "key": key, "type": mtype}})
            continue
        metafields_inputs.append({
            "ownerId": owner_id,
            "namespace": ns,
            "key": key,
            "type": mtype,
            "value": norm,
        })

    if not metafields_inputs:
        return JSONResponse(content={
            "product_id": product_id,
            "attempted": 0,
            "updated": 0,
            "batches": 0,
            "skipped": skipped,
            "message": "No hay updates válidos para aplicar.",
        }, status_code=200)

    mutation = (
        "mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) { "
        "  metafieldsSet(metafields: $metafields) { "
        "    metafields { id namespace key type value } "
        "    userErrors { field message code } "
        "  } "
        "}"
    )

    batches = _chunk_list(metafields_inputs, size=25)

    updated_items: List[Dict] = []
    all_errors: List[Dict] = []

    for batch in batches:
        data = graphql_admin_query(target_shop, api_key, password, access_token, mutation, {"metafields": batch})
        result = (data.get("metafieldsSet") or {})
        for m in (result.get("metafields") or []):
            updated_items.append({
                "id": m.get("id"),
                "namespace": m.get("namespace"),
                "key": m.get("key"),
                "type": m.get("type"),
                "value": m.get("value"),
            })
        for e in (result.get("userErrors") or []):
            all_errors.append(e)

    return JSONResponse(content={
        "product_id": product_id,
        "attempted": len(metafields_inputs),
        "updated": len(updated_items),
        "batches": len(batches),
        "skipped": skipped,
        "errors": all_errors,
        "updated_metafields": updated_items,
    })


@app.get("/productos_metafields")
def productos_metafields(
    product_id: int = Query(default=..., description="ID numérico del producto"),
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
) -> JSONResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    gid = f"gid://shopify/Product/{product_id}"
    query = (
        "query($id: ID!) { product(id: $id) { metafields(first: 250) { edges { node { namespace key type value reference { __typename ... on Metaobject { id handle type } } references(first: 100) { nodes { __typename ... on Metaobject { id handle type } } } } } } } }"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"id": gid})
    edges = (((data.get("product") or {}).get("metafields") or {}).get("edges") or [])

    items: List[Dict] = []
    for e in edges:
        node = e.get("node") or {}
        ref = node.get("reference") or {}
        refs = (((node.get("references") or {}).get("nodes") or []))
        items.append({
            "namespace": node.get("namespace"),
            "key": node.get("key"),
            "type": node.get("type"),
            "value": node.get("value"),
            "reference": {"id": ref.get("id"), "handle": ref.get("handle"), "type": ref.get("type")} if ref else None,
            "references": [{"id": r.get("id"), "handle": r.get("handle"), "type": r.get("type")} for r in refs],
        })

    return JSONResponse(content={"count": len(items), "metafields": items})


def _mf_sort_key(item: Dict, sort_by: str) -> tuple:
    if sort_by == "namespace":
        return (item.get("namespace", ""), item.get("key", ""))
    if sort_by == "key":
        return (item.get("key", ""), item.get("namespace", ""))
    if sort_by == "type":
        return (item.get("type", ""), item.get("namespace", ""), item.get("key", ""))
    return (item.get("namespace", ""), item.get("key", ""))


@app.get("/productos_metafields_ui")
def productos_metafields_ui(
    product_id: int = Query(default=..., description="ID numérico del producto"),
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
    sort_by: str = Query(default="namespace", description="Orden: namespace|key|type"),
    q: Optional[str] = Query(default=None, description="Filtro de texto en namespace/key/type/value"),
) -> HTMLResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    gid = f"gid://shopify/Product/{product_id}"
    query = (
        "query($id: ID!) { product(id: $id) { metafields(first: 250) { edges { node { namespace key type value reference { __typename ... on Metaobject { id handle type } } references(first: 50) { nodes { __typename ... on Metaobject { id handle type } } } } } } } }"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"id": gid})
    edges = (((data.get("product") or {}).get("metafields") or {}).get("edges") or [])

    items: List[Dict] = []
    for e in edges:
        node = e.get("node") or {}
        ref = node.get("reference") or {}
        refs = (((node.get("references") or {}).get("nodes") or []))
        items.append({
            "namespace": node.get("namespace"),
            "key": node.get("key"),
            "type": node.get("type"),
            "value": node.get("value"),
            "reference": {"id": ref.get("id"), "handle": ref.get("handle"), "type": ref.get("type")} if ref else None,
            "references": [{"id": r.get("id"), "handle": r.get("handle"), "type": r.get("type")} for r in refs],
        })

    # Filtro por q
    if q:
        ql = q.lower()
        items = [i for i in items if (
            (i.get("namespace") or "").lower().find(ql) >= 0 or
            (i.get("key") or "").lower().find(ql) >= 0 or
            (i.get("type") or "").lower().find(ql) >= 0 or
            (i.get("value") or "").lower().find(ql) >= 0
        )]

    items_sorted = sorted(items, key=lambda i: _mf_sort_key(i, sort_by))

    def trunc(s: Optional[str], n: int = 160) -> str:
        if not s:
            return ""
        return s if len(s) <= n else s[:n] + "…"

    rows = []
    for m in items_sorted:
        ref = m.get("reference") or {}
        refs = m.get("references") or []
        ref_html = ""
        if ref.get("id"):
            ref_html = f"<div>Ref: {ref.get('handle','')} ({ref.get('type','')})</div>"
        if refs:
            ref_html += f"<div>Refs: {len(refs)} metaobjects</div>"
        rows.append(
            f"<tr>"
            f"<td><code>{m.get('namespace','')}</code></td>"
            f"<td><code>{m.get('key','')}</code></td>"
            f"<td>{m.get('type','')}</td>"
            f"<td>{trunc(m.get('value'))}</td>"
            f"<td>{ref_html}</td>"
            f"</tr>"
        )

    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Metafields del producto {product_id} · {target_shop}</title>
        <style>
            body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
            h1 {{ margin-bottom: 8px; }}
            .meta {{ color: #666; margin-bottom: 12px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
            th {{ background: #f7f7f7; text-align: left; }}
            tr:nth-child(even) {{ background: #fafafa; }}
            .controls a {{ margin-right: 8px; }}
            .controls input {{ padding: 4px 6px; }}
        </style>
    </head>
    <body>
        <h1>Metafields del producto {product_id}</h1>
        <div class=\"meta\">Total: {len(items_sorted)} · Orden: {sort_by}</div>
        <div class=\"controls\">
            Ordenar:
            <a href=\"/productos_metafields_ui?product_id={product_id}&sort_by=namespace\">por namespace</a>
            <a href=\"/productos_metafields_ui?product_id={product_id}&sort_by=key\">por key</a>
            <a href=\"/productos_metafields_ui?product_id={product_id}&sort_by=type\">por type</a>
            · Filtrar:
            <form method=\"get\" action=\"/productos_metafields_ui\" style=\"display:inline\">
                <input type=\"hidden\" name=\"product_id\" value=\"{product_id}\" />
                <input type=\"text\" name=\"q\" value=\"{q or ''}\" placeholder=\"buscar...\" />
                <button type=\"submit\">Aplicar</button>
            </form>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Namespace</th>
                    <th>Key</th>
                    <th>Type</th>
                    <th>Value</th>
                    <th>Referencia(s)</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p class=\"meta\">JSON: <code>/productos_metafields?product_id={product_id}</code></p>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/metaobjects")
def listar_metaobjects(
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
    type: str = Query(default=..., description="Tipo de metaobjeto (handle del tipo)"),
    first: int = Query(default=50, ge=1, le=250, description="Cantidad de metaobjetos a listar"),
) -> JSONResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    query = (
        "query($type: String!, $first: Int!) { "
        "  metaobjects(type: $type, first: $first) { "
        "    edges { cursor node { id handle type fields { key value } } } "
        "  } "
        "}"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"type": type, "first": first})

    edges = ((data.get("metaobjects") or {}).get("edges") or [])
    items = []
    for e in edges:
        node = e.get("node") or {}
        items.append({
            "id": node.get("id"),
            "handle": node.get("handle"),
            "type": node.get("type"),
            "fields": node.get("fields", []),
            "cursor": e.get("cursor"),
        })

    result = {
        "shop": target_shop,
        "type": type,
        "count": len(items),
        "items": items,
    }
    return JSONResponse(content=result)


def _mo_sort_key(item: Dict, sort_by: str) -> tuple:
    if sort_by == "handle":
        return (item.get("handle", ""), item.get("type", ""))
    if sort_by == "type":
        return (item.get("type", ""), item.get("handle", ""))
    # default id
    return (item.get("id", ""),)


@app.get("/metaobjects_ui")
def metaobjects_ui(
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
    type: str = Query(default=..., description="Tipo de metaobjeto (handle del tipo)"),
    first: int = Query(default=50, ge=1, le=250, description="Cantidad de metaobjetos a listar"),
    sort_by: str = Query(default="handle", description="Orden: handle|type|id"),
) -> HTMLResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    query = (
        "query($type: String!, $first: Int!) { "
        "  metaobjects(type: $type, first: $first) { edges { node { id handle type fields { key value } } } } "
        "}"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"type": type, "first": first})
    edges = ((data.get("metaobjects") or {}).get("edges") or [])
    items = []
    for e in edges:
        node = e.get("node") or {}
        items.append({
            "id": node.get("id"),
            "handle": node.get("handle"),
            "type": node.get("type"),
            "fields": node.get("fields", []),
        })

    items_sorted = sorted(items, key=lambda i: _mo_sort_key(i, sort_by))

    rows = []
    for m in items_sorted:
        fields_html = "".join([f"<div><code>{f.get('key')}</code>: {f.get('value')}</div>" for f in m.get("fields", [])])
        rows.append(
            f"<tr>"
            f"<td>{m.get('id','')}</td>"
            f"<td>{m.get('handle','')}</td>"
            f"<td>{m.get('type','')}</td>"
            f"<td>{fields_html}</td>"
            f"</tr>"
        )

    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Metaobjects · {target_shop}</title>
        <style>
            body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
            h1 {{ margin-bottom: 8px; }}
            .meta {{ color: #666; margin-bottom: 16px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
            th {{ background: #f7f7f7; text-align: left; }}
            tr:nth-child(even) {{ background: #fafafa; }}
            .controls {{ margin-bottom: 12px; }}
            .controls a {{ margin-right: 8px; }}
        </style>
    </head>
    <body>
        <h1>Metaobjects de {target_shop}</h1>
        <div class=\"meta\">Tipo: {type} · Total: {len(items_sorted)} · Orden: {sort_by}</div>
        <div class=\"controls\">
            Ordenar:
            <a href=\"/metaobjects_ui?type={type}&sort_by=handle\">por handle</a>
            <a href=\"/metaobjects_ui?type={type}&sort_by=type\">por type</a>
            <a href=\"/metaobjects_ui?type={type}&sort_by=id\">por id</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Handle</th>
                    <th>Type</th>
                    <th>Fields</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p class=\"meta\">JSON: <code>/metaobjects?type={type}</code></p>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/productos_metaobjects_ui")
def productos_metaobjects_ui(
    product_id: int = Query(default=..., description="ID numérico del producto"),
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
    sort_by: str = Query(default="handle", description="Orden: handle|type|id"),
) -> HTMLResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    gid = f"gid://shopify/Product/{product_id}"
    query = (
        "query($id: ID!) { product(id: $id) { metafields(first: 250) { edges { node { namespace key type value reference { __typename ... on Metaobject { id handle type } } references(first: 100) { nodes { __typename ... on Metaobject { id handle type } } } } } } } }"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"id": gid})

    edges = (((data.get("product") or {}).get("metafields") or {}).get("edges") or [])
    referenced: List[Dict] = []
    for e in edges:
        node = e.get("node") or {}
        ns = node.get("namespace")
        key = node.get("key")
        tipo = node.get("type")
        ref = node.get("reference") or {}
        if ref.get("id") and ref.get("handle"):
            referenced.append({"id": ref.get("id"), "handle": ref.get("handle"), "type": ref.get("type"), "from": f"{ns}:{key}:{tipo}"})
        for r in (((node.get("references") or {}).get("nodes") or [])):
            if r.get("id") and r.get("handle"):
                referenced.append({"id": r.get("id"), "handle": r.get("handle"), "type": r.get("type"), "from": f"{ns}:{key}:{tipo}"})

    uniq: Dict[str, Dict] = {}
    for item in referenced:
        keyu = f"{item.get('id')}|{item.get('handle')}"
        if keyu not in uniq:
            uniq[keyu] = item

    items = list(uniq.values())
    items_sorted = sorted(items, key=lambda i: _mo_sort_key(i, sort_by))

    rows = []
    for m in items_sorted:
        rows.append(
            f"<tr>"
            f"<td>{m.get('id','')}</td>"
            f"<td>{m.get('handle','')}</td>"
            f"<td>{m.get('type','')}</td>"
            f"<td>{m.get('from','')}</td>"
            f"</tr>"
        )

    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Metaobjects por producto · {target_shop}</title>
        <style>
            body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 24px; }}
            h1 {{ margin-bottom: 8px; }}
            .meta {{ color: #666; margin-bottom: 16px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background: #f7f7f7; text-align: left; }}
            tr:nth-child(even) {{ background: #fafafa; }}
            .controls {{ margin-bottom: 12px; }}
            .controls a {{ margin-right: 8px; }}
        </style>
    </head>
    <body>
        <h1>Metaobjects referenciados del producto {product_id}</h1>
        <div class=\"meta\">Total: {len(items_sorted)} · Orden: {sort_by}</div>
        <div class=\"controls\">
            Ordenar:
            <a href=\"/productos_metaobjects_ui?product_id={product_id}&sort_by=handle\">por handle</a>
            <a href=\"/productos_metaobjects_ui?product_id={product_id}&sort_by=type\">por type</a>
            <a href=\"/productos_metaobjects_ui?product_id={product_id}&sort_by=id\">por id</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Handle</th>
                    <th>Type</th>
                    <th>Origen metafield</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p class=\"meta\">JSON: <code>/productos_metaobjects?product_id={product_id}</code></p>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/productos_metaobjects")
def listar_metaobjects_de_producto(
    product_id: int = Query(default=..., description="ID numérico del producto"),
    shop: Optional[str] = Query(default=None, description="Subdominio de la tienda Shopify (sin .myshopify.com)"),
) -> JSONResponse:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop

    gid = f"gid://shopify/Product/{product_id}"
    query = (
        "query($id: ID!) { "
        "  product(id: $id) { "
        "    id title "
        "    metafields(first: 250) { "
        "      edges { "
        "        node { "
        "          namespace key type value "
        "          reference { __typename ... on Metaobject { id handle type } } "
        "          references(first: 50) { nodes { __typename ... on Metaobject { id handle type } } } "
        "        } "
        "      } "
        "    } "
        "  } "
        "}"
    )
    data = graphql_admin_query(target_shop, api_key, password, access_token, query, {"id": gid})

    product = data.get("product") or {}
    metafields_edges = ((product.get("metafields") or {}).get("edges") or [])

    referenced: List[Dict] = []
    for e in metafields_edges:
        node = e.get("node") or {}
        ns = node.get("namespace")
        key = node.get("key")
        tipo = node.get("type")
        # Metaobjeto único
        ref = node.get("reference") or {}
        if ref.get("id") and ref.get("handle"):
            referenced.append({
                "id": ref.get("id"),
                "handle": ref.get("handle"),
                "type": ref.get("type"),
                "from_metafield": {"namespace": ns, "key": key, "type": tipo},
            })
        # Lista de metaobjetos
        refs = ((node.get("references") or {}).get("nodes") or [])
        for r in refs:
            if r.get("id") and r.get("handle"):
                referenced.append({
                    "id": r.get("id"),
                    "handle": r.get("handle"),
                    "type": r.get("type"),
                    "from_metafield": {"namespace": ns, "key": key, "type": tipo},
                })

    # Unificar por id+handle
    uniq: Dict[str, Dict] = {}
    for item in referenced:
        key = f"{item.get('id')}|{item.get('handle')}"
        if key not in uniq:
            uniq[key] = item

    items = list(uniq.values())
    result = {
        "shop": target_shop,
        "product": {"id": product.get("id"), "title": product.get("title")},
        "count": len(items),
        "items": items,
    }
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("shopify_api:app", host="127.0.0.1", port=8000, reload=False)