#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from PIL import ImageTk, Image
from . import connection
from .keyboard_logic import C64KeyboardLogic
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
    WINDOW_TITLE = "C64 Keyboard, {layout} layout"
    WINDOW_GEOMETRY = "1006x290"
    IMAGE_PATH = "images"
    KEYBOARD_IMAGE_PATH = IMAGE_PATH + "/{c64_type}_keyboard{lang}.png"
    KEY_IMAGE_PATH = IMAGE_PATH + "/keys/{key}"

    def __init__(self):
        self.logic = C64KeyboardLogic()
        self.serialDevice = None
        self.conn = None
        self.log = logging.getLogger("c64keyboard")
        self.window = None
        self.canvas = None
        self.key_imgages = {}

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
        values = self.logic.process_key(key, pressed)
        if values:
            for val in values:
                img = self.key_imgages.get(val & 0x7F, None)
                if img:
                    s = "normal" if val & 0x80 else "hidden"
                    self.canvas.itemconfig(img["id"], state=s)
                if val & 0xC3 == 0xC3 or val & 0x44 == 0x44:
                    for img in self.key_imgages.values():
                        self.canvas.itemconfig(img["id"], state="hidden")
            if self.conn and self.conn.is_connected():
                self.conn.write(bytearray([len(values)]))
                self.conn.write(values)
                self.conn.flush()
            self.log.debug("------------ Sent-----------------------")

    def read_input(self):
        if self.conn and self.conn.is_connected():
            while True:
                line = self.conn.readline()
                if line and len(line.strip()) > 0:
                    data = line.decode("utf-8").strip()
                    self.log.debug(f" --> {data}")
                else:
                    break

        self.window.after(200, self.read_input)

    def handle_focus(self, event):
        if event.widget == self.window:
            self.logic.parse_key_combinations("RESET_MATRIX")


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

    def initialize_gui(self):
        self.window = tk.Tk()
        self.window.resizable(False, False)
        self.window.title(self.WINDOW_TITLE.format(layout=self.logic.layout))
        self.window.geometry(self.WINDOW_GEOMETRY)
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

        layoutmenu = tk.Menu(menubar, tearoff=0)
        self.populate_layout_menu(layoutmenu)
        menubar.add_cascade(label="Layout", menu=layoutmenu)

        self.window.config(menu=menubar)

        self.canvas = tk.Canvas(self.window, height=290, width=1006)

        self.set_bg_image()
        self.canvas.pack()

        self.load_keyboard_layout()

        self.window.update()

    def set_bg_image(self):
        bg_image_path = self.logic.create_path(self.KEYBOARD_IMAGE_PATH)
        self.log.debug(f"Loading background image {bg_image_path}")
        self.bgImg = ImageTk.PhotoImage(Image.open(bg_image_path))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bgImg)

    def populate_layout_menu(self, layoutmenu):
        layouts = self.logic.get_key_layouts()
        for layout in layouts:
            layoutmenu.add_command(
                label=f"{layout[0]} ({layout[2]})",
                command=lambda c64_type=layout[0], lang=layout[1]: self.change_layout(
                    c64_type, lang
                ),
            )
        # config_dir = "config/keyboard_layout"
        # for filename in os.listdir(config_dir):
        #     if filename.endswith(".json"):
        #         parts = filename.replace(".json", "").split("_")
        #         if len(parts) == 2:
        #             c64_type, lang = parts
        #         else:
        #             c64_type = parts[0]
        #             lang = "en"
        #         layoutmenu.add_command(
        #             label=f"{c64_type} ({lang})",
        #             command=lambda c64_type=c64_type, lang=lang: self.change_layout(
        #                 c64_type, lang
        #             ),
        #         )

    def load_keyboard_layout(self):
        key_layout = self.logic.get_key_layout()
        self.key_imgages = {}
        for key in key_layout:
            key_path = self.KEY_IMAGE_PATH.format(key=key["filename"])
            img = ImageTk.PhotoImage(Image.open(key_path))
            id = self.canvas.create_image(
                key["x"], key["y"], anchor=tk.NW, image=img, state="hidden"
            )
            self.key_imgages[key["matrix_pos"]] = {"img": img, "id": id}

    def change_layout(self, c64_type, lang):
        self.logic.load_config(c64_type, lang)
        self.set_bg_image()
        self.window.title(self.WINDOW_TITLE.format(layout=self.logic.layout))
        self.load_keyboard_layout()

    def run(self):
        self.log.addHandler(self.create_debug_console_handler())
        self.log.setLevel(logging.DEBUG)

        try:
            self.log.debug(f"Connecting to device: {self.serialDevice}")
            self.conn = connection.SerialConnection(self.serialDevice)
            # self.conn.connect()
        except Exception as e:
            self.log.debug(f"Cannot open serial device, exiting. Error: {e}")
            sys.exit()
        # time.sleep(1)

        self.logic.load_config()
        self.initialize_gui()

        self.window.after(20, self.read_input)
        self.window.mainloop()
        self.log.debug("Exiting...")
        sys.exit()


if __name__ == "__main__":
    emulator = C64KeyboardEmulator()
    emulator.run()
