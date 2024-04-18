#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk

from PIL import ImageTk, Image

import connection
import time
import argparse
import serial
import serial.tools.list_ports
import re
import json

import sys
import termios
import os


LINE_PREFIX = "CommadLine:"
LOAD_8 = LINE_PREFIX + "load" + ("{CURSOR_RIGHT}") * 19 + ",8:{RETURN}"
LOAD_DIR = LINE_PREFIX + 'load"$",8:{RETURN}'
LOAD_ACEONE = LINE_PREFIX + 'load"http://c64.aceone.se",8:{RETURN}'
LOAD_MEATLOAF = LINE_PREFIX + 'load"ml:*",8:{RETURN}'

HEX_PREFIX = "0x"

serialDevice = None


def get_matrix_value(c):
    return key_matrix.get(c, -1)


def get_special_value(c):
    return special_keys.get(c, -1) | 0x40 if c in special_keys else -1


def get_special_release_value(c):
    return special_release_keys.get(c, "")


def combination_to_matrix(c, pressed):
    values = bytearray()
    for l in c.split("|"):
        if l.endswith("_OFF") and pressed:
            matrix_val = False
            l = l[:-4]
        else:
            matrix_val = pressed

        value = get_matrix_value(l)
        if value < 0:
            value = get_special_value(l)
        #        print(f"cmd: {l}, pressed: {matrix_val}")
        if value >= 0 and value not in values:
            values.append(value | 0x80 if matrix_val else value)

    return values


def build_key_combination(c, pressed=True):
    key_combo = ""
    if get_matrix_value(c) >= 0:
        key_combo = ("SHIFT_LEFT_OFF|" if c in no_shift else "") + c
    elif len(c) == 1 and re.match("[A-ZÅÄÖ]", c):
        key_combo = "SHIFT_LEFT|" + c.lower()
    elif c in key_mappings:
        key_combo = key_mappings[c]

    if key_combo == "LOAD_DIR":
        key_combo = LOAD_DIR

    if not pressed:
        value = get_special_release_value(c)
        if value:
            key_combo = key_combo + "|" + value

    return key_combo


def parse_key_combinations(key_combo, pressed=True):
    values = combination_to_matrix(key_combo, pressed)

    if values:
        print(f"key combination: {key_combo}")
        for val in values:
            img = key_imgages.get(val & 0x7F, None)
            if img:
                s = "normal" if val & 0x80 else "hidden"
                canvas.itemconfig(img["id"], state=s)
            if val & 0xC3 == 0xC3:
                for img in key_imgages.values():
                    canvas.itemconfig(img["id"], state="hidden")
        hex_string = " ".join(f"{HEX_PREFIX}{element:02X}" for element in values)
        print(f"values: {hex_string}")
        if connection and connection.is_connected():
            written = connection.write(bytearray([len(values)]))
            written = connection.write(values)
            connection.flush()
        print("------------ Sent-----------------------")
    else:
        print(f"Unknown key combination: {key_combo}")
        print("----------------------------------------")


def process_key(c, pressed=True):
    hex_string = ""
    if re.match("[\\w!@#$%^&*()-_=+\\\\|,<.>/?`~\\[\\]{}\"\\']", c):
        print(f"'{c}' in hex = 0x")
    else:
        for element in c:
            hex_string += f"0x{ord(element):02X} "
    print(f"other key: {hex_string}")

    key_combo = build_key_combination(c, pressed)
    if key_combo.startswith(LINE_PREFIX):
        if not pressed:
            return
        parse_key_combinations("TEXT", True)
        for m in re.finditer(r"(\{(\w+)\})|.", key_combo[len(LINE_PREFIX) :]):
            # print (m.group().strip("{}"))
            key_combo = build_key_combination(m.group().strip("{}"))
            parse_key_combinations(key_combo)
            time.sleep(0.05)
        parse_key_combinations("TEXT", False)
    else:
        parse_key_combinations(key_combo, pressed)


def decode_key(event):
    if event.keysym_num >= 33 and event.keysym_num <= 126:
        key = chr(event.keysym_num)
    elif event.keysym == "??":
        key = event.char
    else:
        key = event.keysym
    return key


def on_key_event(event, pressed):
    key = decode_key(event)
    print(f"Key {'pressed' if pressed else 'released'}: {key}")
    process_key(key, pressed)


def read_input():
    if connection:
        if connection.is_connected():
            while True:
                line = connection.readline()
                if len(line.strip()) > 0:
                    data = line.decode("utf-8").strip()
                    print(f" --> {data}")
                else:
                    break
        else:
            print("Connection lost")
            connection.connect()
    window.after(200, read_input)


