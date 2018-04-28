import re
import json
import os
from fuzzywuzzy import process
import spacy

from .utils import logger, args, html_to_txt


# https://spacy.io/usage/models
nlp = spacy.load('en_core_web_sm')
# nlp = spacy.load('en_core_web_md')
# nlp = spacy.load('en_core_web_lg')


class transcript(object):
    """Represent data in a parliamentary committee transcript"""

    def __init__(self, transcript_text, source_document_locations, filename):
        self.raw_html = transcript_text
        self.transcript_data = source_document_locations # initialise the main dict with just the internet location of the underlying document
        self.html_filename = filename
        self.storage_path = args.storage


    def process_raw_html(self, parse_to_json = True):
        """Convert HTML to plain text. Option to parse data to JSON file"""
        self.plain_text = html_to_txt(self.raw_html)
        txt_filename = re.sub('.html', '.txt', self.html_filename)
        with open(os.path.join(self.storage_path, txt_filename), 'w',
                  encoding='utf-8') as txt_file:
            txt_file.write(self.plain_text)
        if parse_to_json:
            self.parse_plain_text()
            json_filename = re.sub('.html', '.json', self.html_filename)
            with open(os.path.join(self.storage_path, json_filename), 'w',
                      encoding='utf-8') as json_file:
                json_file.write(self.json_text)


    def parse_plain_text(self):
        """Identify transcript data in the plain_text string

        Typical structure of the document:
                Title, date, video hyperlink, Members Present
                All Witnesses for all panels
                Examination of Witnesses (panel 1)
                    List of witnesses
                    Q&A
                Examination of Witnesses (panel 2)
                    List of witnesses
                    Q&A
                ...
                Examination of Witnesses (panel N)
                    List of witnesses
                    Q&A
        """

        # firstly, split the document into header material and the main question-answer section.

        all_questions_lines = ''
        # Identify the main Q&A section. Prefer the header 'Examination of Witness(es)'
        #   but sometimes we only have header 'Questions 111 - 222'. We don't prefer this
        #   pattern, however, as it sometimes occurs in the middle of the header section,
        #   prior to the header list of witnesses

        # first attempt to split: expect 'examination of witness(es)' at the top of the document.
        #TODO: this assumes that all panels will be preceded by another 'examination of witnesses' heading - this might not be the case.
        #TODO ...consider using same approach as Step 2, but delete any blocks with too few characters.
        panels_sections = re.split('(?:^\s*\**(?:examination of witness).*\n)+',
                                   self.plain_text, flags=re.IGNORECASE+re.MULTILINE)
        # second attempt to split: split whenever we have a 'questions' or 'examinations' header. works well, with flexibility,  with multiple panels
        if len(panels_sections)==1 or len(panels_sections[0]) > 3000:
            panels_sections = re.split('(?:^\s*\**(?:questions \[?\d+|examination of witness).*\n)+',
                                       self.plain_text, flags=re.IGNORECASE+re.MULTILINE)
        # third attempt: apparently there's no proper headers, so we just split where the Chair introduces the meeting.
        if len(panels_sections)==1 or len(panels_sections[0]) > 3000:
            panels_sections = re.split(r'(?:^\s*\**(?:Q\s?\d+|Chair))',
                                       self.plain_text, flags=re.MULTILINE, maxsplit=1)
            if len(panels_sections) > 1:
                panels_sections[1] = r'**Chair' + panels_sections[1]        # reinstate the 'Chair' word that we removed with re.split

        header_text = panels_sections[0]
        # Remove the notes on 'Use of the Transcript' which occasionally appear after the introductory witnesses list
        # (with a negative-lookahead check to make sure that the witnesses list doesn't in fact appear after the 'Use' notes)
        # (example: see 78101.html)
        header_text = re.sub('use of the transcript(?!.*(\nwitness|gave evidence).*).*',
                             '',header_text, flags=re.IGNORECASE + re.DOTALL)
        search_written_evidence = re.search('^Written evidence.*',
                                            header_text, flags=re.MULTILINE)
        if search_written_evidence:
            logger.info("""written evidence is mostly harmless, 
                        it gets ignored when we extract 
                        "Witnesses:" lists of speakers'""")


        for panel_text in panels_sections[1:]:
            # for each panel section, split the text into (i) Witnesses list; and
            # (ii) Q&A paragraphs.
            # Two patterns: one where the witnesses list begins with 'Witnesses: ...',
            # the second where it just comprises all of the text that happens
            # before the first question 'Q'.
            witness_line = None
            split_witnesses_and_questions_1 = re.search(r'(witness(?:es)?:.*\n|.*gave evidence\.{,4})([\s\S]*)',
                                                        panel_text, flags=re.IGNORECASE+re.MULTILINE) # second group captures the whole Q&A text: \s\S means any chracter, including newline, this approach required so we can use re.MULTILINE. Works better than re.DOTALL here, because we have to use re.MULTILINE here.
            split_witnesses_and_questions_2 = re.search(r'(.*\n)((?:\**Chair|\**Q\s?\d+)[\s\S]*)',
                                                        panel_text, flags=re.IGNORECASE + re.MULTILINE) # first group captures the (unlabelled) witnesses line, second group captures the whole Q&A text, which is expected to either begin with the Chair's introduction, or the first Question
            if split_witnesses_and_questions_1 and split_witnesses_and_questions_1.span()[0]<200:
                # (Additional check for location of the pattern in the panel_text:
                # Ignore 'witnesses' and 'gave evidence' as markers if they appear beyond the first couple of lines of text
                witness_line = split_witnesses_and_questions_1.groups()[0]
                all_questions_lines = all_questions_lines + \
                                      split_witnesses_and_questions_1.groups()[1] + '\n'
            elif split_witnesses_and_questions_2:
                # there are no witness lines that begin with 'Witnesses' so we just assume the first line is the witnesses list
                witness_line = 'Witnesses without a heading: ' + \
                               split_witnesses_and_questions_2.groups()[0]
                all_questions_lines = all_questions_lines + \
                                      split_witnesses_and_questions_2.groups()[1] + '\n'
            if witness_line:
                header_text = header_text + '\n' + witness_line


        extract_metadata_from_header_lines(self.transcript_data, header_text)

        # Q&A section handling follows
        # wherever **bold** text appears (possibly _**bolditalic**_, this is
        #   deemed to be a 'new speaker'.
        # Here, any new line starting with **bold** text, or a (non-bold)
        #   'Q' question number is labelled as representing a new speaker
        text_with_breaks = re.sub(r'\n(Q\s?\d+|\_?\*\*)', r'\nNEWSPEAKER\g<1>',
                                  all_questions_lines.strip())
        # break the text apart at the parts that we have identified as new speakers
        questions_sections = re.split('NEWSPEAKER', text_with_breaks)

        all_p=[]
        for i, p in enumerate(questions_sections):
            # try to extract a speaker name from the start of the line
            parts = re.search(r'((?:Q\s?\d+\s?)?\_?\*\*.*\*\*\_?)(.*)',
                              p, re.DOTALL)
            if parts:
                firstpart = re.sub(r'[\_\*:]*', '', parts.groups()[0])  # the stuff before the colon
                qparts = re.search(r'(Q[\s.]?\d+)(.*)', firstpart)
                section_info = {'section_id': i,
                                'spoken_text': parts.groups()[1].strip()}
                if qparts:
                    speaker_name = qparts.groups()[1].strip()
                    section_info['question_number'] =  qparts.groups()[0].strip()
                else:
                    speaker_name = firstpart.strip()

                section_info['speaker_string'] = re.sub('\s+', ' ', speaker_name)
                # speaker_info['speaker_id'] = self.speaker_metadata(speaker_name)['id']
                all_p.append(section_info)

            else:
                # if no speaker name extracted, then just take the line as 'unparsed text'
                all_p.append({'section_id': i, 'unparsed_text': p.strip()})

        all_speakers_names = [p['speaker_string'] for p in all_p
                              if 'speaker_string' in p]
        self.speakers_dict = self.match_speakers_to_people \
            (all_speakers_names, self.transcript_data['all_people'])

        for s in all_p:
            # map each speaker in the Q&A section to a unique person identified in the header
            if 'speaker_string' in s and len(s['speaker_string'])>1:
                s['speaker'] = self.speakers_dict[s['speaker_string']]

        self.transcript_data['all_sections'] = all_p

        self.json_text = json.dumps(self.transcript_data, sort_keys=False, indent=4)


    def match_speakers_to_people (self, speakers_names, people):
        #
        speakers_dict = {}
        people_names = [p for p in people]
        for s in [sn for sn in speakers_names if len(sn)>1]:  # no blanks, no singleton punctuation marks
            if s not in speakers_dict:
                person_match = process.extractOne(s, people_names,
                                                  score_cutoff=10)
                if person_match[1] < 95:
                    logger.warn('low score %i name match: %s chosen for %s' %
                                (person_match[1], person_match[0], s))
                speakers_dict[s] = {'label_count': 0,
                                    'person': people[person_match[0]].copy(),
                                    'fuzzy_match_score': person_match[1]}
            speakers_dict[s]['label_count'] += 1
        return speakers_dict


    # def speaker_metadata(self, speaker_name):
    #     # get speaker metadata by matching string speaker_name with speakers
    #     # identified in the transcript header
    #     m = {'id': 9999}
    #     return m


