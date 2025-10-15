#!/usr/bin/env python3
"""
Módulo para descargar imágenes de productos de AliExpress
Extrae URLs de imágenes desde el DOM y las descarga en resolución completa
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Optional
import requests
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


def get_full_image_url(image_url: str) -> str:
    """
    Convierte URL de imagen thumbnail a URL de imagen en tamaño completo
    Elimina sufijos como _80x80.jpg, _50x50.jpg, etc.
    """
    # Eliminar sufijos de tamaño como _80x80, _50x50, _640x640, etc.
    cleaned_url = re.sub(r'_\d+x\d+(\.\w+)$', r'\1', image_url)

    # Asegurar HTTPS
    if cleaned_url.startswith('//'):
        cleaned_url = 'https:' + cleaned_url
    elif not cleaned_url.startswith('http'):
        cleaned_url = 'https://' + cleaned_url

    return cleaned_url


async def extract_image_urls(page: Page) -> List[str]:
    """
    Extrae las URLs de imágenes del producto desde el objeto JavaScript de AliExpress

    Args:
        page: Página de Playwright ya cargada

    Returns:
        Lista de URLs de imágenes
    """
    print("🖼️  Extrayendo URLs de imágenes...")

    # Intentar extraer desde el objeto global de datos
    image_data = await page.evaluate("""
        () => {
            try {
                // Intentar obtener lista de imágenes desde el objeto global de datos
                if (window._d_c_ && window._d_c_.DCData && window._d_c_.DCData.imagePathList) {
                    return {
                        mainImages: window._d_c_.DCData.imagePathList,
                        thumbnails: window._d_c_.DCData.summImagePathList || []
                    };
                }
                return null;
            } catch (e) {
                return null;
            }
        }
    """)

    image_urls = []

    if image_data and image_data.get('mainImages'):
        image_urls = image_data['mainImages']
        print(f"✅ Encontradas {len(image_urls)} imágenes principales")
    else:
        print("⚠️  No se encontraron imágenes en la ubicación esperada")
        print("🔄 Intentando método alternativo...")

        # Fallback: buscar imágenes en la página
        fallback_images = await page.evaluate("""
            () => {
                const images = [];
                // Intentar encontrar elementos de imagen en selectores comunes del carrusel
                const selectors = [
                    '.images-view-item img',
                    '.image-view-magnifier-wrap img',
                    '[class*="imageView"] img'
                ];

                for (const selector of selectors) {
                    const imgs = document.querySelectorAll(selector);
                    imgs.forEach(img => {
                        if (img.src && !images.includes(img.src)) {
                            images.push(img.src);
                        }
                    });
                    if (images.length > 0) break;
                }
                return images;
            }
        """)

        if fallback_images:
            image_urls = fallback_images
            print(f"✅ Encontradas {len(image_urls)} imágenes (método alternativo)")
        else:
            raise Exception("No se pudieron extraer las URLs de las imágenes")

    return image_urls


async def download_images(page: Page, output_dir: str) -> Dict:
    """
    Descarga las imágenes principales del producto de AliExpress

    Args:
        page: Página de Playwright ya cargada con el producto
        output_dir: Directorio donde guardar las imágenes

    Returns:
        dict: Información sobre las imágenes descargadas
    """
    try:
        # Asegurar que el directorio existe
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Extraer URLs de imágenes
        image_urls = await extract_image_urls(page)

        if not image_urls:
            raise Exception("No se encontraron imágenes para descargar")
    except Exception as e:
        print(f"❌ Error extrayendo URLs de imágenes: {e}")
        raise

    # Descargar imágenes
    downloaded_images = []
    print(f"\n📥 Descargando {len(image_urls)} imágenes...\n")

    for idx, img_url in enumerate(image_urls, 1):
        try:
            # Obtener URL de imagen en tamaño completo
            full_img_url = get_full_image_url(img_url)

            print(f"  [{idx}/{len(image_urls)}] Descargando imagen...")

            # Descargar imagen
            response = requests.get(full_img_url, timeout=30)
            response.raise_for_status()

            # Determinar extensión del archivo
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'webp' in content_type:
                ext = 'webp'
            else:
                # Intentar obtener desde la URL
                from urllib.parse import urlparse
                ext = Path(urlparse(full_img_url).path).suffix.lstrip('.') or 'jpg'

            # Guardar imagen
            image_filename = f"image_{idx:02d}.{ext}"
            image_path = os.path.join(output_dir, image_filename)

            with open(image_path, 'wb') as f:
                f.write(response.content)

            size_kb = len(response.content) / 1024
            print(f"      ✅ {image_filename} ({size_kb:.1f} KB)")

            downloaded_images.append({
                'filename': image_filename,
                'path': image_path,
                'url': full_img_url,
                'size': len(response.content)
            })

        except Exception as e:
            print(f"      ❌ Error descargando imagen {idx}: {e}")
            continue

    if not downloaded_images:
        raise Exception("No se pudo descargar ninguna imagen")

    print(f"\n✅ Se descargaron {len(downloaded_images)} imágenes en {output_dir}")

    return {
        'total_images': len(downloaded_images),
        'images': downloaded_images,
        'output_dir': output_dir
    }
