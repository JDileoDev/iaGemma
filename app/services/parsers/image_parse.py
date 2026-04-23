import io 
import os
import pytesseract
from PIL import Image

# Configuración de ruta para Windows (local)
# En el servidor de la empresa, esto se manejará vía variables de entorno
tesseract_path = os.getenv("TESSERACT_CMD", r'D:\tesseract\tesseract.exe')
pytesseract.pytesseract.tesseract_cmd = tesseract_path

def parse_image(file_bytes: bytes) -> str:
    imagen = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(imagen, lang="spa+eng").strip()
