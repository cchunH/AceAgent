from PIL import Image, ImageDraw
import os
import base64
from pathlib import Path

import config

def get_all_files_in_folder(folder_path):
    file_list = []
    for file_name in os.listdir(folder_path):
        file_list.append(file_name)
    return file_list

def draw_coordinates_on_image(image_path, coordinates):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    point_size = 10
    for coord in coordinates:
        draw.ellipse((coord[0] - point_size, coord[1] - point_size, coord[0] + point_size, coord[1] + point_size), fill='red')
    output_image_path = './screenshot/output_image.png'
    image.save(output_image_path)
    return output_image_path


def crop(image, box, i, temp_file=config.paths.TEMP_DIR):
    image = Image.open(image)
    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
    if x1 >= x2-10 or y1 >= y2-10:
        return
    cropped_image = image.crop((x1, y1, x2, y2))
    save_path = os.path.join(temp_file, f"{i}.jpg")
    cropped_image.save(save_path)

def encode_image_to_base64_data_uri(image_path):
    """将图片文件编码为Base64 Data URI，这是OpenAI兼容API的标准格式"""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        ext = Path(image_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        else:
            mime_type = 'image/jpeg'
        return f"data:{mime_type};base64,{encoded_string}"
