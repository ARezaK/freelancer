import logging
import re
import os
import subprocess
from PIL import ImageGrab, Image
from pprint import pprint
from Levenshtein import ratio as lratio
from difflib import SequenceMatcher

logging.basicConfig(filename='logs/ocr.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def ocr(image):
    """
    used for connecting to tesseract. Input is filename. Runs tesseract on input and outputs text into tesseract_output.txt
    """
    logging.info("OCRING IMAGE: %s" %(image))
    process = subprocess.Popen(['tesseract.exe', image, 'temp_files/tesseract_output'])
    process.communicate()

def get_regions_to_process():
    """
    Read the regions file and returns the name and coordinates of the regions regions.
    """
    regions = [] # list of tuples. First item in tuple is name of region, second is coordinates(y,x,width,height)
    with open('regions/regions.txt') as f:
        for line in f.readlines():
            if 'MRZ' not in line:
                continue
            split = line.split('>>>')
            regions.append((split[2].strip(),[(v) for k, v in eval(split[1]).iteritems()] ))
    return regions

def read_tesseract_output():
    b = open('temp_files/tesseract_output.txt', 'r')
    output = b.read()
    b.close()
    return output

def determine_if_this_is_the_picture_to_process(filename, regions):
    """
    Go through this file and the regions to determine if this file has the region with the *
    """
    logging.info("Determining If this is the file to process: %s" % file_)
    with open('processed_images/' + file_, 'rb') as f:
        im = Image.open(f)
        for region in regions:
            if '*' not in region[0]:  # want to make sure that we ocr the correct page first so we look for the region that defines that page
                continue
            saveable_region_name = region[0][1:].replace(" ", "_")  # get a saveable region name
            im = im.crop((region[1][1], region[1][0], region[1][1] + region[1][2], region[1][0] + region[1][3]))
            im.save('temp_files/' + saveable_region_name + '.jpg')
            ocr('temp_files/' + saveable_region_name + '.jpg')

            region_name = str(region[0].replace("*", ""))
            tess_output = str(read_tesseract_output())
            ratio = lratio(region_name, tess_output)  # get the levenshtein ratio between the two text
            print(ratio)
            if float(ratio) > .95:
                print("most likely a match")
                return True

def parse_regions_for_this_file(filename, regions):
    """
    Find all the ocrable regions for this file and input them into a csv file
    """
    logging.info("OCRING FILE: %s" % file_)
    with open('processed_images/' + file_, 'rb') as f:
        im = Image.open(f)
        for region in regions:
            saveable_region_name = region[0].replace(" ", "_")  # get a saveable region name
            im = im.crop((region[1][1], region[1][0], region[1][1] + region[1][2], region[1][0] + region[1][3]))
            im.save('temp_files/' + saveable_region_name + '.jpg')
            ocr('temp_files/' + saveable_region_name + '.jpg')

            tess_output = str(read_tesseract_output())
            print tess_output



files_to_process = os.listdir('processed_images')
logging.info(files_to_process)

regions = get_regions_to_process()
for file_ in files_to_process:
    if determine_if_this_is_the_picture_to_process(file_, regions):
        parse_regions_for_this_file(file_, regions)
    else:
        continue



