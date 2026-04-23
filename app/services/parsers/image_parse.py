import io 
import pytesseract
from PIL import Image

def parse_image(file_bytes: bytes) -> str:
    imagen = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(imagen, lang="spa+eng").strip()
