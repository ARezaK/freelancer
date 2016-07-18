import logging
import re
import os
import csv
import subprocess
from PIL import ImageGrab, Image
from pprint import pprint
from Levenshtein import ratio as lratio
from difflib import SequenceMatcher
from sys import platform as _platform
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

logging.basicConfig(filename='logs/ocr.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

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


regions = get_regions_to_process() # [('address', [635, 150, 1040, 272]), ('notice_type', [660, 1215, 1126, 285]),.... ]


class Pdf():
    """
    create csv file when instaiting the pdf
    each tab is a page(image)
    each row is a region and then then extracted text for that region
    """

    def __init__(self, src_path, length=0):
        self.location = src_path
        self.pdf_file_name = src_path.split('/')[-1]
        
    def create_csv(self, regions):
        os.remove(   'extracted_text/%s.csv' % self.pdf_file_name)
        file_ = open('extracted_text/%s.csv' % self.pdf_file_name, 'w+')
        file_.close()

    def write_to_csv(self, things_to_write):
        """
        things to write is an array of data=[[1,2,4,5,'something','spam',2.334],
             [3,1,6,3,'anything','spam',0]] 
        """
        with open('extracted_text/%s.csv' % self.pdf_file_name, 'ab') as mycsvfile:
            thedatawriter = csv.writer(mycsvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL, lineterminator='\n')
            for row in things_to_write:
                thedatawriter.writerow(row)

    def convert_pdf_to_series_of_images(self):
        """
        Takes a pdf filename in pdf folder and extracts an image for each page in the pdf
        """
        print("converting pdf: %s to images " % self.pdf_file_name)
        process = subprocess.Popen('convert -verbose -density 300 -trim %s -quality 100 -depth 8 -sharpen 0x1.0 pdfs/images/%s.png' % (self.location, self.pdf_file_name) , shell=True)
        process.communicate()
        print("done extracting images from  pdf: %s" % self.pdf_file_name)

    def clean_up_images(self):
        images = os.listdir('pdfs/images')
        for image_nu, image_ in enumerate(images):
            print("cleaning up image: %s" % image_)
            if self.pdf_file_name in image_: # all extracted images have the pdf name in the image
                with open('pdfs/images/' + image_, 'rb') as f:
                    process = subprocess.Popen('textcleaner -g -e normalize -f 30 -o 12 -s 2 pdfs/images/%s pdfs/images/%s' % (image_, image_) , shell=True)
                    process.communicate()



    def find_pictures_to_process(self, regions):
        """
        Iterate through images for this pdf and find the image that has the region with *, then call parse_regions_for_this_file 
        """
        images = os.listdir('pdfs/images')
        for image_nu, image_ in enumerate(images):
            print("image_: ", image_)
            if self.pdf_file_name in image_: # all extracted images have the pdf name in the image
                with open('pdfs/images/' + image_, 'rb') as f:
                    im = Image.open(f)
                    for region in regions:
                        print("region: ", region)
                        if '*' not in region[0]:  # want to make sure that we ocr the correct page first so we look for the region that defines that page
                            continue
                        saveable_region_name = region[0][1:].replace(" ", "_")  # get a saveable region name
                        im = im.crop((region[1][1], region[1][0], region[1][1] + region[1][2], region[1][0] + region[1][3]))
                        im.save('temp_files/' + saveable_region_name + '.jpg')
                        ocr('temp_files/' + saveable_region_name + '.jpg')

                        region_name = str(region[0].replace("*", ""))
                        tess_output = str(read_tesseract_output())
                        ratio = lratio(region_name, tess_output)  # get the levenshtein ratio between the two text, b/c ocr is not perfect
                        print(region_name)
                        print(tess_output)
                        print(ratio)
                        x = raw_input()
                        if float(ratio) > .90:
                            logging.info("file has a match")
                            print("file has a match") 
                            self.parse_regions_for_this_file(image_, regions)
                        else:
                            logging.info("No match")

    def parse_regions_for_this_file(self, file_, regions):
        """
        Find all the ocrable regions for this file and get text
        """
        logging.info("OCRING FILE: %s" % file_)
        with open('pdfs/images/' + file_, 'rb') as f:
            for region in regions:
                im = Image.open(f)
                print("region: ", region)
                saveable_region_name = region[0].replace(" ", "_")  # get a saveable region name
                print(saveable_region_name)
                im = im.crop((region[1][1], region[1][0], region[1][1] + region[1][2], region[1][0] + region[1][3]))
                im.save('temp_files/' + saveable_region_name + '.jpg')
                ocr(    'temp_files/' + saveable_region_name + '.jpg')

                tess_output = str(read_tesseract_output())
                print(tess_output)

                # now put into database
                self.write_to_csv([[file_, region[0], tess_output]])

    def delete_extracted_images_for_this_pdf(self):
        """
        Iterate through images for this pdf and find the image that has the region with *, then call parse_regions_for_this_file 
        """
        images = os.listdir('pdfs/images')
        for image_num, image_ in enumerate(images):
            print("image_: ", image_)
            if self.pdf_file_name in image_: # since all extracted images have the pdf name in the image
                os.remove(image_)

    def move_this_pdf_to_processed(self):
        os.rename(image_, 'processed_pdfs')


def ocr(image):
    """
    used for connecting to tesseract. Input is filename. Runs tesseract on input and outputs text into tesseract_output.txt
    """
    logging.info("OCRING IMAGE: %s" %(image))
    if _platform == "darwin":
        process = subprocess.Popen(['tesseract', image, 'temp_files/tesseract_output'])
    else: # windows
        process = subprocess.Popen(['tesseract.exe', image, 'temp_files/tesseract_output'])
    process.communicate()

    


def read_tesseract_output():
    b = open('temp_files/tesseract_output.txt', 'r')
    output = b.read().strip()
    logging.info("Tesseract Output: %s" % output)
    b.close()
    return output





"""
files_to_process = os.listdir('processed_images')
logging.info("images to ocr through: %s" % files_to_process)

for file_ in files_to_process:
    if determine_if_this_is_the_picture_to_process(file_, regions):
        parse_regions_for_this_file(file_, regions)
        quit()
    else:
        continue
"""

class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        print("pdf has entereted directory: %s" % event.src_path)
        added_pdf = Pdf(event.src_path)
        added_pdf.create_csv(regions)
        added_pdf.convert_pdf_to_series_of_images()
        added_pdf.clean_up_images()
        added_pdf.find_pictures_to_process(regions)
        added_pdf.delete_extracted_images_for_this_pdf()
        added_pdf.move_this_pdf_to_processed()

        print("All done")

if __name__ == "__main__":
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path='pdfs', recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

