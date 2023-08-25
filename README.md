# pyNEUNET

## Version number
current version = '0.1.0'

## Installation
In the terminal, go to whatever directory you want the module to be available in and type

    pip install git+https://github.com/sfayfar/pyNEUNET-Detector.git

## Import
To import the entire module, write

    import pyNEUNET

at the top of your Python file. To import only the detectors.py file (for reading data), write

    from pyNEUNET import detectors

## Usage
Assuming you only imported the detectors.py file, create a new reader object by writing

    reader = detectors.Linear3HePSD()

Set exposure time (seconds) and number of position bins (350 bins ~ 1 mm resolution):

    reader.exposure_time = 30

    reader.bins = 350

Read data:

    reader.read()