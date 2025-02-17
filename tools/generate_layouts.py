#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import pytesseract
from PIL import Image
import json
import os
import unicodedata


def find_squares(img):
    squares = []
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Enhance contrast by thresholding
    _, thresh = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        cnt_len = cv2.arcLength(cnt, True)
        cnt = cv2.approxPolyDP(cnt, 0.02 * cnt_len, True)
        if len(cnt) == 4 and cv2.contourArea(cnt) > 1000 and cv2.isContourConvex(cnt):
            squares.append(cnt)
    return squares


def get_square_position(square):
    x, y, w, h = cv2.boundingRect(square)
    return x, y, w, h


def save_square(img, x, y, w, h, c64_type, key_text, layout, layout_sufix):
    key_name = f"{c64_type}_key_{key_text}"
    filename = f"images/keys/{key_name}.png"
    square_img = img[y : y + h, x : x + w]
    if os.path.exists(filename):
        excisting = cv2.imread(filename)
        if (
            excisting.size == square_img.size
            and np.sum(cv2.subtract(square_img, excisting)) == 0
        ):
            return f"{key_name}.png", False
    key_name = f"{key_name}{layout_sufix}"
    filename = f"images/keys/{key_name}.png"
    print(f"Saving {filename}")
    cv2.imwrite(f"{filename}", square_img)
    return f"{key_name}.png", True


class Rectangle:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def find_point_in_rectangle(rect, points):
    """Finds the first point that lies within the given rectangle."""
    for point in points:
        if (
            rect.x <= point.x <= rect.x + rect.w
            and rect.y <= point.y <= rect.y + rect.h
        ):
            return point
    return None  # Return None if no point fits in the rectangle


def load_config(layout):
    keyboard_matrix = json.load(open(f"config/keyboard_matrix{layout}.json"))
    print(f"Loading config for {keyboard_matrix['layout']} layout.")
    key_matrix = keyboard_matrix["matrix"]

    key_positions = {}
    for key in json.load(open(f"tools/layout_key_pos{layout}.json")):
        key_positions[Point(key["x"] + 10, key["y"] + 10)] = key["text"]

    special_keys = json.load(open(f"config/key_config.json"))["special-keys"]
    return key_matrix, key_positions, special_keys


if __name__ == "__main__":
    c64_types = ["breadbin", "c64c"]
    layouts = [
        "en",
        "sv",
    ]

    for layout in layouts:
        layout_sufix = "_" + layout if layout != "en" else ""
        key_matrix, key_positions, special_keys = load_config(layout_sufix)
        for c64_type in c64_types:
            pressed_keys = f"tools/images/{c64_type}_pressed{layout_sufix}.png"
            if not os.path.exists(pressed_keys):
                continue
            img = cv2.imread(pressed_keys)

            squares = find_squares(img)

            square_details = []
            saved_files = 0
            for i, square in enumerate(squares):
                x, y, w, h = get_square_position(square)
                point = find_point_in_rectangle(
                    Rectangle(x, y, w, h), key_positions.keys()
                )

                text = key_positions.get(point)
                matrix_pos = (
                    key_matrix[text]
                    if text in key_matrix
                    else special_keys[text] | 0x40
                )

                key_text = ""
                for s in text:
                    if s.isalnum() or s == "_":
                        key_text += s
                    else:
                        key_text += unicodedata.name(s).replace(" ", "_")
                key_text = key_text.lower()
                filename, saved = save_square(img, x, y, w, h, c64_type, key_text, layout,layout_sufix)
                if saved:
                    saved_files += 1
                # text = preprocess_image_for_ocr(filename)
                square_details.append(
                    {
                        "filename": filename,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        # "point": {"x": point.x, "y": point.y},
                        "text": text,
                        "matrix_pos": matrix_pos,
                    }
                )

            if layout == "sv":
                lang = "Swedish"
            else:
                lang = "English"

            layout_w={
                "type": c64_type,
                "lang": layout,
                "name" : lang,
                "keys": square_details,
            }
            json.dump(
                layout_w,
                open(f"config/keyboard_layout/{c64_type}{layout_sufix}.json", "w"),
                indent=4,
            )
            print(f"Saved {saved_files} keys for {c64_type} {layout}")
