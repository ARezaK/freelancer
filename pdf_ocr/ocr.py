import logging
import os
import csv
import subprocess
from PIL import Image
from Levenshtein import ratio as lratio
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
    Expects a regions text file where the distinguishing region is the one with a star
    """
    regions = []
    with open('regions/new_regions.txt') as f:
        for line in f.readlines():
            if 'MRZ' not in line:
                continue
            split = line.split('>>>')
            regions.append((split[2].strip(), [(v) for k, v in eval(split[1]).iteritems()] ))
    return regions  # list of tuples. First item in tuple is name of region, second is coordinates(y,x,width,height)


regions = get_regions_to_process()  # [('address', [635, 150, 1040, 272]), ('notice_type', [660, 1215, 1126, 285]),...]


class Pdf:

    def __init__(self, src_path):
        self.location = src_path
        self.pdf_file_name = src_path.split('/')[-1]
        
    def create_csv(self, regions):
        logging.info("Creating CSV for %s"   % self.pdf_file_name)
        os.remove(   'extracted_text/%s.csv' % self.pdf_file_name)  # remove old csv file of the same name
        file_ = open('extracted_text/%s.csv' % self.pdf_file_name, 'w+')  # create csv file
        file_.close()

    def write_to_csv(self, things_to_write):
        """
        things to write is an array of data=[[1,2,4,5,'something','spam',2.334],
             [3,1,6,3,'anything','spam',0]] 
        """
        with open('extracted_text/%s.csv' % self.pdf_file_name, 'ab') as mycsvfile:
            writer = csv.writer(mycsvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL, lineterminator='\n')
            for row in things_to_write:
                writer.writerow(row)

    def convert_pdf_to_series_of_images(self):
        """
        Extracts an image from each page of the pdf
        """
        logging.info("converting pdf: %s to images " % self.pdf_file_name)
        #process = subprocess.Popen('convert -verbose -density 400 -trim %s -quality 100 -depth 15 -sharpen 0x0.5 pdfs/images/%s.png' % (self.location, self.pdf_file_name) , shell=True)
        process = subprocess.Popen(
            'convert -verbose -density 300  %s  pdfs/images/%s.png' % (self.location, self.pdf_file_name), shell=True)
        process.communicate()
        logging.info("done extracting images from  pdf: %s" % self.pdf_file_name)

    """
    # if you have the textcleaner script installed you can use it to clean up the images
    def clean_up_images(self):
        images = os.listdir('pdfs/images')
        for image_num, image_ in enumerate(images):
            print("cleaning up image: %s" % image_)
            if self.pdf_file_name in image_: # all extracted images have the pdf name in the image
                with open('pdfs/images/' + image_, 'rb') as f:
                    process = subprocess.Popen('textcleaner -g -e normalize -f 30 -o 12 -s 2 pdfs/images/%s pdfs/images/%s' % (image_, image_) , shell=True)
                    process.communicate()
    """

    def find_pictures_to_process(self, regions):
        """
        Iterate through the extracted images for this pdf and find the image that has the region with *.
        Once you know the important region, then call parse_regions_for_this_file
        """
        logging.info("Finding pictures to process")
        images = os.listdir('pdfs/images')  # get all files in that directory
        for image_num, image_ in enumerate(images):
            logging.info("image_: %s" % image_)
            if self.pdf_file_name in image_:  # all extracted images have the pdf name in the image
                with open('pdfs/images/' + image_, 'rb') as f:
                    im = Image.open(f)
                    for region in regions:
                        # want to make sure that we ocr the correct page first so we look for the region that defines that page
                        if '*' not in region[0]:
                            continue

                        region_name = region[0]
                        region_coord = region[1]

                        saveable_region_name = region_name[1:].replace(" ", "_")  # get a saveable region name

                        # extract the part of the image that has the region
                        im = im.crop((region_coord[1], region_coord[0], region_coord[1] + region_coord[2], region_coord[0] + region_coord[3]))
                        im.save('temp_files/' + saveable_region_name + '.png')

                        ocr(    'temp_files/' + saveable_region_name + '.png')

                        region_name = str(region_name.replace("*", ""))
                        tess_output = str(read_tesseract_output())

                        # get the levenshtein ratio between the two text, b/c ocr is not perfect
                        ratio = lratio(region_name, tess_output)
                        logging.info("Region name: %s"       % region_name)
                        logging.info("Tesseract output: %s"  % tess_output)
                        logging.info("Levenshtein ratio: %s" % ratio)

                        raw_input("Parse regions for this file?")
                        if float(ratio) > .90:
                            logging.info("file has a match")

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
                region_name = region[0]
                region_coord = region[1]

                saveable_region_name = region_name.replace(" ", "_")  # get a saveable region name

                # extract the part of the image that has the region
                im = im.crop((region_coord[1], region_coord[0], region_coord[1] + region_coord[2], region_coord[0] + region_coord[3]))

                im.save('temp_files/' + saveable_region_name + '.png')
                ocr(    'temp_files/' + saveable_region_name + '.png')

                tess_output = str(read_tesseract_output())

                logging.info("tesseract output: %s" % tess_output)

                # now put into database
                self.write_to_csv([[file_, region[0], tess_output]])

    def delete_extracted_images_for_this_pdf(self):
        """
        After you've done everything delete the images for this pdf
        """
        images = os.listdir('pdfs/images')
        for image_num, image_ in enumerate(images):
            print("image_: ", image_)
            if self.pdf_file_name in image_:  # since all extracted images have the pdf name in the image
                os.remove('pdfs/images/' + image_)

    def move_this_pdf_to_processed(self):
        """
        Move the pdf to processed pdfs
        """
        os.rename(self.location, 'processed_pdfs/%s' % self.pdf_file_name)


def ocr(image):
    """
    used for connecting to tesseract. Input is filename. Runs tesseract on input and outputs text into tesseract_output.txt
    """
    logging.info("OCRING IMAGE: %s" % image)
    if _platform == "darwin":
        process = subprocess.Popen(['tesseract', image, 'temp_files/tesseract_output'])
    else:  # windows
        process = subprocess.Popen(['tesseract.exe', image, 'temp_files/tesseract_output'])
    process.communicate()


def read_tesseract_output():
    b = open('temp_files/tesseract_output.txt', 'r')
    output = b.read().strip()
    b.close()
    return output


class MyHandler(FileSystemEventHandler):
    """
    Watchdog handler
    """
    def on_created(self, event):
        logging.info("Pdf has entered directory: %s" % event.src_path)
        if '.pdf' not in event.src_path:
            print("not pdf")
            return

        added_pdf = Pdf(event.src_path)
        added_pdf.create_csv(regions)
        added_pdf.convert_pdf_to_series_of_images()
        #added_pdf.clean_up_images()
        added_pdf.find_pictures_to_process(regions)
        added_pdf.delete_extracted_images_for_this_pdf()
        added_pdf.move_this_pdf_to_processed()

        logging.info("All done")

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