def extract_metadata_from_header_lines(d, header_text):
    # always expect Members to be listed first, before witnesses and others
    d['full_header_text_unparsed'] = header_text

    header_text = re.sub(r'\_ \_', '__', header_text)   # fix a limitation in html2text processing where an extra space will be put between patterns if both patterns are individually enclosed in italic (underline) markup
    header_text = re.sub(r'[\_\*]', '', header_text)

    try:
        # members_search = re.search(r'(members present.*?)(questions|examination)', header_text.strip(), re.IGNORECASE + re.DOTALL)
        members_search = re.search(r'(members present[:\s]*.*?\n)',
                                   header_text.strip(), re.IGNORECASE + re.DOTALL)
        if members_search is None:
            # Members list does not have a proper 'Members present' label. So just look for the first sentence in the
            # header which appears to include a '(chair)' in its text
            members_search = re.search(r'(.*\(chair.*\).*)',
                                       header_text.strip(), re.IGNORECASE)
        members_text = members_search.groups()[0].strip()
        d['members_text'] = members_text
        other_text = re.sub(members_text, '', header_text)
        d['members'] = people_from_text(members_text, 'member')
    except:
        logger.warning('FAILED TO PARSE MEMBERS FROM HEADER TEXT')
        other_text = ''
        d['members'] = {}

    try:
        # To find the witnesses, we simply take all the text after the word 'Witness.*' (and before 'gave evidence'). This may include
        # several lines of text, including separate witness lists for each panel.
        # (later we de-duplicate these and remove any newlines between witnesses names)
        # (alternative approach would be to use findall or finditer to process multiple lines
        #   each of which begins with witnesss')
        # witnesses_search = re.search(r'(\nWitness.*)',header_text.strip(), flags=re.DOTALL)
        witnesses_search = re.search(r'(\nWitness.*)',
                                     header_text.strip(), flags=re.DOTALL)
        if not witnesses_search:
            witnesses_search = re.search(r'(.*gave evidence)', header_text)

        witnesses_text = witnesses_search.groups()[0].strip()
        witnesses_text = witnesses_text.\
            replace('[', '\\[').\
            replace(']', '\\]').\
            replace('(', '\\(').\
            replace(')', '\\)')
        # remove 'written evidence' section (if any) indicated by a header then a series of hyperlinks
        witnesses_text = re.sub('.*(Written evidence|http).*',
                                '', witnesses_text)  # strangely cannot use re.IGNORECASE here, it makes the re.sub work inconsistently?!
        other_text = other_text.replace(witnesses_text, '') # use str.replace instead of re.sub which gets confused by parentheses and square brackets in the text
        # other_text = re.sub(witnesses_text, '', other_text)
        d['witnesses_text'] = witnesses_text
        d['header_other_text'] = other_text

        d['witnesses'] = people_from_text(witnesses_text, 'witness')
    except:
        logger.warning('FAILED TO PARSE WITNESSES TEXT FROM HEADER TEXT')
        d['witnesses'] = {}

    # d['all_people'] = d['members'] + d['witnesses']
    d['all_people'] = {**d['members'], **d['witnesses']}

    # create a unique index id for each person identified
    for i, s in enumerate(d['all_people']):
        d['all_people'][s]['id'] = i  # a unique index number for each speaker
    # d['all_people_names'] = [s['name'] for s in d['all_people']]

    return d


