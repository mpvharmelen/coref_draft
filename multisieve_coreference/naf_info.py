from KafNafParserPy import *
from mention_data import *
from collections import defaultdict
import sys

dep_extractor = None
head2deps = defaultdict(list)


class CquotationNaf:
    '''
    This class encodes source and quotation
    '''

    def __init__(self):
        '''
        Constructor for quotations object
        '''
        self.sip = ''
        self.span = []
        self.source = []
        self.addressee = []
        self.topic = []
        self.beginquote = ''
        self.endquote = ''

    def add_span(self, span):

        self.span = span

    def add_span_id(self, span_id):

        self.span.append(span_id)


class Cconstituent_information:
    '''
    This class contains the main constructional information of mentions
    '''

    def __init__(self, head_id, span = []):
        '''
        Constructor for the constituent object
        :param head_id: term id of the head of the constituent
        :param span: list of term ids providing full span of hte constituent
        '''
        self.head_id = head_id
        self.span = span
        self.multiword = []
        self.modifiers = []
        self.etype = ''

    def set_span(self, span):

        self.span = span

    def get_span(self):

        return self.span

    def set_multiword(self, mw):

        self.multiword = mw

    def get_multiword(self):

        return self.multiword

    def set_modifiers(self, mods):

        self.modifiers = mods

    def add_modifier(self, mod):

        self.modifiers.append(mod)

    def get_modifiers(self):

        return self.modifiers

    def set_etype(self, etype):

        self.etype = etype

    def get_etype(self):

        return self.etype


def get_constituent(head):

    global dep_extractor

    mydeps = dep_extractor.get_full_dependents(head, [])
    if not head in mydeps:
        mydeps.append(head)
    return mydeps


def get_relevant_head_ids(nafobj):
    '''
    Returns list of term ids that head potential mention
    :param nafobj: input nafobj
    :return: list of term ids (string)
    '''

    nominal_pos = ['noun','pron','name']
    mention_heads = []
    for term in nafobj.get_terms():
        pos_tag = term.get_pos()
        if pos_tag in nominal_pos:
            mention_heads.append(term.get_id())
        #check if possessive pronoun
        elif pos_tag == 'det' and 'VNW(bez' in term.get_morphofeat():
            mention_heads.append(term.get_id())

    return mention_heads


def get_contituents(nafobj, mention_heads):

    global dep_extractor

    #global head2deps & check dependents?

    dep_extractor = nafobj.get_dependency_extractor()
    constituents = {}
    for head in mention_heads:
        mydeps = get_constituent(head)
        myConstituent = Cconstituent_information(head, mydeps)
        mwe, mods = get_mwe_and_modifiers(head)
        myConstituent.set_multiword(mwe)
        myConstituent.set_modifiers(mods)
        constituents[head] = myConstituent

    return constituents

def verify_span_uniqueness(found_spans, span):
    '''
    Function that checks whether entity is not listed twice (bug in cltl-spotlight; does not check whether entity has already been found
    :param found_spans: list of previously found spans
    :param span: current span
    :return: boolean (True if span has not been found before)
    '''

    for fspan in found_spans:
        if len(set(fspan) & set(span)) == len(span):
            return False
    return True


def find_closest_to_head(span):

    head_term_candidates = defaultdict(list)

    for tid in span:
        if tid in head2deps:
            count = 0
            for deprel in head2deps:
                if deprel[0] in span:
                    count += 1
            head_term_candidates[count].append(tid)
    max_deps = sorted(head_term_candidates.keys())[-1]
    best_candidates = head_term_candidates.get(max_deps)
    if len(best_candidates) > 0:
        return best_candidates[0]
    else:
        return span[0]


def find_head_in_span(span):
    '''
    Function that return the identifier of the head in the span
    :param span: list of term identiers
    :return: term_id
    '''

    head_term = None
    for term in span:
        constituent = get_constituent(term)
        constituent.append(term)
        if set(span).issubset(set(constituent)):
            if head_term is None:
                head_term = term
            else:
                print('span has more than one head')
    if head_term is None:
        head_term = find_closest_to_head(span)
    return head_term



