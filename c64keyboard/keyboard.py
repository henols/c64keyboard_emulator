#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tkinter as tk
from PIL import ImageTk, Image
from . import connection
from .keyboard_logic import C64KeyboardLogic
import serial
import serial.tools.list_ports
import sys
import time
import logging


class C64KeyboardEmulator:
    WINDOW_TITLE_CONNECTED = "C64 Keyboard, {layout} layout - Connected {connected}"
    WINDOW_TITLE = "C64 Keyboard, {layout} layout - Disconnected"
    WINDOW_GEOMETRY = "1006x290"
    IMAGE_PATH = "images"
    KEYBOARD_IMAGE_PATH = IMAGE_PATH + "/{c64_type}_keyboard{lang}.png"
    KEY_IMAGE_PATH = IMAGE_PATH + "/keys/{key}"

    def __init__(self):
        self.logic = C64KeyboardLogic()
        self.serial_device = None
        self.connection = None
        self.log = logging.getLogger("c64keyboard")
        self.window = None
        self.canvas = None
        self.key_imgages = {}

    def decode_key(self, event):
        # self.log.debug(f"event: {event}")
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
        # self.log.debug(f"Key {'pressed' if pressed else 'released'}: {key}")
        self.send_key(key, pressed)

    def send_key(self, key, pressed):
        values = self.logic.translate_key(key, pressed)
        if values:
            self.connection.send_data(values)
            for val in values:
                img = self.key_imgages.get(val & 0x7F, None)
                if img:
                    s = "normal" if val & 0x80 else "hidden"
                    self.canvas.itemconfig(img["id"], state=s)
                if val & 0xC3 or val & 0x44:
                    for img in self.key_imgages.values():
                        self.canvas.itemconfig(img["id"], state="hidden")
                # time.sleep(0.5)

            self.log.debug("------------ Sent-----------------------")

    def read_input(self):
        if self.connection and self.connection.is_connected():
            while True:
                line = self.connection.readline()
                if line and len(line.strip()) > 0:
                    data = line.decode("utf-8").strip()
                    self.log.debug(f" --> {data}")
                else:
                    break

        self.window.after(200, self.read_input)

    def handle_focus(self, event):
        if event.widget == self.window:
            if self.connection and self.logic:
                data = self.logic.parse_key_combination("RESET_MATRIX")
                self.connection.send_data(data)

    def paste(self, event=None):
        text = self.window.clipboard_get()
        self.log.debug(f"Pasting: {text}")
        # self.log.info(f"----------------------------")
        n = 100
        for t in list(text[i : i + n] for i in range(0, len(text), n)):
            # self.log.info(f"sending part: '{t}'  {len(t)}")
            # self.log.info(f"----------------------------")
            data = self.logic.trasnslate_key_combination(f"{self.logic.LINE_PREFIX}{t}")
            self.connection.send_data(data)

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

    def on_hover(self, event):
        print(f"Hovering over: {event}")

    def initialize_gui(self):
        self.window = tk.Tk()
        self.window.resizable(False, False)
        self.update_window_title()
        self.window.geometry(self.WINDOW_GEOMETRY)
        self.window.bind("<KeyPress>", lambda e: self.on_key_event(e, True), add=True)
        self.window.bind(
            "<KeyRelease>", lambda e: self.on_key_event(e, False), add=True
        )
        self.window.bind("<FocusIn>", self.handle_focus)

        self.window.bind_class("SerialConnection", self.populate_serial_menu)

        menubar = tk.Menu(self.window)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.donothing)
        filemenu.add_command(label="Configure", command=self.donothing)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.window.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        menubar.add_cascade(label="Edit", menu=helpmenu)

        layoutmenu = tk.Menu(menubar, tearoff=0)
        self.populate_layout_menu(layoutmenu)
        menubar.add_cascade(label="Layout", menu=layoutmenu)

        connections_menu = tk.Menu(menubar, tearoff=0)
        serial_menu = tk.Menu(connections_menu, tearoff=0)

        connections_menu.add_cascade(label="Serial", menu=serial_menu)
        connections_menu.add_command(label="Network", command=self.donothing)
        menubar.add_cascade(label="Connections", menu=connections_menu)

        connections_menu.bind(
            "<Enter>", lambda e: self.populate_serial_menu(serial_menu, e), add=True
        )
        self.window.config(menu=menubar)

        self.canvas = tk.Canvas(self.window, height=290, width=1006)

        self.set_bg_image()
        self.canvas.pack()

        self.window.bind_all("<Control-v>", self.paste)

        self.load_keyboard_layout()

        self.window.update()

    def set_bg_image(self):
        bg_image_path = self.logic.create_path(self.KEYBOARD_IMAGE_PATH)
        self.log.debug(f"Loading background image {bg_image_path}")
        self.bgImg = ImageTk.PhotoImage(Image.open(bg_image_path))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bgImg)

    def populate_serial_menu(self, serial_menu, event):
        serial_menu.delete(0, tk.END)
        ports = serial.tools.list_ports.comports()
        for port in ports:
            serial_menu.add_command(
                label=port.device,
                command=lambda p=port.device: self.connect_serial(p),
            )
        if self.connection and self.connection.is_connected():
            for index, port in enumerate(ports):
                if port.device == self.connection.connection_path:
                    serial_menu.entryconfig(index, label=f"{port.device} ✔")

    def connect_serial(self, port):
        try:
            self.log.debug(f"Setting serial port {port}")
            self.connection.set_serial(port)
        except Exception as e:
            self.log.debug(f"Failed to connect to {port}. Error: {e}")

    def populate_layout_menu(self, layoutmenu):
        layouts = self.logic.get_key_layouts()
        for layout in layouts:
            layoutmenu.add_command(
                label=f"{layout[0][:1].upper()}{layout[0][1:]} ({layout[2]})",
                command=lambda c64_type=layout[0], lang=layout[1]: self.change_layout(
                    c64_type, lang
                ),
            )

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
        self.update_window_title()
        self.load_keyboard_layout()

    def update_window_title(self):
        if self.connection and self.connection.is_connected():
            self.window.title(
                self.WINDOW_TITLE_CONNECTED.format(
                    layout=self.logic.layout, connected=self.connection.connection_path
                )
            )
        else:
            self.window.title(self.WINDOW_TITLE.format(layout=self.logic.layout))

    def connection_callback(self, event):
        # print(f"Event: {event}")
        self.update_window_title()
        if self.connection and self.logic:
            if event["type"] == "connected":
                data = self.logic.parse_key_combination("RESET_MATRIX")
                self.connection.send_data(data)

    def run(self):
        self.log.addHandler(self.create_debug_console_handler())
        self.log.setLevel(logging.DEBUG)

        try:
            self.connection = connection.SerialConnection(callback=self.connection_callback)
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