def handle_focus(event):
    if event.widget == window:
        parse_key_combinations("RESET_MATRIX")


def parse_args():
    parser = argparse.ArgumentParser(
        description="c64keyboard, a C64 keyboard emulator."
    )
    specifyDevices = parser.add_mutually_exclusive_group(required=True)
    specifyDevices.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available USB devices and exit. Use this option to find a device for the -d / --device option.",
    )
    specifyDevices.add_argument(
        "-d",
        "--device",
        action="store",
        type=str,
        dest="usbDevice",
        help="Specify an Arduino-like USB device to use.",
    )
    specifyDevices.add_argument(
        "-D",
        "--dummy",
        action="store_true",
        help="Dummy mode. Don't connect to a device, print all serial output to STDOUT instead.",
    )
    return parser.parse_args()


def load_config():
    global key_matrix, layout, no_shift, special_release_keys, special_keys, key_mappings, c64_type, lang
    c64_type = "breadbin"
    # c64_type = "c64c"
    # lang = "_sv"
    lang = ""

    key_layout = json.load(open(f"config/keyboard_matrix{lang}.json"))
    layout = key_layout["layout"]
    print(f"Loading layout {c64_type} {layout}")
    key_matrix = key_layout["matrix"]
    no_shift = key_layout["no-shift"]

    special_release_keys = {}
    if "special-release-keys" in key_layout:
        special_release_keys = key_layout["special-release-keys"]

    key_config = json.load(open(f"config/key_config.json"))
    special_keys = key_config["special-keys"]
    key_mappings = key_config["key-mappings"]
    key_mappings.update(key_layout["key-mappings"])


def donothing():
    x = 0


if __name__ == "__main__":
    args = parse_args()
    if args.list:
        print(
            "\n".join(
                f"Device: {p.device} ; Description: {p.description}"
                for p in serial.tools.list_ports.comports()
            )
        )
        sys.exit()

    serialDevice = args.usbDevice

    if not args.dummy:
        try:
            print(f"Connecting to device: {serialDevice}")
            # arduino = serial.Serial(serialDevice, BAUD, timeout=0.1, write_timeout=0.1)
            # arduino = serial.Serial(serialDevice, BAUD)
            connection = connection.SerialConnection(serialDevice)
            connection.connect()
        except:
            print("Cannot open serial device, exiting.")
            sys.exit()
        # Give serial interface time to settle down
        time.sleep(1)

    load_config()

    # Create the GUI window
    window = tk.Tk()
    window.resizable(False, False)
    window.title(f"C64 Keyboard, {layout} layout")
    window.geometry("1006x290")
    window.bind("<KeyPress>", lambda e: on_key_event(e, True))
    window.bind("<KeyRelease>", lambda e: on_key_event(e, False))
    window.bind("<FocusIn>", handle_focus)

    menubar = tk.Menu(window)
    filemenu = tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Open", command=donothing)
    filemenu.add_command(label="Configure", command=donothing)
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=window.quit)
    menubar.add_cascade(label="File", menu=filemenu)

    helpmenu = tk.Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Paste", command=donothing)
    menubar.add_cascade(label="Edit", menu=helpmenu)

    window.config(menu=menubar)

    canvas = tk.Canvas(window, height=290, width=1006)
    bgImg = ImageTk.PhotoImage(Image.open(f"images/{c64_type}_keyboard{lang}.png"))
    kb = canvas.create_image(0, 0, anchor=tk.NW, image=bgImg)
    canvas.pack()

    keyboard_layout = json.load(open(f"config/keyboard_layout/{c64_type}{lang}.json"))

    # # canvas = tk.Canvas(window, height=250, width=300)
    key_imgages = {}
    for key in keyboard_layout:
        img = ImageTk.PhotoImage(Image.open(key["filename"]))
        id = canvas.create_image(
            key["x"], key["y"], anchor=tk.NW, image=img, state="hidden"
        )
        key_imgages[key["matrix_pos"]] = {"img": img, "id": id}

    window.update()

    window.after(20, read_input)
    # Run the GUI event loop
    window.mainloop()
    print("Exiting...")
    sys.exit()


# def save_square(img, x, y, w, h, c64_type, key_text, layout):
#     filename = f"images/keys/{c64_type}_key_{key_text}{layout}.jpg"
#     square_img = img[y : y + h, x : x + w]
#     # if os.path.exists(filename = f"images/keys/{c64_type}_key_{key_text}.jpg"):
#     #     excisting = cv2.imread(filename)
#     #     # compute difference
#     #     difference = cv2.subtract(square_img, excisting)
#     #     print(f"Diff: {np.sum(difference)}")

#     cv2.imwrite(filename, square_img)
#     return filename
