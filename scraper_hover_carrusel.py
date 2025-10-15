#!/usr/bin/env python3
"""
Scraper de productos de AliExpress con descarga de imágenes
Descarga imágenes del producto y las analiza con OpenAI Vision API
"""

import asyncio
import os
import base64
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from openai import OpenAI
from convert_analisis_copywriting_to_json import convert_file as convert_analysis_html_to_json
from fetch_product_metafields_to_json import fetch_product_metafields, save_json as save_metafields_json
from image_downloader import download_images

# Cargar variables de entorno desde .env
load_dotenv()

class AliExpressImageScraper:
    def __init__(self, output_dir="hover_carrusel"):
        self.output_dir = output_dir
        self.downloaded_images = []
        # Configuración de OpenAI
        self.openai_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
    async def setup_browser(self):
        """Configura el navegador en modo headless"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # Modo invisible para mayor estabilidad
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',  # Evita el asistente de primera ejecución
                '--disable-default-apps',  # Deshabilita apps por defecto
                '--disable-extensions-except',  # Permite extensiones del usuario
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--no-sandbox',  # Evita restricciones de sandbox
                '--disable-web-security',  # Deshabilita restricciones web
                '--allow-running-insecure-content',  # Permite contenido inseguro
                '--disable-features=VizDisplayCompositor',  # Mejora compatibilidad
                '--start-maximized',  # Inicia maximizado como navegador normal
                '--disable-infobars',  # Quita barras de información
                '--disable-dev-shm-usage'  # Evita problemas de memoria compartida
            ]
        )
        # Crear contexto SIN modo incógnito
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ignore_https_errors=True,  # Ignora errores HTTPS
            accept_downloads=True  # Permite descargas como navegador normal
        )
        self.page = await self.context.new_page()
        
    async def navigate_to_product(self, url):
        """Navega a la página del producto"""
        print(f"🔍 Navegando a: {url}")
        try:
            response = await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)

            if not response or response.status >= 400:
                print(f"❌ Error: La página devolvió status {response.status if response else 'unknown'}")
                return False

            # Esperar a que cargue JavaScript - aumentado a 5 segundos para AliExpress
            await self.page.wait_for_timeout(5000)
            print("✅ Página cargada correctamente")
            return True
        except Exception as e:
            print(f"❌ Error navegando: {type(e).__name__}: {e}")
            return False
    
    def encode_image_to_base64(self, image_path):
        """Convierte una imagen a base64 para enviar a OpenAI"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"❌ Error codificando imagen {image_path}: {e}")
            return None
    
    def _convert_markdown_to_html(self, markdown_text):
        """Convertir texto Markdown básico a HTML"""
        html_text = markdown_text
        
        # Convertir negritas **texto** a <strong>texto</strong>
        import re
        html_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_text)
        
        # Convertir cursivas *texto* a <em>texto</em>
        html_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html_text)
        
        # Convertir saltos de línea a <br>
        html_text = html_text.replace('\n', '<br>\n')
        
        # Convertir líneas que empiezan con • a elementos de lista
        lines = html_text.split('<br>\n')
        in_list = False
        result_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('•'):
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                result_lines.append(f'<li>{line[1:].strip()}</li>')
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                if line:
                    result_lines.append(f'<p>{line}</p>')
        
        if in_list:
            result_lines.append('</ul>')
        
        return '\n'.join(result_lines)
    
    async def analyze_images_with_openai(self):
        """Analiza las imágenes descargadas usando OpenAI Vision API con el prompt de copywriting"""
        try:
            print("🤖 Iniciando análisis con OpenAI...")
            print(f"📊 Total de imágenes disponibles: {len(self.downloaded_images)}")

            # Prompt de copywriting especializado - FORMATO MARKDOWN
            prompt_text = """Eres un copywriter profesional especializado en crear ofertas irresistibles para páginas de producto en tiendas de e-commerce.

Tu tarea es analizar las imágenes del producto y generar una página de ventas completa en FORMATO MARKDOWN.

REGLAS IMPORTANTES:
- Nunca mencionar la marca LEGO ni otras marcas registradas
- Usar palabras clave en **negritas** para destacar beneficios
- Tono playful, moderno, coleccionable, sin sensacionalismo
- Evitar la palabra 'premium' salvo en 'manual impreso premium'
- Cada viñeta debe tener ~110 caracteres
- Los headings de Sección 4 siempre deben tener signos de exclamación al inicio y al final
- Limitar la longitud de cada párrafo en la Sección 4 a 250–300 caracteres
- Eliminar cualquier CTA de la salida final
- IMPORTANTE: La salida DEBE ser Markdown válido con headers ##
- NUNCA generar JSON como salida

EXTRACCIÓN DE DATOS:
Extraer de las imágenes: nombre del producto, colección, número de piezas, funciones (motor, dirección, suspensión, articulaciones), escala y dimensiones (alto, ancho, longitud), tipo o estilo del modelo.

Si no observas datos esenciales (piezas, dimensiones, escala) en las imágenes, indica: "No observado en imágenes"

FORMATO DE SALIDA REQUERIDO (usar EXACTAMENTE este formato):

## 0. Nombre del Producto

[Nombre creativo sin marcas registradas] (XXX pzas)

INSTRUCCIONES para nombre:
- Crear nombre único y atractivo basado en el producto
- NO usar marcas (LEGO, Disney, Marvel, etc.)
- NO incluir IDs o códigos del producto original
- Usar lenguaje playful, moderno, en español
- SIEMPRE incluir número de piezas: (XXX pzas)
- Ejemplos: Chispa Ratón (116 pzas), Dragón Guardián (524 pzas)

## 1. Viñetas

- **[keyword]** Beneficio funcional o emocional con número de piezas (~110 caracteres)
- **[keyword]** Dimensión destacada aplicada al valor de exhibición (~110 caracteres)
- **[keyword]** Detalle de diseño o realismo del modelo (~110 caracteres)
- **[keyword]** Experiencia de armado (relajante, desafiante, divertida) (~110 caracteres)
- **[keyword]** Regalo o valor coleccionable (~110 caracteres)

## 2. FAQ

- **¿Qué incluye el precio?**
  El set completo con [número] piezas y manual impreso premium.

- **¿Cuáles son las funciones y beneficios clave?**
  Incluye [funciones: motor, dirección, suspensión, etc.] – todo diseñado para una experiencia realista y coleccionable.

- **¿Por qué este set es especial?**
  Porque combina diseño detallado, funciones realistas y una construcción sólida, convirtiéndolo en una pieza única para fans y coleccionistas.

## 3. Detalles Técnicos

- **Ancho:** [valor en cm o 'No observado en imágenes']
- **Longitud:** [valor en cm o 'No observado en imágenes']
- **Alto:** [valor en cm o 'No observado en imágenes']
- **Piezas:** [número total]
- **Escala:** [valor o 'No observado en imágenes']

## 4. Sección de Video

- **Title:** ¡[Heading de 4–7 palabras]!
- **Body:** [Primer párrafo 250-300 chars sobre experiencia de armado y dimensiones]

[Segundo párrafo 250-300 chars sobre funciones, valor de exhibición y colección]

IMPORTANTE: Genera SOLO el contenido en Markdown siguiendo EXACTAMENTE este formato. NO generes JSON."""
            
            # Preparar imágenes para análisis
            images_for_analysis = []

            print("🔍 Procesando todas las imágenes descargadas...")

            # Agregar todas las imágenes descargadas con alta calidad
            for image_info in self.downloaded_images:
                image_path = image_info.get('path')
                if not image_path or not os.path.exists(image_path):
                    continue

                base64_image = self.encode_image_to_base64(image_path)
                if base64_image:
                    images_for_analysis.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "high"
                        }
                    })
                    print(f"✅ Imagen agregada: {image_info.get('filename', 'sin nombre')}")

            print(f"📸 Imágenes preparadas para análisis: {len(images_for_analysis)}")

            if not images_for_analysis:
                print("❌ No se encontraron imágenes para analizar")
                return None
            
            # Crear el mensaje para OpenAI
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ] + images_for_analysis
                }
            ]
            
            # Llamar a OpenAI Vision API
            print("📤 Enviando imágenes a OpenAI para análisis...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000,
                temperature=0.7
            )
            
            analysis_result = response.choices[0].message.content
            print("✅ Análisis completado")
            
            # Guardar el resultado en formato HTML
            analysis_path = os.path.join(self.output_dir, "analisis_copywriting_openai.html")
            html_content = self._convert_markdown_to_html(analysis_result)
            
            with open(analysis_path, 'w', encoding='utf-8') as f:
                f.write("<!DOCTYPE html>\n")
                f.write("<html lang='es'>\n")
                f.write("<head>\n")
                f.write("    <meta charset='UTF-8'>\n")
                f.write("    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
                f.write("    <title>Análisis de Copywriting con OpenAI Vision</title>\n")
                f.write("    <style>\n")
                f.write("        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n")
                f.write("        h1 { color: #333; border-bottom: 2px solid #007bff; }\n")
                f.write("        .meta { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }\n")
                f.write("        .content { line-height: 1.6; }\n")
                f.write("        strong { color: #007bff; }\n")
                f.write("        ul { background: #f8f9fa; padding: 15px; border-radius: 5px; }\n")
                f.write("        li { margin: 5px 0; }\n")
                f.write("    </style>\n")
                f.write("</head>\n")
                f.write("<body>\n")
                f.write("    <h1>ANÁLISIS DE COPYWRITING CON OPENAI VISION</h1>\n")
                f.write("    <div class='meta'>\n")
                f.write(f"        <strong>Fecha:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>\n")
                f.write(f"        <strong>Imágenes analizadas:</strong> {len(images_for_analysis)}<br>\n")
                f.write(f"        <strong>Modelo:</strong> gpt-4o\n")
                f.write("    </div>\n")
                f.write("    <div class='content'>\n")
                f.write("        <h2>RESULTADO DEL ANÁLISIS</h2>\n")
                f.write(f"        {html_content}\n")
                f.write("    </div>\n")
                f.write("    <hr>\n")
                f.write("    <p><em>Análisis generado automáticamente</em></p>\n")
                f.write("</body>\n")
                f.write("</html>\n")
            
            print(f"📄 Análisis guardado en: analisis_copywriting_openai.html")
            return analysis_result
            
        except Exception as e:
            print(f"❌ Error en análisis con OpenAI: {e}")
            print(f"❌ Tipo de error: {type(e).__name__}")
            import traceback
            print(f"❌ Traceback completo:")
            traceback.print_exc()
            return None
            
    async def scrape_carousel(self, url):
        """Proceso principal de scraping del producto"""
        # Crear directorio de salida
        product_id = url.split('/')[-1].split('.')[0]
        self.output_dir = os.path.join(self.output_dir, f"producto_{product_id}")
        os.makedirs(self.output_dir, exist_ok=True)
        # Subcarpeta específica para imágenes
        self.images_dir = os.path.join(self.output_dir, "imagenes")
        os.makedirs(self.images_dir, exist_ok=True)

        await self.setup_browser()

        try:
            # Navegar a la página
            if not await self.navigate_to_product(url):
                return False

            print(f"\n🚀 Iniciando descarga de imágenes...")
            print("-" * 50)

            # Descargar imágenes del producto
            print("\n📥 Descargando imágenes del producto...")
            download_result = await download_images(self.page, self.images_dir)
            self.downloaded_images = download_result.get('images', [])

            if not self.downloaded_images:
                print("❌ No se pudieron descargar las imágenes")
                return False

            print(f"✅ Se descargaron {len(self.downloaded_images)} imágenes")

            # Generar reporte básico
            await self.generate_report(url)
            
            # Análisis con OpenAI
            print(f"\n🤖 Iniciando análisis de copywriting con OpenAI...")
            analysis_result = await self.analyze_images_with_openai()

            print(f"\n🎉 Scraping completado!")
            print(f"📸 Imágenes descargadas: {len(self.downloaded_images)}")
            if analysis_result:
                print(f"🤖 Análisis OpenAI: {os.path.join(self.output_dir, 'analisis_copywriting_openai.html')}")
                # Guardar respuesta original de OpenAI sin modificaciones
                try:
                    rtf_path = os.path.join(self.output_dir, "rich_text_field.json")
                    rtf_data = {
                        "content": analysis_result,
                        "format": "markdown",
                        "model": "gpt-4o",
                        "generated_at": datetime.utcnow().isoformat() + "Z"
                    }
                    with open(rtf_path, 'w', encoding='utf-8') as rf:
                        json.dump(rtf_data, rf, ensure_ascii=False, indent=2)
                    print(f"✅ rich_text_field.json generado: {rtf_path}")
                except Exception as e:
                    print(f"❌ Error creando rich_text_field.json: {e}")
                try:
                    html_analysis_path = os.path.join(self.output_dir, 'analisis_copywriting_openai.html')
                    if os.path.isfile(html_analysis_path):
                        data = convert_analysis_html_to_json(html_analysis_path)
                        base = os.path.splitext(html_analysis_path)[0]
                        json_path = base + '.json'
                        with open(json_path, 'w', encoding='utf-8') as jf:
                            json.dump(data, jf, ensure_ascii=False, indent=2)
                        print(f"✅ Convertido análisis a JSON: {json_path}")
                    else:
                        print("⚠️ No se encontró analisis_copywriting_openai.html para convertir.")
                except Exception as e:
                    print(f"❌ Error convirtiendo análisis a JSON: {e}")

                # Actualizar metafields en Shopify automáticamente tras generar rich_text_field.json
                try:
                    print("\n🚀 Actualizando metafields en Shopify automáticamente...")
                    id_str = input("🆔 ID numérico del producto Shopify: ").strip()
                    if not id_str:
                        print("⚠️ ID vacío; omitiendo actualización de metafields.")
                    else:
                        try:
                            pid = int(id_str)
                        except ValueError:
                            print("❌ ID inválido; debe ser numérico. Omite actualización.")
                            pid = None

                        if pid is not None:
                            shop = os.getenv("SHOPIFY_SHOP", "").strip()
                            token = os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()
                            if not shop or not token:
                                print("⚠️ Faltan variables de entorno SHOPIFY_SHOP o SHOPIFY_ACCESS_TOKEN. Configura .env y reintenta.")
                            else:
                                cmd = [
                                    "python3",
                                    os.path.join(os.getcwd(), "generate_and_put_metafields.py"),
                                    "--product-id", str(pid),
                                    "--input-json", rtf_path,
                                    "--shop", shop,
                                    "--token", token,
                                    "--auto-update-title"
                                ]
                                print(f"🔧 Ejecutando actualización de metafields: {' '.join(cmd)}")
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                # Mostrar salida del script
                                if result.stdout:
                                    print(result.stdout)
                                if result.returncode != 0:
                                    print(f"❌ Error ejecutando actualización de metafields (código {result.returncode}):")
                                    if result.stderr:
                                        print(result.stderr)
                                else:
                                    print("✅ Metafields actualizados correctamente. Revisa Shopify y los archivos put_updates_* en el proyecto.")
                                    # Exportar metafields a JSON automáticamente usando el mismo ID
                                    try:
                                        data = fetch_product_metafields(pid, shop or None)
                                        out_path = os.path.join(self.output_dir, f"metafields_{pid}.json")
                                        save_metafields_json(data, out_path)
                                        print(f"📦 Metafields exportados: {out_path} (metafields={data.get('count')})")
                                    except Exception as e:
                                        print(f"⚠️ No se pudo exportar metafields tras la actualización: {e}")
                except Exception as e:
                    print(f"❌ Error en actualización automática de metafields: {e}")

            return True
            
        finally:
            await self.browser.close()
            await self.playwright.stop()
            
    async def generate_report(self, url):
        """Genera archivo con información de las imágenes descargadas"""

        if self.downloaded_images:
            report_path = os.path.join(self.output_dir, "imagenes_descargadas.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("IMÁGENES DESCARGADAS DEL PRODUCTO\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Producto: {url}\n")
                f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total de imágenes: {len(self.downloaded_images)}\n\n")

                for i, img in enumerate(self.downloaded_images, 1):
                    f.write(f"# Imagen {i}: {img.get('filename', 'sin nombre')}\n")
                    f.write(f"   Tamaño: {img.get('size', 0) / 1024:.1f} KB\n")
                    f.write(f"   URL: {img.get('url', 'N/A')}\n\n")

            print(f"📄 Reporte de imágenes guardado en: {report_path}")

async def main():
    print("🔍 Scraper de productos de AliExpress")
    print("=" * 50)
    
    # Solicitar URL interactivamente
    while True:
        url = input("📎 Ingresa la URL del producto de AliExpress: ").strip()
        if url:
            if "aliexpress.com" in url:
                break
            else:
                print("⚠️ Por favor ingresa una URL válida de AliExpress")
        else:
            print("⚠️ La URL no puede estar vacía")
    
    output_dir = "hover_carrusel"
    
    print(f"\n📋 Configuración del scraping:")
    print(f"📍 URL: {url}")
    print(f"📁 Directorio: {output_dir}")
    
    print(f"\n🚀 Iniciando scraping...")
    scraper = AliExpressImageScraper(output_dir)
    success = await scraper.scrape_carousel(url)
    
    if success:
        print("✅ Scraping completado exitosamente")
    else:
        print("❌ Error en el scraping")

if __name__ == "__main__":
    asyncio.run(main())