def get_named_entities(nafobj):
    '''
    Function that runs to entity layer and registers named entities
    :param nafobj: the input nafobject
    :return: dictionary of entities, linked to span and entity type
    '''
    entities = {}
    found_spans = []
    for entity in nafobj.get_entities():
        etype = entity.get_type()
        for ref in entity.get_references():
            espan = ref.get_span().get_span_ids()
            head_term = find_head_in_span(espan)
            full_span = get_constituent(head_term)
            myConstituent = Cconstituent_information(head_term, full_span)
            myConstituent.set_multiword(espan)
            mwe, mods = get_mwe_and_modifiers(head_term)
            myConstituent.set_modifiers(mods)
            myConstituent.set_etype(etype)
            if verify_span_uniqueness(found_spans, espan):

                if not head_term in entities:
                    entities[head_term] = myConstituent
                else:
                    entities[head_term + 'b'] = myConstituent
                found_spans.append(espan)

    return entities



def get_mention_spans(nafobj):
    '''
    Function explores various layers of nafobj and retrieves all mentions possibly referring to an entity
    :param nafobj: input nafobj
    :return: dictionary of head term with as value constituent object (head id full head, modifiers, complete constituent0
    '''
    mention_heads = get_relevant_head_ids(nafobj)
    mention_constituents = get_contituents(nafobj, mention_heads)
    return mention_constituents


def get_string_of_term(nafobj, tid):

    my_term = nafobj.get_term(tid)
    termstring = ''
    latest_offset = '-1'

    for wid in my_term.get_span().get_span_ids():
        my_tok = nafobj.get_token(wid)
        # add space between tokens
        if len(termstring) > 0 and int(my_tok.get_offset) > latest_offset:
            termstring += ' '
        termstring += my_tok.get_text()
        latest_offset = int(my_tok.get_offset()) + int(my_tok.get_length())
    return termstring


def get_string_of_span(nafobj, span):

    mstring = ''
    latest_offset = -1
    for tid in span:
        my_term = nafobj.get_term(tid)
        for wid in my_term.get_span().get_span_ids():
            my_tok = nafobj.get_token(wid)
            #add space between tokens
            if len(mstring) > 0 and int(my_tok.get_offset()) > latest_offset:
                mstring += ' '
            mstring += my_tok.get_text()
            latest_offset = int(my_tok.get_offset()) + int(my_tok.get_length())
    return mstring


def get_pos_of_term(nafobj, tid):

    term = nafobj.get_term(tid)
    return term.get_pos()

def get_pos_of_span(nafobj, span):

    pos_seq = []
    for tid in span:
        tpos = get_pos_of_term(nafobj, tid)
        pos_seq.append(tpos)

    return pos_seq

def set_pronoun_person(morphofeat, mention):

    if '1' in morphofeat:
        mention.set_person('1')
    elif '2' in morphofeat:
        mention.set_person('2')
    elif '3' in morphofeat:
        mention.set_person('3')


def set_pronoun_number(morphofeat, myterm, mention):

    if 'ev' in morphofeat:
        mention.set_number('ev')
    elif 'mv' in morphofeat:
        mention.set_number('mv')
    elif 'getal' in morphofeat:
        lemma = myterm.get_lemma()
        if lemma in ['haar','zijn','mijn','jouw','je']:
            mention.set_number('ev')
        elif lemma in ['ons','jullie','hun']:
            mention.set_number('mv')


def set_pronoun_gender(morphofeat, mention):

    if 'fem' in morphofeat:
        mention.set_number('fem')
    elif 'masc' in morphofeat:
        mention.set_number('masc')


def analyze_pronoun(nafobj, term_id, mention):

    myterm = nafobj.get_term(term_id)
    morphofeat = myterm.get_morphofeat()
    set_pronoun_person(morphofeat, mention)
    set_pronoun_gender(morphofeat, mention)
    set_pronoun_number(morphofeat, myterm, mention)



