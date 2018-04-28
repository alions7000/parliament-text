
import logging
import time
import datetime
import argparse
import html2text

from os import path



import sys
from time import sleep


project_dir = path.dirname(path.dirname(__file__))
parser = argparse.ArgumentParser()
parser.add_argument('--storage')
args = parser.parse_args()


batch_number = 999


"""Set up logging
"""
# log_file_name = 'sec_extractor_{0}.log'.format(ts)
log_file_name = 'parliament-text_%s.log' % format(batch_number, '04d')
log_path = path.join(args.storage, log_file_name)

logger = logging.getLogger('text_analysis')
# # set up the logger if it hasn't already been set up earlier in the execution run
logger.setLevel(logging.DEBUG)  # we have to initialise this top-level setting otherwise everything defaults to logging.WARN level
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                              '%Y%m%d %H:%M:%S')

file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
file_handler.set_name('my_file_handler')
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)
console_handler.set_name('my_console_handler')
logger.addHandler(console_handler)


ts = time.time()
logger.info('=' * 65)
logger.info('Analysis started at {0}'.
            format(datetime.datetime.fromtimestamp(ts).
                   strftime('%Y%m%d %H:%M:%S')))
logger.info('Command line:\t{0}'.format(sys.argv[0]))
logger.info('Arguments:\t\t{0}'.format(' '.join(sys.argv[:])))
logger.info('=' * 65)


def html_to_txt(raw_html):
    h = html2text.HTML2Text()  # consider using API field 'bodyText' instead?
    h.body_width = 0
    h.google_doc = True
    h.ignore_emphasis = False
    h.ignore_images = True
    # h.ignore_links = True
    # h.ignore_emphasis = True
    plain_text = h.handle(raw_html)
    return plain_text
