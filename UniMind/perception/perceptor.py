from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from modelscope import snapshot_download, AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from PIL import Image
import os
from UniMind.device.controller import get_screenshot
from .icon_localization import det
from UniMind.utils.image_utils import crop, draw_coordinates_on_image, get_all_files_in_folder
from UniMind.utils.api_client import generate_api, generate_local
import config
from .text_localization import ocr

CAPTION_MODEL = config.models.Perceptor.CAPTION_MODEL
CAPTION_CALL_METHOD = config.models.Perceptor.CAPTION_CALL_METHOD

def load_perception_models(
    device="cuda",
    caption_call_method=CAPTION_CALL_METHOD,
    caption_model=CAPTION_MODEL,
    groundingdino_model=config.models.Perceptor.GROUNDINGDINO_MODEL,
    groundingdino_revision=config.models.Perceptor.GROUNDINGDINO_REVISION,
    ocr_detection_model=config.models.Perceptor.OCR_DETECTION_MODEL,
    ocr_recognition_model=config.models.Perceptor.OCR_RECOGNITION_MODEL,
    ):

    ### Load caption model ###
    if caption_call_method == "local":
        if caption_model == "qwen-vl-chat":
            model_dir = snapshot_download('qwen/Qwen-VL-Chat', revision='v1.1.0')
            vlm_model = AutoModelForCausalLM.from_pretrained(model_dir, device_map=device, trust_remote_code=True).eval()
            vlm_model.generation_config = GenerationConfig.from_pretrained(model_dir, trust_remote_code=True)
        elif caption_model == "qwen-vl-chat-int4":
            qwen_dir = snapshot_download("qwen/Qwen-VL-Chat-Int4", revision='v1.0.0')
            vlm_model = AutoModelForCausalLM.from_pretrained(qwen_dir, device_map=device, trust_remote_code=True,use_safetensors=True).eval()
            vlm_model.generation_config = GenerationConfig.from_pretrained(qwen_dir, trust_remote_code=True, do_sample=False)
        else:
            print("If you choose local caption method, you must choose the caption model from \"Qwen-vl-chat\" and \"Qwen-vl-chat-int4\"")
            exit(0)
        vlm_tokenizer = AutoTokenizer.from_pretrained(qwen_dir, trust_remote_code=True)
    elif caption_call_method == "api":
        vlm_model = None
        vlm_tokenizer = None
        pass
    else:
        print("You must choose the caption model call function from \"local\" and \"api\"")
        exit(0)


    ### Load ocr and icon detection model ###
    groundingdino_dir = snapshot_download(groundingdino_model, revision=groundingdino_revision)
    groundingdino_model = pipeline('grounding-dino-task', model=groundingdino_dir)
    ocr_detection = pipeline(Tasks.ocr_detection, model=ocr_detection_model) # dbnet (no tensorflow)
    ocr_recognition = pipeline(Tasks.ocr_recognition, model=ocr_recognition_model)

    print("INFO: Loaded perception models:")
    print("\t- Caption model method:", caption_call_method, "| caption vlm model:", caption_model)
    print("\t- Grounding DINO model:", groundingdino_model)
    print("\t- OCR detection model:", ocr_detection_model)
    print("\t- OCR recognition model:", ocr_recognition_model)
    return ocr_detection, ocr_recognition, groundingdino_model, vlm_model, vlm_tokenizer


def merge_text_blocks(
    text_list,
    coordinates_list,
    x_distance_threshold=45,
    y_distance_min=-20,
    y_distance_max=30,
    height_difference_threshold=20,
):
    merged_text_blocks = []
    merged_coordinates = []

    # Sort the text blocks based on y and x coordinates
    sorted_indices = sorted(
        range(len(coordinates_list)),
        key=lambda k: (coordinates_list[k][1], coordinates_list[k][0]),
    )
    sorted_text_list = [text_list[i] for i in sorted_indices]
    sorted_coordinates_list = [coordinates_list[i] for i in sorted_indices]

    num_blocks = len(sorted_text_list)
    merge = [False] * num_blocks

    for i in range(num_blocks):
        if merge[i]:
            continue

        anchor = i
        group_text = [sorted_text_list[anchor]]
        group_coordinates = [sorted_coordinates_list[anchor]]

        for j in range(i + 1, num_blocks):
            if merge[j]:
                continue

            # Calculate differences and thresholds
            x_diff_left = abs(sorted_coordinates_list[anchor][0] - sorted_coordinates_list[j][0])
            x_diff_right = abs(sorted_coordinates_list[anchor][2] - sorted_coordinates_list[j][2])

            y_diff = sorted_coordinates_list[j][1] - sorted_coordinates_list[anchor][3]
            height_anchor = sorted_coordinates_list[anchor][3] - sorted_coordinates_list[anchor][1]
            height_j = sorted_coordinates_list[j][3] - sorted_coordinates_list[j][1]
            height_diff = abs(height_anchor - height_j)

            if (
                (x_diff_left + x_diff_right) / 2 < x_distance_threshold
                and y_distance_min <= y_diff < y_distance_max
                and height_diff < height_difference_threshold
            ):
                group_text.append(sorted_text_list[j])
                group_coordinates.append(sorted_coordinates_list[j])
                merge[anchor] = True
                anchor = j
                merge[anchor] = True

        merged_text = "\n".join(group_text)
        min_x1 = min(group_coordinates, key=lambda x: x[0])[0]
        min_y1 = min(group_coordinates, key=lambda x: x[1])[1]
        max_x2 = max(group_coordinates, key=lambda x: x[2])[2]
        max_y2 = max(group_coordinates, key=lambda x: x[3])[3]

        merged_text_blocks.append(merged_text)
        merged_coordinates.append([min_x1, min_y1, max_x2, max_y2])
    return merged_text_blocks, merged_coordinates