def create_mention(nafobj, constituentInfo, head, mid):
    '''
    Function that creates mention object from naf information
    :param nafobj: the input naffile
    :param span: the mention span
    :param span: the id of the constituent's head
    :param idnr: the idnr (for creating a unique mention id
    :return:
    '''

    if head is None:
        head_id = head
    else:
        head_id = get_offset(nafobj, head)

    span = constituentInfo.get_span()
    offset_ids_span = get_span_in_offsets(nafobj, span)
    mention = Cmention(mid, span=offset_ids_span, head_id=head_id)
    #mwe info
    full_head_tids = constituentInfo.get_multiword()
    full_head_span = get_span_in_offsets(nafobj, full_head_tids)
    mention.set_full_head(full_head_span)
    #modifers:
    relaxed_span = offset_ids_span
    for mod_in_tids in constituentInfo.get_modifiers():
        mod_span = get_span_in_offsets(nafobj, mod_in_tids)
        mention.add_modifier(mod_span)
        for mid in mod_span:
            relaxed_span.remove(mid)
    mention.set_relaxed_span(relaxed_span)

    #set sequence of pos FIXME: if not needed till end; remove
    #os_seq = get_pos_of_span(nafobj, span)
    #mention.set_pos_seq(pos_seq)
    #set pos of head
    if head != None:
        head_pos = get_pos_of_term(nafobj, head)
        mention.set_head_pos(head_pos)
        if head_pos == 'pron':
            analyze_pronoun(nafobj, head, mention)

    begin_offset, end_offset = get_offsets_from_span(nafobj, span)
    mention.set_begin_offset(begin_offset)
    mention.set_end_offset(end_offset)

    return mention




def merge_mentions(mentions, heads):
    '''
    Function that merges information from entity mentions
    :param mentions: dictionary mapping mention number to specific mention
    :param heads: dictionary mapping head id to mention number
    :return: list of mentions where identical spans are merged
    '''
    final_mentions = {}

    #TODO: create merge function and merge identical candidates

    for m, val in mentions.items():
        found = False
        #FIXME: this was build with the idea that entity mentions did not have some head; changes now
        for prevm, preval in final_mentions.items():
            if val.head_id == preval.head_id:
                found = True
            elif set(val.span).issubset(set(preval.span)) and set(preval.span).issuperset(set(val.span)):
                found = True
        if not found:
            final_mentions[m] = val

    return final_mentions
    #    if val.head_id is None or val.head_id is not None:
    #        overlap = set(val.span) & set(heads.keys())
    #       if len(overlap) > 1:
    #            for head_id in overlap:
    #               mention_id = heads.get(head_id)
    #                if mention_id in final_mentions:
    #                    del final_mentions[mention_id]
    #        elif len(overlap) > 0:
    #            for head_id in overlap:
    #                final_mentions[m].head_id = head_id
    #                mention_id = heads.get(head_id)
    #                if mention_id in final_mentions:
    #                    del final_mentions[mention_id]

    return final_mentions


def get_offsets_from_span(nafobj, span):
    '''
    Function that identifies begin and end offset for a span of terms
    :param nafobj: input naf
    :param span: list of term identifiers
    :return:
    '''
    offsets = []
    end_offsets = []
    for termid in span:
        offset = get_offset(nafobj, termid)
        length = get_term_length(nafobj, termid)
        offsets.append(offset)
        end_offsets.append(offset+length)

    begin_offset = sorted(offsets)[0]
    end_offset = sorted(end_offsets)[-1]

    return begin_offset, end_offset


def get_term_length(nafobj, term_id):
    '''
    Function that returns the length of a term
    :param nafobj: input naf
    :param term_id: id of term in question
    :return:
    '''
    my_term = nafobj.get_term(term_id)
    length = 0
    expected_offset = 0
    for wid in my_term.get_span().get_span_ids():
        my_token = nafobj.get_token(wid)
        offset = int(my_token.get_offset())
        token_length = int(my_token.get_length())
        length += token_length
        if expected_offset != 0 and expected_offset != offset:
            length += offset - expected_offset
        expected_offset = offset + token_length

    return length


def get_offset(nafobj, term_id):
    '''
    Function that returns beginning offset of term
    :param nafobj: input naf
    :param term_id: id of term in question
    :return:
    '''
    my_term = nafobj.get_term(term_id)
    offsets = []
    for wid in my_term.get_span().get_span_ids():
        my_token = nafobj.get_token(wid)
        offsets.append(int(my_token.get_offset()))

    term_offset = sorted(offsets)[0]
    return term_offset


def get_mwe_and_modifiers(head_id):
    '''
    Function that identifies full mwe head and posthead modifiers
    :param head_id: head_id
    :return: list of full head terms, list of posthead modifiers
    '''

    global head2deps

    mwe = [head_id]
    mods = []

    if head_id in head2deps:
        for deprel in head2deps.get(head_id):
            if deprel[1] == 'mwp/mwp':
                mwe.append(head_id)
            elif deprel[1] == 'hd/mod':
                dep_constituent = get_constituent(deprel[0])
                mods.append(dep_constituent)

    return mwe, mods



