# Scrapper y actualización de Metafields para Shopify

Guía completa para instalar, configurar y ejecutar los scripts que generan contenido con OpenAI/Playwright y actualizan metafields de productos en Shopify.

## Requisitos
- Python 3.9+
- Dependencias de Python:
  - `requests`, `python-dotenv`, `playwright`, `openai`
  - Opcional: `fastapi`, `uvicorn`, `beautifulsoup4` (para servidor UI y convertidor HTML→JSON)
- Navegadores de Playwright instalados:
  - Windows: `py -m playwright install`
  - macOS/Linux: `python3 -m playwright install`
- Credenciales Shopify:
  - `SHOPIFY_SHOP`: subdominio de la tienda (sin `.myshopify.com`)
  - `SHOPIFY_ACCESS_TOKEN`: token con permisos de lectura/escritura para `Products` y `Metafields`
  - Opcional: `SHOPIFY_API_KEY` y `SHOPIFY_PASSWORD` (soporte Basic Auth para GraphQL si no usas token)

## Instalación rápida

### Windows (PowerShell)
```powershell
# Entrar a la carpeta del proyecto
cd scrapper

# Crear y activar entorno virtual
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Si la activación está bloqueada, permite scripts en el usuario actual
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Instalar dependencias
pip install requests python-dotenv playwright openai
# Opcional (servidor y conversiones)
pip install fastapi uvicorn beautifulsoup4

# Instalar navegadores Playwright
py -m playwright install
```

### macOS/Linux
```bash
# Entrar a la carpeta del proyecto
cd scrapper

# Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install requests python-dotenv playwright openai
# Opcional (servidor y conversiones)
pip install fastapi uvicorn beautifulsoup4

# Instalar navegadores Playwright
python3 -m playwright install
```

## Configuración de credenciales
Crea un archivo `.env` en la raíz del proyecto:
```env
SHOPIFY_SHOP=bloqmx
SHOPIFY_ACCESS_TOKEN=shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Opcional (solo si usas Basic Auth para GraphQL)
SHOPIFY_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SHOPIFY_PASSWORD=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SHOPIFY_API_VERSION=2024-07
```

También puedes pasar `--shop` y `--token` como argumentos CLI si prefieres no usar `.env`.

En Windows, también puedes establecer variables de entorno en la sesión actual:
```powershell
$env:SHOPIFY_SHOP = "bloqmx"
$env:SHOPIFY_ACCESS_TOKEN = "shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```
En CMD clásico:
```cmd
set SHOPIFY_SHOP=bloqmx
set SHOPIFY_ACCESS_TOKEN=shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

## Estructura de salidas
El scraper crea una carpeta por producto de AliExpress dentro de `hover_carrusel/`:
```
hover_carrusel/
  producto_<ID_AE>/
    analisis_copywriting_openai.html
    analisis_copywriting_openai.json
    rich_text_field.json
    imagenes/
    metafields_<ID_SHOPIFY>.json
```

- `rich_text_field.json`: entrada principal para actualizar metafields.
- `metafields_<id>.json`: export de los metafields del producto en Shopify.

## Uso: actualizar metafields desde JSON
Script: `generate_and_put_metafields.py`

Argumentos:
- `--product-id`: ID numérico del producto en Shopify (obligatorio)
- `--input-json`: ruta al JSON de entrada con `{"content": "<markdown>", "format": "markdown"}` (obligatorio)
- `--shop`: subdominio Shopify (por defecto toma `.env`)
- `--token`: access token Shopify (por defecto toma `.env`)
- `--ids-json`: ruta a mapa `{key: id}` para actualizaciones directas (opcional; si no se pasa, los IDs se consultan por REST)
- `--out-json`: ruta para guardar los updates generados (opcional)

Ejemplo usando `.env` (Windows/macOS/Linux):
```bash
# macOS/Linux
python3 generate_and_put_metafields.py \
  --product-id 7384820154465 \
  --input-json hover_carrusel/producto_1005007023215594/rich_text_field.json

# Windows (PowerShell)
py generate_and_put_metafields.py \
  --product-id 7384820154465 \
  --input-json hover_carrusel/producto_1005007023215594/rich_text_field.json
```

Ejemplo pasando credenciales por CLI:
```bash
# macOS/Linux
python3 generate_and_put_metafields.py \
  --product-id 7384820154465 \
  --input-json hover_carrusel/producto_1005009508765865/rich_text_field.json \
  --shop bloqmx \
  --token shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Windows (PowerShell)
py generate_and_put_metafields.py \
  --product-id 7384820154465 \
  --input-json hover_carrusel/producto_1005009508765865/rich_text_field.json \
  --shop bloqmx \
  --token shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Comportamiento clave:
- `sec5_body` siempre se genera con un texto fijo de dos párrafos definido por `SEC5_BODY_DESIRED` y convertido a Rich Text JSON.
- Se ignoran encabezados `###` en el parsing de la sección de video.
- Si no hay cambios (lista `updates` vacía), el script:
  - borra `put_updates_<id>.json` vacío,
  - omite ejecutar PUT en Shopify,
  - no crea `put_updates_<id>_results.json`.

## Uso: scraper de carrusel (AliExpress)
Script: `scraper_hover_carrusel.py`

Pasos:
1. Ejecuta el scraper:
   ```bash
   # macOS/Linux
   python3 scraper_hover_carrusel.py

   # Windows (PowerShell)
   py scraper_hover_carrusel.py
   ```
2. Ingresa la URL del producto de AliExpress cuando se solicite.
3. Confirma continuar con el scraping.
4. Al finalizar, el script convertirá el análisis HTML a JSON y generará `rich_text_field.json`.
5. Luego solicitará el `ID` del producto en Shopify y actualizará los metafields automáticamente usando `generate_and_put_metafields.py` (requiere `SHOPIFY_SHOP` y `SHOPIFY_ACCESS_TOKEN` en `.env`).
6. Exportará los metafields a `hover_carrusel/producto_<ID_AE>/metafields_<ID_SHOPIFY>.json`.

Notas:
- El scraper usa Playwright en modo visible (no headless) para facilitar debugging.
- Asegúrate de haber ejecutado `python3 -m playwright install`.

## Uso: exportar metafields de un producto
Script: `fetch_product_metafields_to_json.py`

Argumentos:
- `--id`: ID numérico del producto en Shopify
- `--shop`: subdominio Shopify (opcional; toma de `.env` si no se pasa)
- `--out`: ruta del archivo de salida `.json` (opcional)

Ejemplo:
```bash
# macOS/Linux
python3 fetch_product_metafields_to_json.py --id 7384820154465 --out hover_carrusel/producto_1005007023215594/metafields_7384820154465.json

# Windows (PowerShell)
py fetch_product_metafields_to_json.py --id 7384820154465 --out hover_carrusel/producto_1005007023215594/metafields_7384820154465.json
```

## Servidor opcional (UI de inspección)
Puedes iniciar un servidor con endpoints para visualizar metafields:
```bash
# macOS/Linux
python3 -m uvicorn shopify_api:app --host 127.0.0.1 --port 8001

# Windows (PowerShell)
py -m uvicorn shopify_api:app --host 127.0.0.1 --port 8001
```

UI de ejemplo:
- Metafields UI: `http://127.0.0.1:8001/productos_metafields_ui?product_id=7384820154465&shop=bloqmx`

## Ejemplos rápidos
- Actualizar metafields desde un JSON generado por el scraper:
  ```bash
  # macOS/Linux
  export SHOPIFY_SHOP=bloqmx
  export SHOPIFY_ACCESS_TOKEN=shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
  python3 generate_and_put_metafields.py \
    --product-id 7385183879265 \
    --input-json hover_carrusel/producto_1005009735069213/rich_text_field.json

  # Windows (PowerShell)
  $env:SHOPIFY_SHOP = "bloqmx"
  $env:SHOPIFY_ACCESS_TOKEN = "shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  py generate_and_put_metafields.py \
    --product-id 7385183879265 \
    --input-json hover_carrusel/producto_1005009735069213/rich_text_field.json
  ```
- Ejecutar scraper y seguir flujo automático:
  ```bash
  # macOS/Linux
  python3 scraper_hover_carrusel.py
  # Ingresa URL de AliExpress cuando se pida
  # Ingresa ID de producto Shopify para actualizar metafields

  # Windows (PowerShell)
  py scraper_hover_carrusel.py
  # Ingresa URL de AliExpress cuando se pida
  # Ingresa ID de producto Shopify para actualizar metafields
  ```

## Solución de problemas
- Playwright no inicia:
  - Ejecuta `python3 -m playwright install`.
  - En macOS, instala Xcode Command Line Tools: `xcode-select --install`.
- Errores 401/403 con Shopify:
  - Verifica `SHOPIFY_SHOP`/`SHOPIFY_ACCESS_TOKEN` y permisos del token.
  - Asegúrate de usar el subdominio correcto (sin `.myshopify.com`).
- No se crean archivos de resultados:
  - Si la lista de updates queda vacía, el script limpia el archivo vacío y no ejecuta PUTs (comportamiento esperado).

## Notas de seguridad
- No compartas ni publiques tu `SHOPIFY_ACCESS_TOKEN`.
- Excluye `.env` de commits públicos.
- Revisa y actualiza `SEC5_BODY_DESIRED` si necesitas personalizar el contenido fijo de `sec5_body`.








umérgete en una experiencia de armado única con dimensiones compactas de 18.5 cm de longitud. Perfecto parexhibir en cualquier espacio.
Detalles realistas y un diseño innovador que transforman este set en un tesoro coleccionable. Ideal para entusiastas y soñadores."""