class Perceptor:
    def __init__(self, adb_path, perception_args = None):
        if perception_args is None:
            perception_args = config.models.perceptor.to_dict()
        self.ocr_detection, self.ocr_recognition, self.groundingdino_model, \
            self.vlm_model, self.vlm_tokenizer = load_perception_models(**perception_args)
        self.adb_path = adb_path

    def get_perception_infos(self, screenshot_file, temp_file=config.paths.TEMP_DIR):
        get_screenshot(self.adb_path)
        
        width, height = Image.open(screenshot_file).size
        
        text, coordinates = ocr(screenshot_file, self.ocr_detection, self.ocr_recognition)
        text, coordinates = merge_text_blocks(text, coordinates)
        
        center_list = [[(coordinate[0]+coordinate[2])/2, (coordinate[1]+coordinate[3])/2] for coordinate in coordinates]
        draw_coordinates_on_image(screenshot_file, center_list)
        
        perception_infos = []
        for i in range(len(coordinates)):
            perception_info = {"text": "text: " + text[i], "coordinates": coordinates[i]}
            perception_infos.append(perception_info)
            
        coordinates = det(screenshot_file, "icon", self.groundingdino_model)
        
        for i in range(len(coordinates)):
            perception_info = {"text": "icon", "coordinates": coordinates[i]}
            perception_infos.append(perception_info)
            
        image_box = []
        image_id = []
        for i in range(len(perception_infos)):
            if perception_infos[i]['text'] == 'icon':
                image_box.append(perception_infos[i]['coordinates'])
                image_id.append(i)
        
        MIN_ICON_SIZE = 28  # Qwen-VL API的最小尺寸要求

        valid_icons_to_crop = []

        for i in range(len(image_box)):
            box = image_box[i]
            # box 格式是 [x1, y1, x2, y2]
            box_width = box[2] - box[0]
            box_height = box[3] - box[1]

            # 【关键修复】增加尺寸过滤器
            if box_width >= MIN_ICON_SIZE and box_height >= MIN_ICON_SIZE:
                # 如果尺寸有效，将它的信息保存下来
                valid_icons_to_crop.append({
                    "box": box,
                    "id": image_id[i]
                })
            else:
                # 打印一条日志，告诉我们过滤掉了一个过小的“假图标”
                print(f"DEBUG: Skipped a small detected box (width={box_width}, height={box_height}) at original index {image_id[i]} as it's likely not a valid icon.")
                # 对于被过滤掉的无效图标，我们将其从 perception_infos 中移除或标记为无效
                # 一个简单的方法是将其文本置空，以便后续逻辑可以忽略它
                perception_infos[image_id[i]]['text'] = '' # 标记为无效


        # 现在，我们只对通过了尺寸检查的有效图标进行裁剪
        for icon_info in valid_icons_to_crop:
            crop(screenshot_file, icon_info["box"], icon_info["id"], temp_file=temp_file)

        images = get_all_files_in_folder(temp_file)
        if len(images) > 0:
            images = sorted(images, key=lambda x: int(x.split('/')[-1].split('.')[0]))
            image_id = [int(image.split('/')[-1].split('.')[0]) for image in images]
            icon_map = {}
            prompt = 'This image is an icon from a phone screen. Please briefly describe the shape and color of this icon in one sentence.'
            if CAPTION_CALL_METHOD == "local":
                for i in range(len(images)):
                    image_path = os.path.join(temp_file, images[i])
                    icon_width, icon_height = Image.open(image_path).size
                    if icon_height > 0.8 * height or icon_width * icon_height > 0.2 * width * height:
                        des = "None"
                    else:
                        des = generate_local(self.vlm_tokenizer, self.vlm_model, image_path, prompt)
                    icon_map[i+1] = des
            else:
                for i in range(len(images)):
                    images[i] = os.path.join(temp_file, images[i])
                icon_map = generate_api(images, prompt, caption_model=CAPTION_MODEL)
            for i, j in zip(image_id, range(1, len(image_id)+1)):
                if icon_map.get(j):
                    perception_infos[i]['text'] = "icon: " + icon_map[j]
        
        final_perception_infos = [info for info in perception_infos if info.get('text')]
        for i in range(len(final_perception_infos)):
            final_perception_infos[i]['coordinates'] = [int((final_perception_infos[i]['coordinates'][0]+final_perception_infos[i]['coordinates'][2])/2), int((final_perception_infos[i]['coordinates'][1]+final_perception_infos[i]['coordinates'][3])/2)]
            
        return final_perception_infos, width, height
