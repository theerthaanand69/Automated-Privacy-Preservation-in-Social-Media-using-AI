import os
import xml.etree.ElementTree as ET

# Paths
IMAGE_DIR = "dataset/images"
ANNOTATION_DIR = "dataset/labels"   # You renamed annotations to labels
OUTPUT_DIR = "dataset/labels"       # Save txt in same folder

os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert(size, box):
    dw = 1. / size[0]
    dh = 1. / size[1]

    x_center = (box[0] + box[1]) / 2.0
    y_center = (box[2] + box[3]) / 2.0
    width = box[1] - box[0]
    height = box[3] - box[2]

    x_center *= dw
    width *= dw
    y_center *= dh
    height *= dh

    return (x_center, y_center, width, height)


for xml_file in os.listdir(ANNOTATION_DIR):
    if not xml_file.endswith(".xml"):
        continue

    tree = ET.parse(os.path.join(ANNOTATION_DIR, xml_file))
    root = tree.getroot()

    size = root.find("size")
    w = int(size.find("width").text)
    h = int(size.find("height").text)

    output_path = os.path.join(
        OUTPUT_DIR,
        xml_file.replace(".xml", ".txt")
    )

    with open(output_path, "w") as output_file:

        for obj in root.iter("object"):
            cls_id = 0  # license plate class

            xmlbox = obj.find("bndbox")
            b = (
                float(xmlbox.find("xmin").text),
                float(xmlbox.find("xmax").text),
                float(xmlbox.find("ymin").text),
                float(xmlbox.find("ymax").text)
            )

            bb = convert((w, h), b)

            output_file.write(
                f"{cls_id} {' '.join([str(a) for a in bb])}\n"
            )

print("✅ Conversion completed!")
