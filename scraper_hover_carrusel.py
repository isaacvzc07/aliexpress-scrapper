#!/usr/bin/env python3
"""
Scraper de carrusel de AliExpress usando eventos HOVER
Detecta thumbnails y usa hover para cambiar la imagen principal
"""

import asyncio
import os
import hashlib
import base64
import json
import subprocess
from datetime import datetime
from playwright.async_api import async_playwright
from openai import OpenAI
from convert_analisis_copywriting_to_json import convert_file as convert_analysis_html_to_json
from fetch_product_metafields_to_json import fetch_product_metafields, save_json as save_metafields_json

class AliExpressHoverScraper:
    def __init__(self, output_dir="hover_carrusel"):
        self.output_dir = output_dir
        self.screenshots = []
        self.hover_count = 0
        # Configuración de OpenAI
        self.openai_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
    async def setup_browser(self):
        """Configura el navegador en modo normal (NO incógnito)"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Visible para debugging
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
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await self.page.wait_for_timeout(2000)  # Esperar a que cargue completamente
            return True
        except Exception as e:
            print(f"❌ Error navegando: {e}")
            return False

            # Confirmación después de navegar a la página
            print(f"\n🌐 Página cargada correctamente")
            print(f"📋 Configuración del scraping:")
            print(f"📍 URL: {url}")
            print(f"🖱️ Hovers: {max_hovers}")
            print("-" * 50)
            
            while True:
                confirmacion = input("¿Deseas continuar con el scraping? (s/n): ").strip().lower()
                if confirmacion in ["s", "si", "sí", "y", "yes"]:
                    break
                elif confirmacion in ["n", "no"]:
                    print("❌ Scraping cancelado por el usuario")
                    await self.browser.close()
                    await self.playwright.stop()
                    return False
                else:
                    print("⚠️ Por favor responde 's' para sí o 'n' para no")
            
            print(f"\n🚀 Continuando con el scraping...")
            print("-" * 50)
            
    async def take_full_viewport_screenshot(self, name, description=""):
        """Toma una captura de pantalla completa del viewport en alta resolución"""
        try:
            screenshot_path = os.path.join(getattr(self, 'images_dir', self.output_dir), f"{name}_viewport_completo.png")
            # Capturar todo el viewport sin recortes
            await self.page.screenshot(
                path=screenshot_path,
                full_page=False  # Solo viewport visible, no toda la página
            )
            self.screenshots.append({
                'name': f"{name}_viewport_completo",
                'path': screenshot_path,
                'description': f"Viewport completo - {description}",
                'timestamp': datetime.now().isoformat(),
                'type': 'viewport_completo',
                'resolution': '1280x720'  # Resolución del viewport configurado
            })
            print(f"📸 Captura viewport completo guardada: {name}_viewport_completo.png")
            return screenshot_path
        except Exception as e:
            print(f"❌ Error capturando viewport completo {name}: {e}")
            return None
            
    async def take_screenshot(self, name, description=""):
        """Toma una captura de pantalla de una región específica del viewport"""
        try:
            screenshot_path = os.path.join(getattr(self, 'images_dir', self.output_dir), f"{name}.png")
            # Capturar solo la región específica (100,80) a (520,500) - 420x420px
            clip_region = {
                'x': 110,
                'y': 90,
                'width': 392,
                'height': 392
            }
            await self.page.screenshot(path=screenshot_path, clip=clip_region)
            self.screenshots.append({
                'name': name,
                'path': screenshot_path,
                'description': description,
                'timestamp': datetime.now().isoformat(),
                'region': f"({clip_region['x']},{clip_region['y']}) - {clip_region['width']}x{clip_region['height']}px",
                'type': 'region_especifica'
            })
            print(f"📸 Captura región específica guardada: {name}")
            return screenshot_path
        except Exception as e:
            print(f"❌ Error capturando {name}: {e}")
            return None
            
    async def find_thumbnail_images(self):
        """Encuentra las imágenes thumbnail del carrusel"""
        print("🔍 Buscando thumbnails del carrusel...")
        
        # Buscar específicamente elementos slider--item--RpyeewA
        thumbnails = await self.page.evaluate("""
            () => {
                const sliderItems = Array.from(document.querySelectorAll('.slider--item--RpyeewA'));
                const thumbnails = [];
                
                sliderItems.forEach((item, index) => {
                    const img = item.querySelector('img');
                    if (img) {
                        const rect = item.getBoundingClientRect();
                        const imgRect = img.getBoundingClientRect();
                        
                        if (rect.top > 0 && rect.left > 0) {
                            thumbnails.push({
                                index: index,
                                src: img.src,
                                width: Math.round(imgRect.width),
                                height: Math.round(imgRect.height),
                                x: Math.round(rect.left + rect.width/2), // Centro del elemento
                                y: Math.round(rect.top + rect.height/2),
                                alt: img.alt || '',
                                className: item.className || '',
                                parentTag: item.tagName,
                                isSliderItem: true
                            });
                        }
                    }
                });
                
                // También buscar imágenes pequeñas como fallback
                const images = Array.from(document.querySelectorAll('img[src*="alicdn.com"]'));
                images.forEach((img, index) => {
                    const rect = img.getBoundingClientRect();
                    const computedStyle = window.getComputedStyle(img);
                    
                    // Filtrar imágenes pequeñas que podrían ser thumbnails
                    if (rect.width > 20 && rect.width <= 150 && 
                        rect.height > 20 && rect.height <= 150 &&
                        rect.top > 0 && rect.left > 0 &&
                        computedStyle.visibility !== 'hidden' &&
                        computedStyle.display !== 'none') {
                        
                        // Evitar duplicados con slider items
                        const isDuplicate = thumbnails.some(thumb => 
                            Math.abs(thumb.x - rect.left) < 20 && 
                            Math.abs(thumb.y - rect.top) < 20
                        );
                        
                        if (!isDuplicate) {
                            thumbnails.push({
                                index: index + 1000, // Offset para distinguir
                                src: img.src,
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                                x: Math.round(rect.left),
                                y: Math.round(rect.top),
                                alt: img.alt || '',
                                className: img.className || '',
                                parentTag: img.parentElement ? img.parentElement.tagName : 'NONE',
                                isSliderItem: false
                            });
                        }
                    }
                });
                
                // Ordenar por posición (izquierda a derecha, arriba a abajo)
                thumbnails.sort((a, b) => {
                    if (Math.abs(a.y - b.y) < 50) { // Misma fila aproximadamente
                        return a.x - b.x; // Ordenar por x
                    }
                    return a.y - b.y; // Ordenar por y
                });
                
                return thumbnails;
            }
        """)
        
        print(f"📊 Thumbnails encontrados: {len(thumbnails)}")
        for i, thumb in enumerate(thumbnails[:10]):  # Mostrar solo los primeros 10
            print(f"  {i+1}. {thumb['width']}x{thumb['height']} en ({thumb['x']}, {thumb['y']}) - {thumb['className']}")
            
        return thumbnails
        
    async def hover_thumbnail(self, thumbnail):
        """Hace hover sobre un thumbnail específico"""
        try:
            # Usar las coordenadas del thumbnail para hacer hover
            x = thumbnail['x'] + thumbnail['width'] // 2
            y = thumbnail['y'] + thumbnail['height'] // 2
            
            print(f"🖱️ Hover en thumbnail {thumbnail['width']}x{thumbnail['height']} en ({x}, {y})")
            
            # Hacer hover en las coordenadas
            await self.page.mouse.move(x, y)
            await self.page.wait_for_timeout(700)  # Esperar a que cambie la imagen
            
            return True
            
        except Exception as e:
            print(f"❌ Error haciendo hover: {e}")
            return False

            # Confirmación después de navegar a la página
            print(f"\n🌐 Página cargada correctamente")
            print(f"📋 Configuración del scraping:")
            print(f"📍 URL: {url}")
            print(f"🖱️ Hovers: {max_hovers}")
            print("-" * 50)
            
            while True:
                confirmacion = input("¿Deseas continuar con el scraping? (s/n): ").strip().lower()
                if confirmacion in ["s", "si", "sí", "y", "yes"]:
                    break
                elif confirmacion in ["n", "no"]:
                    print("❌ Scraping cancelado por el usuario")
                    await self.browser.close()
                    await self.playwright.stop()
                    return False
                else:
                    print("⚠️ Por favor responde 's' para sí o 'n' para no")
            
            print(f"\n🚀 Continuando con el scraping...")
            print("-" * 50)
            
    async def capture_main_image(self):
        """Captura la imagen principal después del hover"""
        try:
            # Buscar la imagen principal más grande con múltiples estrategias
            main_image_info = await self.page.evaluate("""
                () => {
                    // Estrategia 1: Buscar por selectores específicos de AliExpress
                    const specificSelectors = [
                        'img[class*="magnifier"]',
                        'img[class*="main"]',
                        'img[class*="big"]',
                        'img[class*="large"]',
                        'img[class*="preview"]',
                        '.image-view img',
                        '.magnifier-image img',
                        '[class*="ImageView"] img'
                    ];
                    
                    for (const selector of specificSelectors) {
                        const img = document.querySelector(selector);
                        if (img && img.src && img.src.includes('alicdn.com')) {
                            const rect = img.getBoundingClientRect();
                            if (rect.width > 200 && rect.height > 200) {
                                return {
                                    src: img.src,
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height),
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    selector: selector,
                                    strategy: 'specific_selector'
                                };
                            }
                        }
                    }
                    
                    // Estrategia 2: Buscar la imagen más grande en el centro de la página
                    const images = Array.from(document.querySelectorAll('img[src*="alicdn.com"]'));
                    let mainImage = null;
                    let maxSize = 0;
                    const centerX = window.innerWidth / 2;
                    const centerY = window.innerHeight / 2;
                    
                    images.forEach(img => {
                        const rect = img.getBoundingClientRect();
                        const size = rect.width * rect.height;
                        
                        // Debe ser una imagen grande
                        if (rect.width > 200 && rect.height > 200) {
                            // Calcular distancia al centro
                            const imgCenterX = rect.left + rect.width / 2;
                            const imgCenterY = rect.top + rect.height / 2;
                            const distanceToCenter = Math.sqrt(
                                Math.pow(imgCenterX - centerX, 2) + 
                                Math.pow(imgCenterY - centerY, 2)
                            );
                            
                            // Priorizar imágenes grandes cerca del centro
                            const score = size / (distanceToCenter + 1);
                            
                            if (score > maxSize) {
                                maxSize = score;
                                mainImage = {
                                    src: img.src,
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height),
                                    x: Math.round(rect.left),
                                    y: Math.round(rect.top),
                                    distanceToCenter: Math.round(distanceToCenter),
                                    strategy: 'center_large'
                                };
                            }
                        }
                    });
                    
                    return mainImage;
                }
            """)
            
            if main_image_info:
                print(f"📷 Imagen principal: {main_image_info['width']}x{main_image_info['height']} (estrategia: {main_image_info.get('strategy', 'unknown')})")
                print(f"🔗 URL: {main_image_info['src'][:80]}...")
                return main_image_info
            else:
                print("⚠️ No se encontró imagen principal")
                return None
                
        except Exception as e:
            print(f"❌ Error capturando imagen principal: {e}")
            return None
    
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
        """Analiza las imágenes capturadas usando OpenAI Vision API con el prompt de copywriting"""
        try:
            print("🤖 Iniciando análisis con OpenAI...")
            print(f"📊 Total de screenshots disponibles: {len(self.screenshots)}")
            
            # Prompt de copywriting especializado
            copywriting_prompt = {
                "intro": "Eres un copywriter profesional especializado en crear ofertas irresistibles para páginas de producto en tiendas de e-commerce, dentro del modelo de marketing de respuesta directa. Tu tarea es crear una página de ventas completa, persuasiva y estructurada en formato listado, siguiendo el orden de los metafields que se detalla abajo. Cada vez que te comparta una URL de producto o un screenshot, debes:",
                "style": {
                    "audience": "adultos jóvenes y adultos",
                    "tone": "playful, moderno, coleccionable",
                    "no_sensationalism": True,
                    "bold_keywords": True,
                    "avoid_premium": True,
                    "language": "es"
                },
                "extraction_instructions": "Cuando el usuario proporcione un screenshot o la URL del producto, la IA debe extraer todos los datos posibles: nombre del producto, colección o temática, número de piezas o bloques, funciones mecánicas o de construcción (motor, dirección, suspensión, articulaciones, etc.), escala y dimensiones (alto, ancho, longitud), tipo o estilo del modelo (réplica técnica, set de personajes, vehículo icónico, etc.). Si algún dato esencial (piezas, alto, ancho, longitud o escala) no se observa en las capturas, la IA debe preguntar al usuario si puede proporcionarlo. Si no es posible, proceder con el copy indicando explícitamente que la información no fue observada en las imágenes. También puede preguntar información adicional si ayuda a enriquecer las viñetas, el body o la sección de video/gif.",
                "rules": [
                    "Nunca mencionar la marca LEGO",
                    "Usar palabras clave en negritas para destacar beneficios clave",
                    "Tono playful, moderno, coleccionable, sin sensacionalismo",
                    "Evitar la palabra 'premium' salvo en 'manual impreso premium'",
                    "Cada viñeta debe tener ~110 caracteres",
                    "Los headings de la Sección 4 siempre deben tener signos de exclamación al inicio y al final",
                    "Limitar la longitud de cada párrafo en la Sección 4 a 250–300 caracteres",
                    "Eliminar cualquier CTA de la salida final",
                    "La salida debe generarse siempre en formato listado, alineado al orden de los metafields",
                    "Nunca salirse del formato especificado en este JSON"
                ],
                "sections_order": {
                    "1_vinetas": {
                        "vineta1": "Beneficio funcional o emocional con número de piezas (~110 caracteres)",
                        "vineta2": "Dimensión destacada (alto, ancho o longitud) aplicada al valor de exhibición (~110 caracteres)",
                        "vineta3": "Detalle de diseño o realismo del modelo (~110 caracteres)",
                        "vineta4": "Experiencia de armado (relajante, desafiante, divertida, etc.) (~110 caracteres)",
                        "vineta5": "Regalo o valor coleccionable (~110 caracteres)"
                    },
                    "2_faq": {
                        "¿Qué incluye el precio?": "El set completo con [número de piezas] piezas y manual impreso premium.",
                        "¿Cuáles son las funciones y beneficios clave?": "Incluye [listar funciones principales: motor, dirección, suspensión, articulaciones, etc.] – todo diseñado para una experiencia realista y coleccionable.",
                        "¿Por qué este set es especial?": "Porque combina diseño detallado, funciones realistas y una construcción sólida, convirtiéndolo en una pieza única para fans y coleccionistas."
                    },
                    "3_detalles_tecnicos": {
                        "ancho": "[valor en cm o 'No observado en imágenes']",
                        "longitud": "[valor en cm o 'No observado en imágenes']",
                        "alto": "[valor en cm o 'No observado en imágenes']",
                        "piezas": "[número total de piezas]",
                        "escala": "[valor o 'No observado en imágenes']"
                    },
                    "4_video_section": {
                        "title": "¡[Heading de 4–7 palabras]!",
                        "body": "Dos párrafos de 250–300 caracteres: el primero sobre experiencia de armado y dimensiones; el segundo sobre funciones, valor de exhibición y colección.",
                        "video": "[archivo/video de producto si aplica]"
                    }
                }
            }
            
            # Preparar imágenes para análisis
            images_for_analysis = []
            
            print("🔍 Procesando todas las imágenes capturadas...")
            
            # Procesar todas las imágenes capturadas
            viewport_images = []
            hover_images = []
            
            for screenshot in self.screenshots:
                print(f"   - Screenshot: {screenshot.get('path', 'sin path')} | Tipo: {screenshot.get('type', 'sin tipo')}")
                if screenshot.get('type') == 'viewport_completo':
                    viewport_images.append(screenshot)
                else:
                    hover_images.append(screenshot)
            
            # Agregar todas las imágenes del viewport con alta calidad
            for screenshot in viewport_images:
                base64_image = self.encode_image_to_base64(screenshot['path'])
                if base64_image:
                    images_for_analysis.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "high"
                        }
                    })
                    print(f"✅ Imagen del viewport agregada: {screenshot['path']}")
            
            # Agregar todas las imágenes de hover con calidad media
            for screenshot in hover_images:
                base64_image = self.encode_image_to_base64(screenshot['path'])
                if base64_image:
                    images_for_analysis.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "low"
                        }
                    })
                    print(f"✅ Imagen de hover agregada: {screenshot['path']}")
            
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
                            "text": f"Analiza estas imágenes de producto siguiendo exactamente este prompt de copywriting: {json.dumps(copywriting_prompt, ensure_ascii=False, indent=2)}"
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
            
    async def scrape_carousel(self, url, max_hovers=10):
        """Proceso principal de scraping del carrusel"""
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

            # Confirmación después de navegar a la página
            print(f"\n🌐 Página cargada correctamente")
            print(f"📋 Configuración del scraping:")
            print(f"📍 URL: {url}")
            print(f"🖱️ Hovers: {max_hovers}")
            print("-" * 50)
            
            while True:
                confirmacion = input("¿Deseas continuar con el scraping? (s/n): ").strip().lower()
                if confirmacion in ["s", "si", "sí", "y", "yes"]:
                    break
                elif confirmacion in ["n", "no"]:
                    print("❌ Scraping cancelado por el usuario")
                    await self.browser.close()
                    await self.playwright.stop()
                    return False
                else:
                    print("⚠️ Por favor responde 's' para sí o 'n' para no")
            
            print(f"\n🚀 Continuando con el scraping...")
            print("-" * 50)
                
            # Capturas iniciales - viewport completo y región específica
            await self.take_full_viewport_screenshot("00_pagina_inicial", "Página inicial antes de hover")
            await self.take_screenshot("00_pagina_inicial", "Página inicial antes de hover")
            
            # Encontrar thumbnails
            thumbnails = await self.find_thumbnail_images()
            
            if not thumbnails:
                print("❌ No se encontraron thumbnails")
                return False

            # Hacer hover en cada thumbnail
            main_images = []
            for i, thumbnail in enumerate(thumbnails[:max_hovers]):
                print(f"\n🔄 Procesando thumbnail {i+1}/{min(len(thumbnails), max_hovers)}")
                
                if await self.hover_thumbnail(thumbnail):
                    self.hover_count += 1
                    
                    # Capturar imagen principal y screenshot en paralelo para mayor velocidad
                    import asyncio
                    main_image_task = self.capture_main_image()
                    screenshot_task = self.take_screenshot(
                        f"hover_{i+1:02d}_{thumbnail['width']}x{thumbnail['height']}", 
                        f"Después de hover en thumbnail {i+1}"
                    )
                    
                    # Ejecutar ambas tareas en paralelo
                    main_image, _ = await asyncio.gather(main_image_task, screenshot_task)
                    if main_image:
                        main_images.append(main_image)
                    
                    # Pequeña pausa entre hovers
                    await self.page.wait_for_timeout(150)
                    
            # Captura final del viewport completo después de todos los hovers
            print(f"\n📸 Tomando captura final del viewport completo...")
            await self.take_full_viewport_screenshot("99_final_viewport", "Viewport completo después de todos los hovers")
                    
            # Generar reporte
            await self.generate_report(url, thumbnails, main_images)
            
            # Análisis con OpenAI
            print(f"\n🤖 Iniciando análisis de copywriting con OpenAI...")
            analysis_result = await self.analyze_images_with_openai()

            print(f"\n🎉 Scraping completado!")
            print(f"📊 Thumbnails procesados: {self.hover_count}")
            print(f"📸 Capturas realizadas: {len(self.screenshots)}")
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
            
    async def generate_report(self, url, thumbnails, main_images):
        """Genera archivos auxiliares (sin reporte .txt)"""
        
        # Crear archivo separado con URLs de imágenes principales
        if main_images:
            urls_path = os.path.join(self.output_dir, "imagenes_principales.txt")
            with open(urls_path, 'w', encoding='utf-8') as f:
                f.write("URLS DE IMÁGENES PRINCIPALES DEL CARRUSEL\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Producto: {url}\n")
                f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total de imágenes: {len(main_images)}\n\n")
                
                for i, img in enumerate(main_images, 1):
                    f.write(f"# Imagen {i} ({img['width']}x{img['height']})\n")
                    f.write(f"{img['src']}\n\n")
            
            print(f"📄 URLs de imágenes principales guardadas en: {urls_path}")

async def main():
    print("🔍 Scraper de carrusel AliExpress con hover")
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
    
    # Configurar 7 hovers por defecto (sin preguntar)
    max_hovers = 7
    output_dir = "hover_carrusel"
    
    print(f"\n📋 Configuración del scraping:")
    print(f"�� URL: {url}")
    print(f"🖱️ Hovers: {max_hovers}")
    print(f"📁 Directorio: {output_dir}")
    
    print(f"\n🚀 Iniciando scraping...")
    scraper = AliExpressHoverScraper(output_dir)
    success = await scraper.scrape_carousel(url, max_hovers)
    
    if success:
        print("✅ Scraping completado exitosamente")
    else:
        print("❌ Error en el scraping")

if __name__ == "__main__":
    asyncio.run(main())