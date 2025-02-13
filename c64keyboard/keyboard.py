#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from PIL import ImageTk, Image
from . import connection
import time
import argparse
import serial
import serial.tools.list_ports
import re
import json
import sys
import termios
import os
import logging

class C64KeyboardEmulator:
    LINE_PREFIX = "CommadLine:"
    LOAD_8 = LINE_PREFIX + "load" + ("{CURSOR_RIGHT}") * 19 + ",8:{RETURN}"
    LOAD_DIR = LINE_PREFIX + 'load"$",8:{RETURN}'
    HEX_PREFIX = "0x"

    def __init__(self):
        self.serialDevice = None
        self.conn = None
        self.log = logging.getLogger("c64keyboard")
        self.key_matrix = {}
        self.layout = ""
        self.no_shift = []
        self.special_release_keys = {}
        self.special_keys = {}
        self.key_mappings = {}
        self.c64_type = "breadbin"
        self.lang = ""
        self.window = None
        self.canvas = None
        self.key_imgages = {}

    def get_matrix_value(self, c):
        return self.key_matrix.get(c, -1)

    def get_special_value(self, c):
        return self.special_keys.get(c, -1) | 0x40 if c in self.special_keys else -1

    def get_special_release_value(self, c):
        return self.special_release_keys.get(c, "")

    def combination_to_matrix(self, c, pressed):
        values = bytearray()
        for l in c.split("|"):
            if l.endswith("_OFF") and pressed:
                matrix_val = False
                l = l[:-4]
            else:
                matrix_val = pressed

            value = self.get_matrix_value(l)
            if value < 0:
                value = self.get_special_value(l)
            if value >= 0 and value not in values:
                values.append(value | 0x80 if matrix_val else value)

        return values

    def build_key_combination(self, c, pressed=True):
        key_combo = ""
        if self.get_matrix_value(c) >= 0:
            key_combo = ("SHIFT_LEFT_OFF|" if c in self.no_shift else "") + c
        elif len(c) == 1 and re.match("[A-ZÅÄÖ]", c):
            key_combo = "SHIFT_LEFT|" + c.lower()
        elif c in self.key_mappings:
            key_combo = self.key_mappings[c]

        if key_combo == "LOAD_DIR":
            key_combo = self.LOAD_DIR
        elif key_combo == "LOAD_8":
            key_combo = self.LOAD_8

        if not pressed:
            value = self.get_special_release_value(c)
            if value:
                key_combo = key_combo + "|" + value

        return key_combo

    def parse_key_combinations(self, key_combo, pressed=True):
        values = self.combination_to_matrix(key_combo, pressed)

        if values:
            self.log.debug(f"key combination: {key_combo}")
            for val in values:
                img = self.key_imgages.get(val & 0x7F, None)
                if img:
                    s = "normal" if val & 0x80 else "hidden"
                    self.canvas.itemconfig(img["id"], state=s)
                if val & 0xC3 == 0xC3 or val & 0x44 == 0x44:
                    for img in self.key_imgages.values():
                        self.canvas.itemconfig(img["id"], state="hidden")
            hex_string = " ".join(f"{self.HEX_PREFIX}{element:02X}" for element in values)
            self.log.debug(f"values: {hex_string}")
            if self.conn and self.conn.is_connected():
                self.conn.write(bytearray([len(values)]))
                self.conn.write(values)
                self.conn.flush()
            self.log.debug("------------ Sent-----------------------")
        else:
            self.log.debug(f"Unknown key combination: {key_combo}")
            self.log.debug("----------------------------------------")

    def process_key(self, c, pressed=True):
        hex_string = ""
        if re.match("[\\w!@#$%^&*()-_=+\\\\|,<.>/?`~\\[\\]{}\"\\']", c):
            self.log.debug(f"'{c}' in hex = 0x")
        else:
            for element in c:
                hex_string += f"0x{ord(element):02X} "
        self.log.debug(f"other key: {hex_string}")

        key_combo = self.build_key_combination(c, pressed)
        if key_combo.startswith(self.LINE_PREFIX):
            if not pressed:
                return
            self.parse_key_combinations("TEXT", True)
            for m in re.finditer(r"(\{(\w+)\})|.", key_combo[len(self.LINE_PREFIX):]):
                key_combo = self.build_key_combination(m.group().strip("{}"))
                self.parse_key_combinations(key_combo)
                time.sleep(0.05)
            self.parse_key_combinations("TEXT", False)
        else:
            self.parse_key_combinations(key_combo, pressed)

    def decode_key(self, event):
        self.log.debug(f"event: {event}")
        if event.keysym_num >= 33 and event.keysym_num <= 126:
            key = chr(event.keysym_num)
        elif event.keysym == "??":
            key = event.char
        else:
            key = event.keysym
        if event.state & 4 == 4:
            key = "Ctrl_" + key
        return key

    def on_key_event(self, event, pressed):
        key = self.decode_key(event)
        self.log.debug(f"Key {'pressed' if pressed else 'released'}: {key}")
        self.process_key(key, pressed)

    def read_input(self):
        if self.conn:
            if self.conn.is_connected():
                while True:
                    line = self.conn.readline()
                    if len(line.strip()) > 0:
                        data = line.decode("utf-8").strip()
                        self.log.debug(f" --> {data}")
                    else:
                        break
            else:
                self.log.debug("Connection lost")
                self.conn.connect()
        self.window.after(200, self.read_input)

    def handle_focus(self, event):
        if event.widget == self.window:
            self.parse_key_combinations("RESET_MATRIX")

    def parse_args(self):
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
            help="Dummy mode. Don't connect to a device, log.debug all serial output to STDOUT instead.",
        )
        return parser.parse_args()

    def load_config(self):
        self.c64_type = "breadbin"
        self.lang = ""

        key_layout = json.load(open(f"config/keyboard_matrix{self.lang}.json"))
        self.layout = key_layout["layout"]
        self.log.debug(f"Loading layout {self.c64_type} {self.layout}")
        self.key_matrix = key_layout["matrix"]
        self.no_shift = key_layout["no-shift"]

        self.special_release_keys = {}
        if "special-release-keys" in key_layout:
            self.special_release_keys = key_layout["special-release-keys"]

        key_config = json.load(open(f"config/key_config.json"))
        self.special_keys = key_config["special-keys"]
        self.key_mappings = key_config["key-mappings"]
        self.key_mappings.update(key_layout["key-mappings"])

    def donothing(self):
        pass

    def create_debug_console_handler(self):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        return console_handler

    def run(self):
        self.log.addHandler(self.create_debug_console_handler())
        self.log.setLevel(logging.DEBUG)

        args = self.parse_args()
        if args.list:
            self.log.debug(
                "\n".join(
                    f"Device: {p.device} ; Description: {p.description}"
                    for p in serial.tools.list_ports.comports()
                )
            )
            sys.exit()

        self.serialDevice = args.usbDevice

        if not args.dummy:
            try:
                self.log.debug(f"Connecting to device: {self.serialDevice}")
                self.conn = connection.SerialConnection(self.serialDevice)
                self.conn.connect()
            except:
                self.log.debug("Cannot open serial device, exiting.")
                sys.exit()
            time.sleep(1)

        self.load_config()

        self.window = tk.Tk()
        self.window.resizable(False, False)
        self.window.title(f"C64 Keyboard, {self.layout} layout")
        self.window.geometry("1006x290")
        self.window.bind("<KeyPress>", lambda e: self.on_key_event(e, True))
        self.window.bind("<KeyRelease>", lambda e: self.on_key_event(e, False))
        self.window.bind("<FocusIn>", self.handle_focus)

        menubar = tk.Menu(self.window)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.donothing)
        filemenu.add_command(label="Configure", command=self.donothing)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.window.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Paste", command=self.donothing)
        menubar.add_cascade(label="Edit", menu=helpmenu)

        self.window.config(menu=menubar)

        self.canvas = tk.Canvas(self.window, height=290, width=1006)
        bgImg = ImageTk.PhotoImage(Image.open(f"images/{self.c64_type}_keyboard{self.lang}.png"))
        kb = self.canvas.create_image(0, 0, anchor=tk.NW, image=bgImg)
        self.canvas.pack()

        keyboard_layout = json.load(open(f"config/keyboard_layout/{self.c64_type}{self.lang}.json"))

        self.key_imgages = {}
        for key in keyboard_layout:
            img = ImageTk.PhotoImage(Image.open(key["filename"]))
            id = self.canvas.create_image(
                key["x"], key["y"], anchor=tk.NW, image=img, state="hidden"
            )
            self.key_imgages[key["matrix_pos"]] = {"img": img, "id": id}

        self.window.update()

        self.window.after(20, self.read_input)
        self.window.mainloop()
        self.log.debug("Exiting...")
        sys.exit()

if __name__ == "__main__":
    emulator = C64KeyboardEmulator()
    emulator.run()