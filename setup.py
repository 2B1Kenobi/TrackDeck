from setuptools import setup, find_packages

setup(
    name="trackdeck",
    version="0.1.0",
    description="Multitrack Session Ingestion & Lossless Stem Bus Middleware for StemDeck",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "numpy",
        "soundfile",
        "scipy",
    ],
    entry_points={
        "console_scripts": [
            "trackdeck=track_deck.cli:main",
        ],
    },
)
