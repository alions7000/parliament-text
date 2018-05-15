
import logging
import time
import datetime
import argparse
import html2text
import re
from os import path
import sys


project_dir = path.dirname(path.dirname(__file__))
parser = argparse.ArgumentParser()
parser.add_argument('--storage')
parser.add_argument('--download', action='store_true') # store_true -> default action is false
parser.add_argument('--parse', action='store_true')
parser.add_argument('--diagnostic', action='store_true')
parser.add_argument('--analyse', action='store_true')
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

    # plain_text_raw = plain_text
    # plain_text = plain_text_raw
    plain_text = re.sub('(\*\*\_?) ', r'\1',
                           plain_text)  # remove trailing space that typically gets added by html2text at the end of every emphasis pair (not perfect: sometimes it's valid space)
    # plain_text = re.sub('\_\*\*\_', '', plain_text)  # remove redundant empty italic emphasis tags e.g. 26885.html, Q130
    plain_text = re.sub('\*\*\_?(\s*)\_?\*\*', r'\1',
                           plain_text)  # remove redundant empty emphasis e.g. 49412, Q200; 45429.html, Q105 Professor Bell

    return plain_text