def people_from_text(names_string, speaker_type):
    names_groups = re.split(r'(?:[\n:;,()]+|and)', names_string)
    people = []
    name_extracted = []
    designation_extracted = []
    for ng in names_groups:
        if not re.search('(witness|members)',ng.strip(), flags=re.IGNORECASE):
            doc = nlp(ng.strip())
            # TODO: consider doing NLP on names word-by-word to avoid bad
            # results with 'David Davies' etc. 41400.html [doc #3]
            # Instead use SpaCy model core_web_md, this seems to have better NER?
            if ('PERSON' in [t.ent_type_ for t in doc]
                or 'Davies' in [t.text for t in doc]) \
                    and not 'Foundation' in [t.text for t in doc]:  # Elton John Foundation, for example
                if len(name_extracted)>0:
                    # we have found a new name, so we store the previous name and its designation information
                    # join the tokens that form the name, and remove any roman numerals at the start
                    append_person_name (name_extracted, designation_extracted,
                                        speaker_type, people)
                name_extracted = []
                designation_extracted = []
                for token in doc:
                    if token.pos_ == 'PROPN' or token.ent_type_ == 'PERSON' \
                            or token.text == 'Davies':       # includes honorifics via PROPN, and certain people's names that don't get parsed as PROPN but do get tagged as PERSON (e.g. Davies (!))
                        name_extracted.append(token.text)
            else:
                # 'designation' is just everything apart from the
                #   honorifics+names, that is, position, affiliation, etc.
                designation_extracted.append(ng.strip())
    if len(name_extracted) > 0:
        # store the final name
        append_person_name(name_extracted, designation_extracted,
                           speaker_type, people)

    # de-duplicate the people, store as a dictionary with name as key
    people_deduplicated = {}
    for p in people:
        # if p['name'] not in [pd['name'] for pd in people_deduplicated]:
        #     people_deduplicated.append(p)
        if p['name'] not in people_deduplicated:
            people_deduplicated[p['name']] = p
        if p['designation'].lower().startswith('chair') \
                and 'Chair' not in people_deduplicated \
                and speaker_type=='member':
            # a further entry for identifying the Chair of the meeting
            # (only relevant for members, not for witnesses who may be
            # 'Chair' of their own organisations)
            people_deduplicated['Chair'] = p.copy()
    return people_deduplicated


def append_person_name(name_parts, designation_parts, speaker_type, people_list):

    name_string = ' '.join(name_parts)
    # remove any roman numerals indicating the panel number from the start
    # of the first (witness) name in the list
    name_string = re.sub('^\s?[IV]+\.?\s', '', name_string).strip()
    designation_string = ', '.join(designation_parts)
    people_list.append({
        'name': name_string,
        'designation': designation_string,
        'speaker_type': speaker_type})

