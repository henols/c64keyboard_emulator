import json
import logging
import os
import re
import time


class C64KeyboardLogic:
    HEX_PREFIX = "0x"
    LINE_PREFIX = "CommadLine:"
    LOAD_8 = LINE_PREFIX + "load" + ("{CURSOR_RIGHT}") * 19 + ",8:{RETURN}"
    LOAD_DIR = LINE_PREFIX + 'load"$",8:{RETURN}'

    CONFIG_PATH = "config/"
    KEY_CONFIG_PATH = "{config_path}/key_config.json"
    KEYBOARD_LAYOUT_PATH = "{config_path}/keyboard_layout"
    KEYBOARD_LAYOUT_FILE_PATH = KEYBOARD_LAYOUT_PATH + "/{c64_type}{lang}.json"
    KEYBOARD_MATRIX_PATH = "{config_path}/keyboard_matrix{lang}.json"
    IMAGE_PATH = "images/{c64_type}_keyboard{lang}.png"

    def __init__(self):
        self.log = logging.getLogger("c64keyboard")
        self.key_matrix = {}
        self.no_shift = []
        self.special_release_keys = {}
        self.special_keys = {}
        self.key_mappings = {}
        self.c64_type = "breadbin"
        self.lang = ""
        self.key_layout = {}

    def create_path(self, path):
        return path.format(
            config_path=self.CONFIG_PATH,
            c64_type=self.c64_type,
            lang=f"_{self.lang}" if self.lang and not self.lang == "en" else "",
        )

    def get_key_layouts(self):
        layout_info = []
        config_dir = self.create_path(self.KEYBOARD_LAYOUT_PATH)
        for filename in os.listdir(config_dir):
            if filename.endswith(".json"):
                keyboard_layout = json.load(open(f"{config_dir}/{filename}"))
                layout_info.append(
                    (keyboard_layout["type"], keyboard_layout["lang"], keyboard_layout["name"])
                )
        return layout_info

    def get_key_layout(self):
        keyboard_layout_path = self.create_path(self.KEYBOARD_LAYOUT_FILE_PATH)
        self.log.debug(f"Loading keyboard layout {keyboard_layout_path}")
        keyboard_layout = json.load(open(keyboard_layout_path))
        return keyboard_layout["keys"]

    def load_config(self, type="breadbin", lang=""):
        self.c64_type = type
        self.lang = lang

        config_path = self.create_path(self.KEYBOARD_MATRIX_PATH)
        self.log.debug(f"Loading matrix {config_path}")
        self.key_layout = json.load(open(config_path))
        self.layout = self.key_layout["layout"]
        self.log.debug(f"Loading layout {self.c64_type} {self.layout}")
        self.key_matrix = self.key_layout["matrix"]
        self.no_shift = self.key_layout["no-shift"]

        self.special_release_keys = {}
        if "special-release-keys" in self.key_layout:
            self.special_release_keys = self.key_layout["special-release-keys"]

        key_config_path = self.create_path(self.KEY_CONFIG_PATH)
        self.log.debug(f"Loading key config {key_config_path}")
        key_config = json.load(open(key_config_path))

        self.special_keys = key_config["special-keys"]
        self.key_mappings = key_config["key-mappings"]
        self.key_mappings.update(self.key_layout["key-mappings"])

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
            hex_string = " ".join(
                f"{self.HEX_PREFIX}{element:02X}" for element in values
            )
            self.log.debug(f"values: {hex_string}")
            return values
        else:
            self.log.debug(f"Unknown key combination: {key_combo}")
            self.log.debug("----------------------------------------")
            return None

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
            for m in re.finditer(r"(\{(\w+)\})|.", key_combo[len(self.LINE_PREFIX) :]):
                key_combo = self.build_key_combination(m.group().strip("{}"))
                self.parse_key_combinations(key_combo)
                time.sleep(0.05)
            self.parse_key_combinations("TEXT", False)
        else:
            return self.parse_key_combinations(key_combo, pressed)
