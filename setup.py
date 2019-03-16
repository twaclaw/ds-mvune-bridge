import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ds-mvune-bridge-twaclaw",
    version="0.0.1",
    author="Diego Sandoval",
    author_email="dsandovalv@gmail.com",
    description="ds-mvune package for RPi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/twaclaw/ds-mvune-bridge",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)