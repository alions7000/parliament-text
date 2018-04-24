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
        # DOWNLOAD ALL FILES FROM PARLIAMENT WEBSITE
        downloader = Downloader()
        all_committees = downloader.get_committees_urls()
        logger.info("Starting to process %i committees" % len(all_committees))

        for idx, committee_url in enumerate([c for c in all_committees]): #  if 'foreign-affairs-committee' in c]):
            downloader.process_committee(committee_url)
            logger.info('Completed committee %i / %i' % (idx, len(all_committees)))
        pass
    elif True:
        # PARSE ALL HTML FILES IN DATA DIRECTORY, CREATE JSON FILES
        all_filenames = glob.glob(os.path.expanduser('~/projects_data/parliament-text/*.html'))
        # df_key_data = pd.DataFrame(data={'plain_text': '',
        #                                  'members_text': '', 'members': '',
        #                                  'witnesses_text': '', 'witnesses': '',
        #                                  'Q&A': ''}, index=[])
        df_key_data = pd.DataFrame(columns=['members','witnesses','speakers_dict','Q&A','plain_text'], index=[])
        for i, filename in enumerate(all_filenames[0:]):
            with open(filename, 'r') as f:
                html_text = f.read()
            logger.info('%i / %i: %s' % (i, len(all_filenames), filename))
            current_transcript = transcript(html_text, {'status': 'read html from directory',
                                                        'html_file_location': f.name}, filename=filename)
            current_transcript.process_raw_html()
            members_text_for_xlsx = current_transcript.transcript_data.get('members_text', 'na') + \
                '\n' + '='*40 + '\n' + \
                                    re.sub('}, "', '}, \n"', json.dumps(
                                        current_transcript.transcript_data.get(
                                            'members', 'na')))
            witnesses_text_for_xlsx = current_transcript.transcript_data.get('witnesses_text', 'na') + \
                '\n' + '='*40 + '\n' + \
                                    re.sub('}, "', '}, \n"', json.dumps(
                                        current_transcript.transcript_data.get(
                                            'witnesses', 'na')))
            qna_text_for_xlsx = [short_section(s) for s in current_transcript.transcript_data.get('all_sections', 'na')]
            hyperlink_for_xlsx = r'=HYPERLINK("file:' + filename + '")'


            df_key_data.loc[hyperlink_for_xlsx] = {'plain_text': current_transcript.plain_text[0:5000],
                                         'members': members_text_for_xlsx[0:5000],
                                         'witnesses': witnesses_text_for_xlsx[0:5000],
                                         # 'members_text': current_transcript.transcript_data.get('members_text', 'na'),
                                         # 'members': json.dumps(current_transcript.transcript_data.get('members', 'na'), indent=4),
                                         # 'members': re.sub('}, "', '}, \n"', json.dumps(current_transcript.transcript_data.get('members', 'na'))),
                                         # 'witnesses_text': current_transcript.transcript_data.get('witnesses_text', 'na'),
                                         # 'witnesses': json.dumps(current_transcript.transcript_data.get('witnesses', 'na'), indent=4),
                                         # 'witnesses': re.sub('}, "', '}, \n"',json.dumps(current_transcript.transcript_data.get('witnesses','na'))),
                                         # 'Q&A': re.sub(r'}, {', '}, \n{', json.dumps(current_transcript.transcript_data.get('all_sections', 'na')))[0:5000]
                                         'Q&A': re.sub(r'}, {', '}, \n{',json.dumps(qna_text_for_xlsx))[0:5000],
                                         'speakers_dict': re.sub(r'}, "', '}, \n"',json.dumps(current_transcript.speakers_dict))[0:5000]
                                         }

            # analyse_transcript(current_transcript)
        writer = pd.ExcelWriter('summary.xlsx', engine='xlsxwriter')
        pandas.io.formats.excel.header_style = None
        df_key_data.to_excel(writer, sheet_name='debug', index_label='html_file_hyperlink')
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
        for ii in range(1, i+2):
            debug_sheet.set_row(ii, 300)
        # fix for LibreOffice calc not showing hyperlinks properly: https://stackoverflow.com/questions/32205927/xlsxwriter-and-libreoffice-not-showing-formulas-result
        writer.save()
        logger.info('Finished summary output to XLSX: %s' % writer.path)

        # df_key_data.to_csv(os.path.expanduser('~/projects_data/parliament-text/summary.csv'),
        #                    index_label='filename')


    else:
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

            current_transcript = transcript(html_text, {'status': 'debugging case'}, filename=d)
            current_transcript.process_raw_html()


def short_section(section_data):
    # Q&A section data, shortened for use in xlsx output
    # (also removes the detailed speaker dict data)
    ss = section_data.copy()
    if 'speaker' in ss:
        ss['speaker_matched'] = ss['speaker']['person']['name']
        del ss['speaker']
    if 'unparsed_text' in ss:
        ss['unparsed_text'] = ss['unparsed_text'][0:500]
    else:
        ss['spoken_text'] = ss['spoken_text'][0:500]
    return ss

if __name__ == '__main__':
    main()