def get_mentions(nafobj):
    '''
    Function that creates mention objects based on mentions retrieved from NAF
    :param nafobj: input naf
    :return: list of Cmention objects
    '''

    global head2deps
    dep2heads = create_headdep_dicts(nafobj)

    mention_spans = get_mention_spans(nafobj)
    mentions = {}
    heads = defaultdict(list)
    for head, constituentInfo in mention_spans.items():
        mid = 'm' + str(len(mentions))
        mention = create_mention(nafobj, constituentInfo, head, mid)
        mentions[mid] = mention
        heads[head].append(mid)

    entities = get_named_entities(nafobj)
    for entity, constituent in entities.items():
        mid = 'm' + str(len(mentions))
        mention = create_mention(nafobj, constituent, entity, mid)
        mention.set_entity_type(constituent.get_etype())
        mentions[mid] = mention
        heads[entity].append(mid)

    mentions = merge_mentions(mentions, heads)

    return mentions


def get_starting_count(nafobj):

    coref_counter = 1
    for coref in nafobj.get_corefs():
        coref_counter += 1

    return coref_counter


def get_terms_from_offsets(nafobj, offset_span, head_offset = -1):

    wids = []
    head_wid = ''
    for token in nafobj.get_tokens():
        if int(token.get_offset()) in offset_span:
            wids.append(token.get_id())
            if int(token.get_offset()) == head_offset:
                head_wid = token.get_id()

    tids = []
    head_tid = ''
    for term in nafobj.get_terms():
        if term.get_span().get_span_ids()[0] in wids:
            tids.append(term.get_id())
        if head_wid in term.get_span().get_span_ids():
            head_tid = term.get_id()

    return tids, head_tid

def get_span_in_offsets(nafobj, span):

    offset_span = []
    for tid in span:
        toffset = get_offset(nafobj, tid)
        offset_span.append(toffset)
    return offset_span

def create_span(term_id_span, head_id):
    '''
    Creates naf span object where head id is set
    :param term_id_span: list of term ids
    :param head_id: identifier for the head id
    :return: naf span object
    '''
    mySpan = Cspan()
    for term in term_id_span:
        if term == head_id:
            myTarget = Ctarget()
            myTarget.set_id(term)
            myTarget.set_as_head()
            mySpan.add_target(myTarget)
        else:
            mySpan.add_target_id(term)
    return mySpan


def add_coreference_to_naf(nafobj, corefclasses, mentions):

    start_count = get_starting_count(nafobj)
    for mids in sorted(corefclasses.values()):
        if not mids is None:
            mids = set(mids)
            if len(mids) > 1:
                nafCoref = Ccoreference()
                cid = 'co' + str(start_count)
                start_count += 1
                nafCoref.set_id(cid)
                nafCoref.set_type('entity')
                for mid in mids:
                    mention = mentions.get(mid)
                    term_id_span, head_id = get_terms_from_offsets(nafobj,mention.span,mention.head_id)
                    coref_span = create_span(term_id_span, head_id)
                    nafCoref.add_span_object(coref_span)
                nafobj.add_coreference(nafCoref)


def get_quotation_spans(nafobj):
    '''
    Function that goes through nafobj and identifies spans of quotations
    :param nafobj: input naf
    :return: list of quotation objects with span defined
    '''

    #FIXME investigate on development corpus what to do with embedded quotations; for now we'll assume a double quotation within a single quote is an error

    in_double_quotation = False
    in_single_quotation = False
    quotations = []
    for term in nafobj.get_terms():
        if term.get_lemma() in ['"','&amp;amp;amp;quot;']:
            if not in_double_quotation:
                in_double_quotation = True
                myQuote = CquotationNaf()
                myQuote.beginquote = term.get_id()
            else:
                in_double_quotation = False
                myQuote.endquote = term.get_id()
                quotations.append(myQuote)
            #break off single quotation if double quotation found during this
            if in_single_quotation:
                in_single_quotation = False
        elif in_double_quotation:
            myQuote.add_span_id(term.get_id())

        if term.get_lemma() == "'":
            if not in_single_quotation:
                in_single_quotation = True
                myQuoteSingle = CquotationNaf()
                myQuoteSingle.beginquote = term.get_id()
            else:
                in_single_quotation = False
                myQuoteSingle.endquote = term.get_id()
                quotations.append(myQuoteSingle)
        elif in_single_quotation:
            myQuoteSingle.add_span_id(term.get_id())

    return quotations



