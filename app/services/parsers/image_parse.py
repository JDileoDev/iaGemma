import io 
import os
import pytesseract
from PIL import Image
import shutil

# Configuración de ruta para Windows (local)
# 1. Buscamos dónde está instalado tesseract en el sistema
# shutil.which busca el ejecutable automáticamente en el PATH de Linux
tesseract_bin = shutil.which("tesseract")

if tesseract_bin:
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin
else:
    pytesseract.pytesseract.tesseract_cmd = r'D:\tesseract\tesseract.exe'


def parse_image(file_bytes: bytes) -> str:
    imagen = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(imagen, lang="spa+eng").strip()
