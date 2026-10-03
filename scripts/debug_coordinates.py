import json
import os
import glob
from pathlib import Path
import cv2

CONFIG_PATH = os.path.join("config", "coordinates.json")
OUTPUT_DIR = "debug_output"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def process_image(img_path, config, output_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Failed to load image: {img_path}")
        return

    h, w, _ = img.shape
    
    # Optional: Check aspect ratio (e.g., 16:9)
    # expected_ratio = 16 / 9
    # actual_ratio = w / h
    # if abs(actual_ratio - expected_ratio) > 0.05:
    #     print(f"Warning: {img_path} is not 16:9. Layout might be off.")

    regions = config.get("regions", {})
    
    # Draw boxes
    for label, coords in regions.items():
        x_start = int(coords["x"] * w)
        y_start = int(coords["y"] * h)
        box_w = int(coords["w"] * w)
        box_h = int(coords["h"] * h)
        
        x_end = x_start + box_w
        y_end = y_start + box_h
        
        # Draw Rectangle (Red)
        cv2.rectangle(img, (x_start, y_start), (x_end, y_end), (0, 0, 255), 2)
        
        # Put Label
        # To avoid text going out of bounds
        text_y = y_start - 5 if y_start - 5 > 10 else y_start + 15
        cv2.putText(img, label, (x_start, text_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)

    cv2.imwrite(output_path, img)
    print(f"Saved debug image: {output_path}")

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    config = load_config()
    
    # Get all sample images from test_images directory
    # User can place their images in 'test_images' folder.
    test_dir = "test_images"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        print(f"Created '{test_dir}' folder. Please place the 4 reference images inside and run this script again.")
        return

    image_paths = glob.glob(os.path.join(test_dir, "*.[jp][pn]g"))
    if not image_paths:
        print(f"No images found in '{test_dir}' folder. Please place the 4 reference images there.")
        return

    for i, img_path in enumerate(image_paths, start=1):
        filename = os.path.basename(img_path)
        out_path = os.path.join(OUTPUT_DIR, f"debug_{filename}")
        process_image(img_path, config, out_path)

if __name__ == "__main__":
    main()