def create_headdep_dicts(nafobj):
    '''
    Function that creates dictionaries of dep to heads and head to deps
    :param nafobj: nafobj from input file
    :return: None
    '''

    global head2deps

    dep2heads = defaultdict(list)

    for dep in nafobj.get_dependencies():
        head = dep.get_from()
        mydep = dep.get_to()
        relation = dep.get_function()
        dep2heads[mydep].append([head, relation])
        head2deps[head].append([mydep, relation])
    return dep2heads

def create_set_of_tids_from_tidfunction(tidfunctionlist):

    tids = set()
    for tidfunc in tidfunctionlist:
        tids.add(tidfunc[0])

    return tids

def find_relevant_spans(deps, outside_ids):

    for dep in deps:
        if dep[0] in outside_ids and dep[1] in ['nucl/tag','dp/dp']:
            return dep[0]

    return None


def analyze_head_relations(nafobj, head_term, head2deps):

    dependents = head2deps.get(head_term)
    speaker = None
    addressee = None
    topic = None
    #FIXME: we want to check the preposition
    if dependents is not None:
        for dep in dependents:
            if dep[1] == 'hd/su':
                speaker = get_constituent(dep[0])
            elif dep[1] == 'hd/obj2':
                term = nafobj.get_term(dep[0])
                if term.get_pos() == 'prep':
                    if dep[0] in head2deps:
                        for deprel in head2deps.get(dep[0]):
                            if deprel[1] == 'hd/obj1':
                                addressee = get_constituent(deprel[0])
                else:
                    addressee = get_constituent(dep[0])
            elif dep[1] in ['hd/mod']:
                term = nafobj.get_term(dep[0])
                if term.get_pos() == 'prep':

                    if dep[0] in head2deps:
                        #override addressee by complement if headed by preposition
                        for deprel in head2deps.get(dep[0]):
                            if deprel[1] == 'hd/obj1':
                                if term.get_lemma() == 'tegen':
                                    addressee = get_constituent(deprel[0])
                                elif term.get_lemma() == 'over':
                                    topic = get_constituent(deprel[0])

    else:
        print(head_term, 'has no dependents')

    return speaker, addressee, topic


def identify_direct_links_to_sip(nafobj, quotation):
    '''
    Function that identifies
    :param head2deps: dictionary linking head to dependents
    :param quotation: the quotation itself
    :return: boolean indicating whether source was found
    '''

    global head2deps

    for tid in quotation.span:
        deps = head2deps.get(tid)
        if not deps is None:
            depids = create_set_of_tids_from_tidfunction(deps)
            #if one of deps falls outside of quote, it can be linked to the sip
            span_with_quotes = quotation.span + [quotation.beginquote] + [quotation.endquote]
            if len(depids.difference(set(span_with_quotes))) > 0:
                my_joint_set = depids.difference(set(span_with_quotes))
                head_term = find_relevant_spans(deps, my_joint_set)
                if not head_term is None:
                    speaker, addressee, topic = analyze_head_relations(nafobj, head_term, head2deps)
                    if not speaker is None:
                        speaker_in_offsets = get_span_in_offsets(nafobj, speaker)
                        quotation.source = speaker_in_offsets
                    if not addressee is None:
                        addressee_in_offsets = get_span_in_offsets(nafobj, addressee)
                        quotation.addressee = addressee_in_offsets
                    if not topic is None:
                        topic_in_offsets = get_span_in_offsets(nafobj, topic)
                        quotation.topic = topic_in_offsets


