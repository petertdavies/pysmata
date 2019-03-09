import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysmata",
    version="0.0.1",
    author="Peter Davies",
    author_email="ultratwo@gmail.com",
    description="Library and Program for manipulating Prismata replays/games",
    packages=setuptools.find_packages(),
    install_requires = [
      'numpy',
      'datadiff',
      'requests',
    ],
    entry_points={
        'console_scripts': [
            'pysmata=pysmata.__main__:main',
        ]
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
