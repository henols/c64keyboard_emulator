from setuptools import setup, find_packages

setup(
    name="c64keyboard_emulator",
    version="1.0",
    description="Emulator for C64 keyboard",
    author="Henrik",
    packages=find_packages(),
    install_requires=[
        "tkinter",
        "time",
        "argparse",
        "pyserial",
        "re",
        "json",
        "numpy",
        # Add any other required packages here
    ],
    # package_data={b'multigtfs': ['test/fixtures/*.zip']},
    include_package_data=True,
    package_data={
        "": ["config/*.json", "images/*.*"],
    },
    entry_points={
        "console_scripts": ["c64keyboard_emulator = c64keyboard_emulator.main:main"]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    keywords="c64 keyboard emulator",
)