def check_if_quotation_contains_dependent(quotation, dep2heads):

    #FIXME: verify on larger set of development corpus whether this behavior is correct
    for tid in quotation.span:
        heads = dep2heads.get(tid)
        if not heads is None:
            headids = create_set_of_tids_from_tidfunction(heads)
            span_with_quotes = quotation.span + [quotation.beginquote] + [quotation.endquote]
            if len(headids.difference(set(span_with_quotes))) > 0:
                for headid in headids.difference(set(span_with_quotes)):
                    for headrel in heads:
                        if headrel[0] == headid:
                            if headrel[1] in ['cmp/body','hd/predc','hd/obj1','hd/vc','hd/su','hd/pc']:
                                return False
                            elif headrel[1] in ['crd/cnj']:
                                motherheadrels = dep2heads.get(headrel[0])
                                for mhid in motherheadrels:
                                    if mhid[1] in ['cmp/body','hd/predc','hd/obj1','hd/vc','hd/su','hd/pc']:
                                        return False
                                    elif not mhid[1] in ['hd/app','tag/nucl','--/--','dp/dp','-- / --','nucl/sat']:
                                        print(tid, headids.difference(set(span_with_quotes)), 'has outside head')
                                        print(motherheadrels)
                            elif not headrel[1] in ['hd/app','tag/nucl','--/--','dp/dp','-- / --','nucl/sat']:
                                print(tid, headids.difference(set(span_with_quotes)), 'has outside head')
                                print(heads, quotation.span)
    return True


def get_sentences_of_quotation(nafobj, quotation):

    sentences = set()

    for tid in quotation.span:
        term = nafobj.get_term(tid)
        wid = term.get_span().get_span_ids()[0]
        token = nafobj.get_token(wid)
        sentence_nr = token.get_sent()
        #storing them as integers; they need to be sorted later
        sentences.add(int(sentence_nr))
    return sentences


def get_previous_and_next_sentence(sentences):

    ordered_sentences = sorted(sentences)
    previous_sentence = ordered_sentences[0] - 1
    following_sentence = ordered_sentences[-1] + 1

    return previous_sentence, following_sentence

def retrieve_sentence_preceding_sip(nafobj, terms):

    global head2deps

    source_head = None
    for tid in terms:
        myterm = nafobj.get_term(tid)
        if myterm.get_lemma() == 'volgens':
            deps = head2deps.get(tid)
            for dep in deps:
                if dep[1] == 'hd/obj1':
                    source_head = dep[0]

    return source_head


def retrieve_quotation_following_sip(nafobj, terms):

    global head2deps

    source_head = None
    for tid in terms:
        myterm = nafobj.get_term(tid)
        if myterm.get_lemma() == 'aldus':
            deps = head2deps.get(tid)
            for dep in deps:
                if dep[1] == 'hd/obj1':
                    source_head = dep[0]

    return source_head


def identify_addressee_or_topic_relations(nafobj, tid, dep2heads, quotation):

    #FIXME: language specific function
    heads = dep2heads.get(tid)
    if heads is not None:
        for headrel in heads:
            headterm = nafobj.get_term(headrel[0])
            if headterm.get_lemma() == 'tegen' or headrel[1] == 'hd/obj2':
                myconstituent = get_constituent(headterm.get_id())
                addressee = get_span_in_offsets(nafobj, myconstituent)
                quotation.addressee = addressee
                return True
            elif headterm.get_lemma() == 'over':
                myconstituent = get_constituent(headterm.get_id())
                topic = get_span_in_offsets(nafobj, myconstituent)
                quotation.topic = topic
                return True
    return False


def get_candidates_not_part_of_addressee_topic(candidate_names, quotation):

    remaining_candidates = []
    covered_tids = quotation.addressee + quotation.topic
    for tid in candidate_names:
        if not tid in covered_tids:
            myconstituent = get_constituent(tid)
            remaining_candidates.append(myconstituent)
            covered_tids += myconstituent
    return remaining_candidates


def extract_full_names_or_prons(nafobj, constituents):

    names = []
    for const in constituents:
        name = []
        for tid in const:
            term = nafobj.get_term(tid)
            if term.get_pos() == 'name':
                name.append(tid)
        if len(name) == 0 and len(const) != 0:
            names.append(const)
        else:
            names.append(name)
    return names


def get_closest(candidates):

    closest = []
    selected_cand = []
    for cand in candidates:
        candnums = create_ordered_number_span(cand)
        if len(closest) == 0 or candnums[-1] > closest[-1]:
            closest = candnums
            selected_cand = cand
    return selected_cand



