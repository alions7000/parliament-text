import requests
import re
import html2text
import json
import os
from .utils import args

class transcript(object):

    def __init__(self, transcript_text, urls_dict, filename):
        self.raw_html = transcript_text
        self.transcript_data = urls_dict
        self.filename = filename
        self.storage_path = args.storage


    def process_and_save(self):
        txt = self.html_to_txt()
        txt_filename = re.sub('.html', '.txt', self.filename)
        with open(os.path.join(self.storage_path, txt_filename), 'w',
                  encoding='utf-8') as txt_file:
            txt_file.write(txt)
        json_text = self.txt_to_json()
        json_filename = re.sub('.html', '.json', self.filename)
        with open(os.path.join(self.storage_path, json_filename), 'w',
                  encoding='utf-8') as json_file:
            json_file.write(json_text)

    def html_to_txt(self):
        h = html2text.HTML2Text()  # consider using API field 'bodyText' instead?
        h.body_width=0
        h.google_doc = True
        h.ignore_emphasis=False
        # h.ignore_links = True
        # h.ignore_emphasis = True
        self.plain_text = h.handle(self.raw_html)
        return self.plain_text


    def txt_to_json(self):
    # TODO:difficult cases: http://data.parliament.uk/writtenevidence/committeeevidence.svc/evidencedocument/treasury-committee/monetary-policy-forward-guidance/oral/3245.html

        # wherever **bold** text appears (possibly _**bolditalic**_, this is
        # deemed to be a 'new speaker'.
        t2 = re.search(r'(.*Witness.*?)(\*{,2}(Chair|Q).*)', self.plain_text, re.DOTALL)
        main_split = re.search(r'(.*Witness.*?)(\*{,2}Q.*)', self.plain_text, re.DOTALL)
        header_text = main_split.groups()[0]


        # any new line starting with **bold** text is labelled as representing a new speaker
        text_temp = re.sub(r'\n(\_?\*\*)', r'\nNEWSPEAKER\g<1>', main_split.groups()[1].strip())
        # break the text apart at the parts that we have identified as new speakers
        questions_sections = re.split('NEWSPEAKER', text_temp)

        all_p=[]
        for i, p in enumerate(questions_sections):
            # try to extract a speaker name from the start of the line
            parts = re.search(r'(\_?\*\*.*\*\*\_?)(.*)', p, re.DOTALL)
            if parts:
                firstpart = re.sub(r'[\_\*:]*', '', parts.groups()[0])
                qparts = re.search(r'(Q[\s.]?\d)(.*)', firstpart)
                if qparts:
                    all_p.append({'section_id': i,
                                  'question_number': qparts.groups()[0].strip(),
                                  'speaker': qparts.groups(0)[1].strip(),
                                  'spoken_text': parts.groups()[1].strip()})
                else:
                    all_p.append({'section_id': i, 'speaker': firstpart.strip(),
                                  'spoken_text': parts.groups()[1].strip()})

            else:
                # if no speaker name extracted, then just take the line as 'unparsed text'
                all_p.append({'section_id': i, 'unparsed_text': p.strip()})


        if header_text:
            # if any introduction text was captured then parse this separately
            metadata_from_header_lines(self.transcript_data, header_text)
            self.transcript_data['all_sections'] = all_p

        self.text_as_json = json.dumps(self.transcript_data, sort_keys=False, indent=4)

        return self.text_as_json


def metadata_from_header_lines(d, header_text):
    # always expect Members to be listed first, before witnesses and others
    header_text = re.sub(r'[\_\*]', '', header_text)
    try:
        # # rs = re.search('(.*)(Members Present.*)', header_text,
        # #                re.IGNORECASE + re.DOTALL)
        # rs = re.search('(.*)(Members Present.*)', header_text,
        #                re.IGNORECASE + re.DOTALL)
        # first_bit = rs.groups()[0]
        # people_lines = rs.groups()[1].split('\n', maxsplit=1)
        # members_text = people_lines[0]
        # d['meeting_header'] = first_bit
        # d['members_text'] = members_text
        # ws = re.search('Witness.*', people_lines[1])
        # if ws:
        #     witnesses_text = ws.group()
        #     others_text = re.sub(witnesses_text, '', people_lines[1])
        #     d['witnesses_text'] = witnesses_text,
        #     d['others_text'] = others_text
        #
        # other_text = header_text

        members_search = re.search(r'(members present.*?)(questions|examination)', header_text.strip(), re.IGNORECASE + re.DOTALL)
        members_text = members_search.groups()[0].strip()
        d['members_text'] = members_text
        other_text = re.sub(members_text, '', header_text)

        # witnesses_search = re.search(r'(\nWitness.*\n)((Examination|$))', header_text.strip(), re.DOTALL)
        witnesses_search = re.search(r'(\nWitness.*)',header_text.strip(), re.DOTALL)
        # witnesses_search = re.search(r'(\nWitness.*)', header_text.strip(), re.DOTALL)
        witnesses_text = witnesses_search.groups()[0].strip()
        d['witnesses_text'] = witnesses_text
        other_text = re.sub(witnesses_text, '', other_text)

        d['header_other_text'] = other_text

    except:
        pass
    d['full_header_text_unparsed'] = header_text
    return d
