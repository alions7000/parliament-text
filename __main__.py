#!/usr/bin/env python3
"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

Open Parliament Licence:
    Contains Parliamentary information licensed under the Open Parliament Licence v3.0
    License information:
        https://www.parliament.uk/site-information/copyright-parliament/open-parliament-licence/


"""

import re
import os
import glob
import pandas as pd
import pandas.formats
import pandas.io.formats.excel
import json

from src.capture_text import Downloader
from src.utils import logger, args

from src.parse_text import transcript




def main():

    if False:
        # Download all files
        downloader = Downloader()
        all_committees = downloader.committees_urls_list()
        logger.info("Starting to process %i committees" % len(all_committees))

        for idx, committee_url in enumerate([c for c in all_committees]): #  if 'foreign-affairs-committee' in c]):
            downloader.capture_committee_documents(committee_url)
            logger.info('Completed committee %i / %i' % (idx, len(all_committees)))
        pass
    elif True:
        # Parse all HTML files, store to JSON, and summarise in XLSX
        html_filenames = glob.glob(os.path.expanduser(
            '~/projects_data/parliament-text/*.html'))
        df = pd.DataFrame(columns=['members','witnesses',
                                            'speakers_dict','Q&A','plain_text'],
                                   index=[])
        for i, html_filename in enumerate(html_filenames[0:100]):
            with open(html_filename, 'r') as f:
                html_text = f.read()
            logger.info('%i / %i: %s' % (i, len(html_filenames), html_filename))
            trscrpt = transcript(html_text,
                                 {'status': 'read html from directory',
                                  'html_file_location': f.name},
                                 html_filename=html_filename)
            trscrpt.process_raw_html()
            key_data, hyperlink = trscrpt.key_data_summary()
            df.loc[hyperlink] = key_data

        xlsx_filename = 'summary.xlsx'
        key_data_to_xlsx(df, xlsx_filename)

    else:
        # Parse selected files
        key_html_documents = [
            '9422.html',
            '38389.html',
            '3245.html',
            '8332.html'
            # 'http://data.parliament.uk/writtenevidence/committeeevidence.svc/evidencedocument/treasury-committee/monetary-policy-forward-guidance/oral/3245.html'
        ]
        for d in key_html_documents:
            with open(os.path.join(os.path.expanduser('~/projects_data/parliament-text'), d),
                      'r') as f:
                html_text = f.read()

            trscrpt = transcript(html_text, {'status': 'debugging case'}, html_filename=d)
            trscrpt.process_raw_html()



def key_data_to_xlsx(df, xlsx_filename):
    # Save dataframe to xlsx, with formatting for readability

    n_rows = df.shape[0]
    writer = pd.ExcelWriter(xlsx_filename, engine='xlsxwriter')
    pandas.io.formats.excel.header_style = None
    df.to_excel(writer, sheet_name='debug', index_label='html_file_hyperlink')
    wrap_format = writer.book.add_format({'text_wrap': True, 'align': 'left', 'valign': 'top'})
    headers_format = writer.book.add_format({'text_wrap': True, 'bold': True})
    hyperlink_format = writer.book.add_format({
        'text_wrap': True, 'align': 'left', 'valign': 'top',
        'font_color': 'Blue', 'underline': True})
    debug_sheet = writer.sheets['debug']
    debug_sheet.freeze_panes(1,1)
    debug_sheet.set_column('A:A', 20, hyperlink_format)
    debug_sheet.set_column('B:F', 60, wrap_format)
    debug_sheet.set_row(0, [], headers_format)
    for ii in range(1, n_rows+2):
        debug_sheet.set_row(ii, 300)
    # fix for LibreOffice calc not showing hyperlinks properly: https://stackoverflow.com/questions/32205927/xlsxwriter-and-libreoffice-not-showing-formulas-result
    writer.save()
    logger.info('Finished summary output to XLSX: %s' % writer.path)




if __name__ == '__main__':
    main()