def identify_primary_candidate(candidates, dep2heads):

    for cand in candidates:
        for tid in cand:
            if tid in dep2heads:
                for headrel in dep2heads:
                    if headrel[1] == 'hd/su':
                        return cand

    #if no highest ranking found, return closest candidate
    return get_closest(candidates)



def find_name_or_pronoun(nafobj, preceding_terms, dep2heads, quotation):

    #FIXME: not over paragraph borders; if nothing found, sentence after can also work
    candidate_names = []
    for tid in preceding_terms:
        term = nafobj.get_term(tid)
        if term.get_pos() == 'name' or term.get_pos() == 'pron':
            if not identify_addressee_or_topic_relations(nafobj, tid, dep2heads, quotation):
                candidate_names.append(term.get_id())

    #change make dictionary with head term to constituent
    candidates = []
    if len(candidate_names) > 0:
        remaining_candidates = get_candidates_not_part_of_addressee_topic(candidate_names, quotation)
        if len(remaining_candidates) > 0:
            candidates = extract_full_names_or_prons(nafobj, remaining_candidates)
            if len(candidates) == 1:
                candidate_in_offsets = get_span_in_offsets(nafobj, candidates[0])
                quotation.source = candidate_in_offsets
            else:
                candidate = identify_primary_candidate(candidates, dep2heads)
                candidate_in_offsets = get_span_in_offsets(nafobj, candidate)
                quotation.source = candidate_in_offsets


def create_ordered_number_span(term_list):

    number_list = []
    for tid in term_list:
        if 't_' in tid:
            tnumber = int(tid.lstrip('t_'))
            number_list.append(tnumber)
        elif 't' in tid:
            tnumber = int(tid.lstrip('t'))
            number_list.append(tnumber)

    return sorted(number_list)

def get_preceding_terms_in_sentence(first_sentence, quotation_span):


    #FIXME; move to offset based ids earlier; then this hack is not necessary
    quotation_numbers = create_ordered_number_span(quotation_span)
    preceeding_terms = []
    for tid in first_sentence:
        if 't_' in tid:
            tnumber = int(tid.lstrip('t_'))
            if tnumber < quotation_numbers[0]:
                preceeding_terms.append(tid)
        elif 't' in tid:
            tnumber = int(tid.lstrip('t'))
            if tnumber < quotation_numbers[0]:
                preceeding_terms.append(tid)
    return preceeding_terms

def get_following_terms_in_sentence(last_sentence, quotation_span):

    #FIXME; move to offset based ids earlier; then this hack is not necessary
    quotation_numbers = create_ordered_number_span(quotation_span)
    following_terms = []
    for tid in last_sentence:
        if 't_' in tid:
            tnumber = int(tid.lstrip('t_'))
            if tnumber > quotation_numbers[0]:
                following_terms.append(tid)
        elif 't' in tid:
            tnumber = int(tid.lstrip('t'))
            if tnumber > quotation_numbers[0]:
                following_terms.append(tid)
    return following_terms


def identify_source_introducing_constructions(nafobj, quotation, sentence_to_term, dep2heads):
    '''
    Function that identifies structures that introduce sources of direct quotes
    :param nafobj: the input nafobj
    :param quotation: the quotation
    :return: None
    '''

    sentences = get_sentences_of_quotation(nafobj, quotation)
    prev_sent, follow_sent = get_previous_and_next_sentence(sentences)
    #FIXME: find out using development data whether preceding and following sentence should be taken into account or not
    #preceding_terms = sentence_to_term.get(str(prev_sent)) + sentence_to_term.get(str(prev_sent + 1))

    #start with 'aldus' construction; this is more robust
    following_terms = get_following_terms_in_sentence(sentence_to_term.get(str(follow_sent - 1)),quotation.span)
    source_head = retrieve_quotation_following_sip(nafobj,following_terms)

    if source_head is None:
        preceding_terms = get_preceding_terms_in_sentence(sentence_to_term.get(str(prev_sent + 1)),quotation.span)
        source_head = retrieve_sentence_preceding_sip(nafobj, preceding_terms)

    if source_head is not None:
        source_constituent = get_constituent(source_head)
        source_in_offsets = get_span_in_offsets(nafobj, source_constituent)
        quotation.source = source_in_offsets
    else:
        find_name_or_pronoun(nafobj, preceding_terms, dep2heads, quotation)
    #3. check previous sentence for name or pronoun


