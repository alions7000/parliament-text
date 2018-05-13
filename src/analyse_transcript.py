
import json
import pandas as pd
from textstat.textstat import textstat

def analyse_json(json_text):
    # consider moving this to be a feature of Transcript in the other module

    df_witnesses = pd.DataFrame(columns=['html_file_location', 'witness_name',
                                         'syllable_count','lexicon_count',
                                         'sentence_count',
                                         'syllables_per_word',
                                         'gunning_fog', 'smog_index',
                                         'text_standard'],
                      index=[])

    trscrpt = json.loads(json_text)
    if 'witnesses' in trscrpt:
        witnesses = trscrpt['witnesses']


        for s in trscrpt['all_sections']:
            if 'speaker' in s and 'person' in s['speaker'] and \
                    s['speaker']['person']['speaker_type']=='witness':
                witness =  witnesses[s['speaker']['person']['name']]
                witness.setdefault('all_text', []).append(s['spoken_text'])

        for i, p in enumerate(witnesses):
            if 'all_text' in witnesses[p]:
                witness_text = '\n\n'.join(witnesses[p]['all_text'])
                if len(witness_text) > 0:
                    stats_data = {'html_file_location': trscrpt['html_file_location'],
                                  'witness_name': p,
                                  'syllable_count': textstat.syllable_count(witness_text),
                                  'lexicon_count': textstat.lexicon_count(witness_text),
                                  'sentence_count': textstat.sentence_count(witness_text),
                                  'syllables_per_word': textstat.avg_syllables_per_word(witness_text),
                                  'gunning_fog': textstat.gunning_fog(witness_text),
                                  'smog_index': textstat.smog_index(witness_text),
                                  'text_standard': textstat.text_standard(witness_text)}
                    df_witnesses.loc['witness_%i' % i] = stats_data
                else:
                    df_witnesses.loc['witness_%i' % i, 'html_file_location'] = trscrpt['html_file_location']
                    df_witnesses.loc['witness_%i' % i, 'witness_name'] = p
            else:
                df_witnesses.loc['witness_%i' % i, 'html_file_location'] = trscrpt['html_file_location']
                df_witnesses.loc['witness_%i' % i, 'witness_name'] = p

    return df_witnesses