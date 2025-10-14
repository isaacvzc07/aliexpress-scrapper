import os
import json
import argparse
from datetime import datetime
from typing import Optional, List, Dict

from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

try:
    from shopify_api import get_env_credentials, graphql_admin_query
except Exception:
    raise SystemExit("No se pudo importar funciones de shopify_api.py. Asegúrate de ejecutar desde la raíz del proyecto.")


def fetch_product_metafields(product_id: int, shop: Optional[str]) -> dict:
    api_key, password, env_shop, access_token = get_env_credentials()
    target_shop = shop or env_shop
    if not target_shop:
        raise RuntimeError("Falta SHOPIFY_SHOP. Configura .env o usa --shop.")

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

    return {
        "shop": target_shop,
        "product_id": product_id,
        "count": len(items),
        "metafields": items,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


def save_json(data: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta los metafields de un producto a JSON")
    parser.add_argument("--id", type=int, help="ID numérico del producto")
    parser.add_argument("--shop", type=str, default=None, help="Subdominio de la tienda Shopify (sin .myshopify.com)")
    parser.add_argument("--out", type=str, default=None, help="Ruta del archivo de salida .json")
    args = parser.parse_args()

    product_id = args.id
    if not product_id:
        try:
            product_id = int(input("Ingresa el ID numérico del producto: ").strip())
        except Exception:
            raise SystemExit("ID inválido. Debe ser un número entero.")

    data = fetch_product_metafields(product_id, args.shop)

    output_path = args.out or os.path.join(os.getcwd(), f"metafields_{product_id}.json")
    save_json(data, output_path)
    print(f"Guardado: {output_path} (metafields={data['count']})")


if __name__ == "__main__":
    main()