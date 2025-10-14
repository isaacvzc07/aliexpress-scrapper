# AliExpress to Shopify Product Scraper & Metafields Manager

<div align="center">

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991.svg)
![Shopify](https://img.shields.io/badge/Shopify-Admin%20API-96bf48.svg)

**Automated product scraping from AliExpress with AI-powered copywriting and seamless Shopify metafield integration**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Configuration](#-configuration) • [Documentation](#-documentation)

</div>

---

## 📋 Overview

This project automates the complete workflow of scraping product information from AliExpress, generating professional product descriptions using OpenAI's GPT-4o Vision API, and automatically updating Shopify product metafields with structured, rich content.

### **What It Does**

1. **Scrapes AliExpress Products** - Captures product images using Playwright browser automation
2. **AI-Powered Copywriting** - Analyzes images with OpenAI Vision API to generate compelling product descriptions
3. **Shopify Integration** - Automatically updates product metafields with structured content
4. **Robust Parsing** - Handles multiple markdown formats and validates content before updating

---

## ✨ Features

### 🤖 **AI-Powered Content Generation**
- OpenAI GPT-4o Vision API integration
- Custom copywriting prompts for product marketing
- Supports multiple product images analysis
- Generates structured content: bullets, FAQs, technical details, and video sections

### 🎯 **Smart Product Scraping**
- Automated AliExpress carousel image capture
- Hover-based thumbnail navigation
- High-resolution screenshots (1280x720)
- Handles dynamic content loading

### 🔄 **Shopify Metafields Management**
- Automatic metafield creation and updates via GraphQL
- Support for multiple metafield types (rich_text, number, single_line_text)
- Batch operations (up to 25 metafields per request)
- Automatic type conversion and validation

### 🛡️ **Robust Error Handling**
- Content validation before Shopify updates
- Detailed error diagnostics
- Handles OpenAI content policy rejections
- Graceful fallbacks for parsing edge cases

### 📊 **Export & Inspection**
- Export existing metafields to JSON
- Optional FastAPI server for UI inspection
- Detailed logging and debugging information

---

## 🚀 Installation

### **Prerequisites**

- Python 3.9 or higher
- Shopify store with Admin API access
- OpenAI API key with GPT-4o Vision access
- Git (for cloning the repository)

### **Quick Setup**

#### **macOS/Linux**

```bash
# Clone the repository
git clone https://github.com/isaacvzc07/aliexpress-scrapper.git
cd aliexpress-scrapper

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install requests python-dotenv playwright openai

# Optional: Install UI server dependencies
pip install fastapi uvicorn beautifulsoup4

# Install Playwright browsers
python3 -m playwright install
```

#### **Windows (PowerShell)**

```powershell
# Clone the repository
git clone https://github.com/isaacvzc07/aliexpress-scrapper.git
cd aliexpress-scrapper

# Create virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# If activation is blocked, enable script execution
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Install dependencies
pip install requests python-dotenv playwright openai

# Optional: Install UI server dependencies
pip install fastapi uvicorn beautifulsoup4

# Install Playwright browsers
py -m playwright install
```

---

## ⚙️ Configuration

### **Environment Variables**

Create a `.env` file in the project root:

```env
# Shopify Configuration (Required)
SHOPIFY_SHOP=your-store-name
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI Configuration (Required)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional Configuration
SHOPIFY_API_VERSION=2024-07
SHOPIFY_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SHOPIFY_PASSWORD=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### **Getting Credentials**

#### **Shopify Access Token**

1. Go to your Shopify Admin → **Settings** → **Apps and sales channels**
2. Click **Develop apps** → **Create an app**
3. Configure Admin API scopes:
   - `read_products`
   - `write_products`
   - `read_metaobjects`
   - `write_metaobjects`
4. Install the app and copy the **Admin API access token**

#### **OpenAI API Key**

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Go to **API Keys** → **Create new secret key**
3. Ensure you have access to GPT-4o with Vision

---

## 📖 Usage

### **1. Complete Workflow (Recommended)**

Run the scraper to automatically handle the entire process:

```bash
# macOS/Linux
python3 scraper_hover_carrusel.py

# Windows
py scraper_hover_carrusel.py
```

**Interactive Steps:**

1. Enter AliExpress product URL
2. Confirm scraping configuration
3. Wait for image capture and AI analysis
4. Enter Shopify product ID
5. Automatic metafield updates

**Output:** `hover_carrusel/producto_<ID>/`
- `rich_text_field.json` - AI-generated content
- `analisis_copywriting_openai.html` - Formatted analysis
- `metafields_<shopify_id>.json` - Updated metafields
- `imagenes/` - Captured screenshots

---

### **2. Update Metafields from JSON**

If you already have a `rich_text_field.json` file:

```bash
# macOS/Linux
python3 generate_and_put_metafields.py \
  --product-id 7384820154465 \
  --input-json hover_carrusel/producto_1005007023215594/rich_text_field.json

# Windows
py generate_and_put_metafields.py `
  --product-id 7384820154465 `
  --input-json hover_carrusel/producto_1005007023215594/rich_text_field.json
```

**Options:**
- `--product-id` - Shopify product ID (required)
- `--input-json` - Path to JSON with OpenAI content (required)
- `--shop` - Shopify shop subdomain (optional, uses `.env`)
- `--token` - Shopify access token (optional, uses `.env`)
- `--out-json` - Save generated updates to file (optional)

---

### **3. Export Existing Metafields**

Download current metafields from a Shopify product:

```bash
# macOS/Linux
python3 fetch_product_metafields_to_json.py \
  --id 7384820154465 \
  --out metafields_export.json

# Windows
py fetch_product_metafields_to_json.py `
  --id 7384820154465 `
  --out metafields_export.json
```

---

### **4. Optional: Run UI Inspection Server**

Start a FastAPI server to browse metafields visually:

```bash
# macOS/Linux
python3 -m uvicorn shopify_api:app --host 127.0.0.1 --port 8000

# Windows
py -m uvicorn shopify_api:app --host 127.0.0.1 --port 8000
```

**Available Endpoints:**
- `http://127.0.0.1:8000/` - API documentation
- `http://127.0.0.1:8000/productos_metafields_ui?product_id=<ID>` - Metafields browser
- `http://127.0.0.1:8000/productos_ui` - Products list

---

## 🏗️ Project Structure

```
aliexpress-scrapper/
├── scraper_hover_carrusel.py          # Main scraper with OpenAI integration
├── generate_and_put_metafields.py     # Metafield updater (robust parsing)
├── fetch_product_metafields_to_json.py # Metafield exporter
├── convert_analisis_copywriting_to_json.py # HTML to JSON converter
├── shopify_api.py                     # FastAPI server for UI inspection
├── .env                               # Environment variables (not committed)
├── .env.example                       # Example environment file
├── .gitignore                         # Git ignore rules
├── README.md                          # This file
└── hover_carrusel/                    # Output directory (auto-created)
    └── producto_<ID>/
        ├── rich_text_field.json       # AI-generated content
        ├── analisis_copywriting_openai.html
        ├── analisis_copywriting_openai.json
        ├── metafields_<shopify_id>.json
        └── imagenes/                  # Captured screenshots
```

---

## 🔧 Advanced Configuration

### **Metafields Structure**

The scraper generates and updates the following metafields:

| Key | Type | Description |
|-----|------|-------------|
| `vineta_1` to `vineta_5` | `rich_text_field` | Product bullet points (~110 chars each) |
| `faq_2` to `faq_4` | `rich_text_field` | FAQ answers (price, features, why special) |
| `ancho`, `longitud`, `alto` | `number_decimal` | Product dimensions in cm |
| `piezas` | `number_integer` | Number of pieces/blocks |
| `escala` | `single_line_text_field` | Product scale (e.g., "1:18") |
| `sec5_title` | `single_line_text_field` | Video section title |
| `sec5_body` | `rich_text_field` | Video section body (2 paragraphs) |

All metafields are created under the `custom` namespace.

---

### **Customizing OpenAI Prompt**

Edit the copywriting prompt in `scraper_hover_carrusel.py` (lines 414-463):

```python
copywriting_prompt = {
    "intro": "Your custom instructions...",
    "style": {
        "audience": "young adults",
        "tone": "playful, modern",
        # ...
    },
    # ...
}
```

---

### **Adjusting Temperature**

Control OpenAI response creativity in `scraper_hover_carrusel.py` (line 533):

```python
response = self.openai_client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    max_tokens=2000,
    temperature=0.7  # Lower = more consistent, Higher = more creative
)
```

---

## 🐛 Troubleshooting

### **Common Issues**

#### **1. Playwright Installation Fails**

```bash
# macOS
xcode-select --install
python3 -m playwright install

# Linux
sudo apt-get install libgbm1
python3 -m playwright install
```

#### **2. OpenAI Rejects Request**

**Error:** `"Lo siento, no puedo ayudarte con eso."`

**Causes:**
- Product contains sensitive content (weapons, violence, etc.)
- Images violate OpenAI content policies
- Too many requests (rate limiting)

**Solutions:**
- Try a different product
- Wait and retry (may be a false positive)
- Adjust prompt to be less explicit

#### **3. Shopify Authentication Fails**

**Error:** `401 Unauthorized` or `403 Forbidden`

**Solutions:**
- Verify `SHOPIFY_SHOP` is correct (without `.myshopify.com`)
- Check `SHOPIFY_ACCESS_TOKEN` has required scopes
- Ensure token hasn't expired

#### **4. Parsing Fails (No Content Extracted)**

**Error:** `❌ ERROR CRÍTICO: El parsing del contenido de OpenAI falló`

**Causes:**
- OpenAI returned non-standard format
- Content doesn't follow expected structure

**Solutions:**
- Check `rich_text_field.json` content
- Re-run scraper to get fresh OpenAI response
- Review error diagnostics (shows first 800 chars)

#### **5. No Metafields Updated**

**Possible reasons:**
- Parsing extracted no data (validation prevents empty updates)
- OpenAI response was rejected
- Network issues with Shopify API

**Check:**
- Look for `put_updates_*.json` file
- Review console output for validation errors
- Ensure `.env` credentials are correct

---

## 🔒 Security Best Practices

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use environment variables** - Don't hardcode API keys in scripts
3. **Rotate tokens regularly** - Update Shopify and OpenAI tokens periodically
4. **Review generated content** - Always verify AI-generated text before publishing
5. **Limit API access** - Grant minimum required scopes to Shopify apps

---

## 📚 Documentation

### **Key Features Explained**

#### **Robust Markdown Parsing**

The parser handles multiple OpenAI response formats:
- Accepts `##`, `###`, or `####` section headers
- Extracts FAQ answers even with bold text inside
- Validates content before updating Shopify
- Multiple fallback strategies for edge cases

#### **Smart FAQ Extraction**

New implementation (Solution 4) prevents truncation:
- Searches for `?**` (end of question) pattern
- Handles bold text within answers (e.g., `**motor**`)
- Doesn't split on internal `**` markers
- 3-level fallback system for reliability

#### **Content Validation**

Prevents empty metafield updates:
- Checks for bullets, FAQs, technical details
- Shows diagnostic information on failure
- Fails fast with clear error messages
- Displays problematic content for debugging

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 Changelog

### **Recent Updates**

#### **v1.1.0 (2025-10-14)**
- ✨ Enhanced markdown parser to accept multiple header formats
- 🐛 Fixed FAQ truncation when answers contain bold text
- ✅ Added comprehensive content validation
- 📖 Improved error diagnostics and debugging output
- 🔧 Implemented 3-level fallback system for parsing

#### **v1.0.0 (2025-10-13)**
- 🎉 Initial release
- ✨ AliExpress scraper with Playwright
- 🤖 OpenAI GPT-4o Vision integration
- 🔄 Shopify metafields auto-update
- 📊 FastAPI inspection server

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- [OpenAI](https://openai.com/) - GPT-4o Vision API
- [Shopify](https://shopify.dev/) - Admin API & GraphQL
- [Playwright](https://playwright.dev/) - Browser automation
- [FastAPI](https://fastapi.tiangolo.com/) - UI server framework

---

## 📧 Support

For issues, questions, or suggestions:
- **GitHub Issues**: [Create an issue](https://github.com/isaacvzc07/aliexpress-scrapper/issues)
- **Documentation**: Check this README and inline code comments
- **OpenAI Policies**: Review [OpenAI Usage Policies](https://openai.com/policies/usage-policies)

---

<div align="center">

**Made with ❤️ using OpenAI GPT-4o and Shopify**

[⬆ Back to Top](#aliexpress-to-shopify-product-scraper--metafields-manager)

</div>