def get_sentence_to_terms(nafobj):

    token2terms = {}
    for term in nafobj.get_terms():
        tokens = term.get_span().get_span_ids()
        for tok in tokens:
            token2terms[tok] = term.get_id()

    sentence2terms = defaultdict(list)
    for token in nafobj.get_tokens():
        sent_nr = token.get_sent()
        term_id = token2terms.get(token.get_id())
        sentence2terms[sent_nr].append(term_id)

    return sentence2terms


def get_reduced_list_of_quotations(toremove, found_quotations):

    reduced_quotations = []
    for quote in found_quotations:
        wrong = False
        for wrong_quote in toremove:
            if set(quote.span) == set(wrong_quote.span):
                wrong = True
        if not wrong:
            reduced_quotations.append(quote)
    return reduced_quotations


def identify_direct_quotations(nafobj, mentions):
    '''
    Function that identifies direct quotations in naf
    :param nafobj: input naf object
    :return:
    '''

    nafquotations = get_quotation_spans(nafobj)
    dep2heads = create_headdep_dicts(nafobj)
    toremove = []
    for quotation in nafquotations:
        identify_direct_links_to_sip(nafobj, quotation)
        if len(quotation.source) == 0:
            #this can lead to indication of quotation being attribution rather than quotation
            if check_if_quotation_contains_dependent(quotation, dep2heads):
                sentence_to_terms = get_sentence_to_terms(nafobj)
                identify_source_introducing_constructions(nafobj, quotation, sentence_to_terms, dep2heads)
            else:
                toremove.append(quotation)

    finalnafquotations = get_reduced_list_of_quotations(toremove, nafquotations)
    quotations = []
    for qid, nafquotation in enumerate(finalnafquotations):
        myquote = create_coref_quotation_from_quotation_naf(nafobj, nafquotation, mentions, qid)
        quotations.append(myquote)

    return quotations


def link_span_ids_to_mentions(span, mentions):
    '''
    Function that takes span as input and finds out whether this corresponds to a mention candidate and, if so, which one
    :param span: list of span ids
    :param mentions: object containing all candidate mentions
    :return:
    '''

    for key, mention in mentions.items():
        if set(span) == set(mention.span):
            return key

    for key, mention in mentions.items():
        if set(span).issubset(set(mention.span)) or set(span).issuperset(mention.span):
            return key

    import traceback; print(traceback.extract_stack(limit=2)[-1][2] + " - span: " + str(span))


def create_coref_quotation_from_quotation_naf(nafobj, nafquotation, mentions, quote_id):
    '''
    Function that turns naf quotation object into quotation object to be passed on to multisieve
    :param nafobj: input naf
    :param nafquotation: quotation object with naf specific information
    :param quote_id: identifier for quotation
    :return:
    '''

    myQuote = Cquotation(quote_id)

    quotespan = get_span_in_offsets(nafobj, nafquotation.span)
    myQuote.set_span(quotespan)

    quotestring = get_string_of_span(nafobj, nafquotation.span)
    myQuote.set_string(quotestring)

    beginoffset, endoffset = get_offsets_from_span(nafobj, nafquotation.span)
    myQuote.set_begin_offset(beginoffset)
    myQuote.set_end_offset(endoffset)

    if len(nafquotation.source) > 0:
        source_mention_id = link_span_ids_to_mentions(nafquotation.source, mentions)
        myQuote.set_source(source_mention_id)
    if len(nafquotation.addressee) > 0:
        addressee_mention_id = link_span_ids_to_mentions(nafquotation.addressee, mentions)
        myQuote.set_addressee(addressee_mention_id)
    if len(nafquotation.topic) > 0:
        topic_mention_id = link_span_ids_to_mentions(nafquotation.topic, mentions)
        myQuote.set_topic(topic_mention_id)

    return myQuote


def initiate_id2string_dicts(nafobj):

    id2string = {}
    id2lemma = {}

    for term in nafobj.get_terms():
        identifier = get_offset(nafobj, term.get_id())
        lemma = term.get_lemma()
        id2lemma[identifier] = lemma

    for token in nafobj.get_tokens():
        identifier = int(token.get_offset())
        surface_string = token.get_text()
        id2string[identifier] = surface_string

    return id2string, id2lemma
