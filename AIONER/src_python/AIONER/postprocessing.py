# -*- coding: utf-8 -*-
"""
Created on Nov 03 20:08:30 2022 
@author: luol2
"""


import logging
import regex
import sys
import io

"""
A Python 3 refactoring of Vincent Van Asch's Python 2 code at
http://www.cnts.ua.ac.be/~vincent/scripts/abbreviations.py
Based on
A Simple Algorithm for Identifying Abbreviations Definitions in Biomedical Text
A. Schwartz and M. Hearst
Biocomputing, 2003, pp 451-462.
"""

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
log = logging.getLogger('Abbre')


class Candidate(str):
    def __init__(self, value):
        super().__init__()
        self.start = 0
        self.stop = 0

    def set_position(self, start, stop):
        self.start = start
        self.stop = stop


def yield_lines_from_file(file_path):
    with open(file_path, 'rb') as f:
        for line in f:
            try:
                line = line.decode('utf-8')
            except UnicodeDecodeError:
                line = line.decode('latin-1').encode('utf-8').decode('utf-8')
            line = line.strip()
            yield line
        f.close()


def yield_lines_from_doc(doc_text):
    for line in doc_text.split("\n"):
        yield line.strip()


def best_candidates(sentence):
    """
    :param sentence: line read from input file
    :return: a Candidate iterator
    """

    if '(' in sentence:
        # Check some things first
        if sentence.count('(') != sentence.count(')'):
            raise ValueError("Unbalanced parentheses: {}".format(sentence))

        if sentence.find('(') > sentence.find(')'):
            raise ValueError("First parentheses is right: {}".format(sentence))

        closeindex = -1
        while 1:
            # Look for open parenthesis
            openindex = sentence.find('(', closeindex + 1)

            if openindex == -1: break

            # Look for closing parentheses
            closeindex = openindex + 1
            open = 1
            skip = False
            while open:
                try:
                    char = sentence[closeindex]
                except IndexError:
                    # We found an opening bracket but no associated closing bracket
                    # Skip the opening bracket
                    skip = True
                    break
                if char == '(':
                    open += 1
                elif char in [')', ';', ':']:
                    open -= 1
                closeindex += 1

            if skip:
                closeindex = openindex + 1
                continue

            # Output if conditions are met
            start = openindex + 1
            stop = closeindex - 1
            candidate = sentence[start:stop]

            # Take into account whitespace that should be removed
            start = start + len(candidate) - len(candidate.lstrip())
            stop = stop - len(candidate) + len(candidate.rstrip())
            candidate = sentence[start:stop]

            if conditions(candidate):
                new_candidate = Candidate(candidate)
                new_candidate.set_position(start, stop)
                yield new_candidate


def conditions(candidate):
    """
    Based on Schwartz&Hearst
    2 <= len(str) <= 10
    len(tokens) <= 2
    re.search('\p{L}', str)
    str[0].isalnum()
    and extra:
    if it matches (\p{L}\.?\s?){2,}
    it is a good candidate.
    :param candidate: candidate abbreviation
    :return: True if this is a good candidate
    """
    viable = True
    if regex.match('(\p{L}\.?\s?){2,}', candidate.lstrip()):
        viable = True
    if len(candidate) < 2 or len(candidate) > 10:
        viable = False
    if len(candidate.split()) > 2:
        viable = False
    if not regex.search('\p{L}', candidate):
        viable = False
    if not candidate[0].isalnum():
        viable = False

    return viable


def get_definition(candidate, sentence):
    """
    Takes a candidate and a sentence and returns the definition candidate.
    The definintion candidate is the set of tokens (in front of the candidate)
    that starts with a token starting with the first character of the candidate
    :param candidate: candidate abbreviation
    :param sentence: current sentence (single line from input file)
    :return: candidate definition for this abbreviation
    """
    # Take the tokens in front of the candidate
    tokens = regex.split(r'[\s\-]+', sentence[:candidate.start - 2].lower())
    #print(tokens)
    # the char that we are looking for
    key = candidate[0].lower()

    # Count the number of tokens that start with the same character as the candidate
#     print(tokens)
    firstchars = [t[0] for t in tokens]
#     print(firstchars)
    definition_freq = firstchars.count(key)
    candidate_freq = candidate.lower().count(key)

    # Look for the list of tokens in front of candidate that
    # have a sufficient number of tokens starting with key
    if candidate_freq <= definition_freq:
        # we should at least have a good number of starts
        count = 0
        start = 0
        startindex = len(firstchars) - 1
        
        while count < candidate_freq:
            if abs(start) > len(firstchars):
                raise ValueError("candiate {} not found".format(candidate))
            start -= 1
            # Look up key in the definition
            try:
                startindex = firstchars.index(key, len(firstchars) + start)
            except ValueError:
                pass

            # Count the number of keys in definition
            count = firstchars[startindex:].count(key)
        
        # We found enough keys in the definition so return the definition as a definition candidate
        start = len(' '.join(tokens[:startindex]))
        stop = candidate.start - 1
        candidate = sentence[start:stop]

        # Remove whitespace
        start = start + len(candidate) - len(candidate.lstrip())
        stop = stop - len(candidate) + len(candidate.rstrip())
        candidate = sentence[start:stop]

        new_candidate = Candidate(candidate)
        new_candidate.set_position(start, stop)
        #print('new_candidate:')
        #print(new_candidate,start,stop)
        return new_candidate

    else:
        raise ValueError('There are less keys in the tokens in front of candidate than there are in the candidate')


def select_definition(definition, abbrev):
    """
    Takes a definition candidate and an abbreviation candidate
    and returns True if the chars in the abbreviation occur in the definition
    Based on
    A simple algorithm for identifying abbreviation definitions in biomedical texts, Schwartz & Hearst
    :param definition: candidate definition
    :param abbrev: candidate abbreviation
    :return:
    """


    if len(definition) < len(abbrev):
        raise ValueError('Abbreviation is longer than definition')

    if abbrev in definition.split():
        raise ValueError('Abbreviation is full word of definition')

    sindex = -1
    lindex = -1

    while 1:
        try:
            longchar = definition[lindex].lower()
        except IndexError:
            raise

        shortchar = abbrev[sindex].lower()

        if not shortchar.isalnum():
            sindex -= 1

        if sindex == -1 * len(abbrev):
            if shortchar == longchar:
                if lindex == -1 * len(definition) or not definition[lindex - 1].isalnum():
                    break
                else:
                    lindex -= 1
            else:
                lindex -= 1
                if lindex == -1 * (len(definition) + 1):
                    raise ValueError("definition {} was not found in {}".format(abbrev, definition))

        else:
            if shortchar == longchar:
                sindex -= 1
                lindex -= 1
            else:
                lindex -= 1
#     print('lindex:',lindex,len(definition),definition[lindex:len(definition)])
    new_candidate = Candidate(definition[lindex:len(definition)])
    new_candidate.set_position(definition.start+lindex+len(definition), definition.stop)
    definition = new_candidate

    tokens = len(definition.split())
    length = len(abbrev)

    if tokens > min([length + 5, length * 2]):
        raise ValueError("did not meet min(|A|+5, |A|*2) constraint")

    # Do not return definitions that contain unbalanced parentheses
    if definition.count('(') != definition.count(')'):
        raise ValueError("Unbalanced parentheses not allowed in a definition")
#     print('select:')
#     print(definition,definition.start, definition.stop)
    new_definition_dict={'definition':definition,'start':definition.start,'stop':definition.stop}
    return new_definition_dict


def extract_abbreviation_definition_pairs(file_path=None, doc_text=None):
    abbrev_map = [] #[{definition,start,stop,abbre}]
    abbr_full_dict={} #{abbre:(fullname_start,fullname_stop)}
    fullloc_abbr_dict={} #{"fullname_s fullname_e":abbr}
    omit = 0
    written = 0
    if file_path:
        sentence_iterator = enumerate(yield_lines_from_file(file_path))
    elif doc_text:
        sentence_iterator = enumerate(yield_lines_from_doc(doc_text))
    else:
        return abbrev_map

    for i, sentence in sentence_iterator:
        #print(sentence)
        try:
            for candidate in best_candidates(sentence):
                #print(candidate)
                try:
                    #print('begin get definition')
                    definition = get_definition(candidate, sentence)
                    #print('get_definition:')
                    #print(definition)
                    
                except (ValueError, IndexError) as e:
                    #log.debug("{} Omitting candidate {}. Reason: {}".format(i, candidate, e.args[0]))
                    omit += 1
                else:
                    try:
                        definition_dict = select_definition(definition, candidate)
                    except (ValueError, IndexError) as e:
                        #log.debug("{} Omitting definition {} for candidate {}. Reason: {}".format(i, definition_dict, candidate, e.args[0]))
                        omit += 1
                    else:
                        definition_dict['abbre']=candidate
                        abbrev_map.append(definition_dict)
                        abbr_full_dict[definition_dict['abbre']]=(definition_dict['start'],definition_dict['stop'])
                        fullloc_abbr_dict[str(definition_dict['start'])+' '+str(definition_dict['stop'])]=definition_dict['abbre']
                        written += 1
        except (ValueError, IndexError) as e:
            log.debug("{} Error processing sentence {}: {}".format(i, sentence, e.args[0]))
    log.debug("{} abbreviations detected and kept ({} omitted)".format(written, omit))
    return abbrev_map,abbr_full_dict,fullloc_abbr_dict


def postprocess_abbr(ner_result,ori_text): #ner_result {'entity_s entity_e':[eles]}
    
    final_result=[]
    if len(ner_result)==0:
        return {}
    
    # abbr recognition
    abbr_list, abbr_full_dict,fullloc_abbr_dict=extract_abbreviation_definition_pairs(doc_text=ori_text)
    # print(abbr_list)
    #print(abbr_full_dict)
    # print(fullloc_abbr_dict)
    
    #ner loc
    ner_loc_result={}
    for ele in ner_result.keys():
        # ner_loc_result[ner_result[ele][0]+' '+ner_result[ele][1]]=ner_result[ele]
        ner_loc_result[ner_result[ele][1]]=ner_result[ele]

    # remove the wrong abbr, add miss abbr
    for entity_loc in ner_result.keys():
        
        if (ner_result[entity_loc][-1]!='CellLine') and (ner_result[entity_loc][2] in abbr_full_dict.keys()) : #the entity is abbr
            #use the fullname entity type
            fullname_loc_e=str(abbr_full_dict[ner_result[entity_loc][2]][1])

            if fullname_loc_e in ner_loc_result.keys(): #fullname is entity
                final_result.append([ner_result[entity_loc][0], ner_result[entity_loc][1],ner_result[entity_loc][2],ner_loc_result[fullname_loc_e][-1]])
            
                                    
        # # fullname_loc=str(abbr_full_dict[ner_result[entity_loc][2]][0])+' '+str(abbr_full_dict[ner_result[entity_loc][2]][1])
        #     fullname_loc_e=str(abbr_full_dict[ner_result[entity_loc][2]][1])
        #     if (ner_result[entity_loc][-1]=='Gene') or (ner_result[entity_loc][-1]=='FamilyName'): #gene keep original entity type
        #         if fullname_loc_e in ner_loc_result.keys(): #fullname is entity
        #             final_result.append(ner_result[entity_loc]) 
        #         # elif fullname_loc_e in ner_loc_result.keys(): #fullname is entity
        #         #     final_result.append(ner_result[entity_loc]) 
        #     else: # no-gene use the fullname entity type
        #         if fullname_loc_e in ner_loc_result.keys(): #fullname is entity
        #             final_result.append([ner_result[entity_loc][0], ner_result[entity_loc][1],ner_result[entity_loc][2],ner_loc_result[fullname_loc_e][-1]])
        #         # elif fullname_loc_e in ner_loc_result.keys(): #fullname is entity
        #             # final_result.append([ner_result[entity_loc][0], ner_result[entity_loc][1],ner_result[entity_loc][2],ner_loc_result[fullname_loc_e][-1]])

           
                    
        elif entity_loc in fullloc_abbr_dict.keys(): #the entity is fullname
            abbr_loc_s=ori_text.find(fullloc_abbr_dict[entity_loc],int(ner_result[entity_loc][1]))
            final_result.append(ner_result[entity_loc])
            if abbr_loc_s>=0:
                abbr_loc_e=abbr_loc_s+len(fullloc_abbr_dict[entity_loc])
                abbr_loc=str(abbr_loc_s)+' '+str(abbr_loc_e)
                # print(abbr_loc,fullloc_abbr_dict[entity_loc])
                if abbr_loc not in ner_result.keys():#add abbr 
                    final_result.append([str(abbr_loc_s),str(abbr_loc_e),ori_text[abbr_loc_s:abbr_loc_e],ner_result[entity_loc][-1]])
            
        else:
            #if entity is only Punctuation
            if len(ner_result[entity_loc][2])==1 and (not ner_result[entity_loc][2].isalpha()):
                pass
                # print(ner_result[entity_loc])
            else:
                final_result.append(ner_result[entity_loc])
        
        
    #print(final_result)
    return final_result
   

def entity_consistency(ner_result,ori_text): #ner_result=[]
    
    final_result={}
    entity_loc_set=set()
    entity_type={} #{entity:{type1:num,type2:num}}

    for segs in ner_result:
        entity_loc_set.add(segs[0]+' '+segs[1])
        final_result['\t'.join(segs)]=[int(segs[0]),int(segs[1])]
        if len(segs[2])>1:
            if segs[2].isupper():#entity is all supper abbr
                if segs[2] not in entity_type.keys():
                    entity_type[segs[2]]={segs[-1]:1}
                else:
                    if segs[-1] in entity_type[segs[2]]:
                        entity_type[segs[2]][segs[-1]]+=1
                    else:
                        entity_type[segs[2]][segs[-1]]=1
            else: #not abbr
                if segs[2].lower() not in entity_type.keys():
                    entity_type[segs[2].lower()]={segs[-1]:1}
                else:
                    if segs[-1] in entity_type[segs[2].lower()]:
                        entity_type[segs[2].lower()][segs[-1]]+=1
                    else:
                        entity_type[segs[2].lower()][segs[-1]]=1
     

    # print(entity_type)
    # print('..........')
    entity_type_major={}
    for ele in entity_type.keys():
        entity_type_major[ele]=max(zip(entity_type[ele].values(), entity_type[ele].keys()))[1]
    # print(entity_type_major)
    
    
    #find miss entity
    for entity_text in entity_type_major.keys():

        if entity_text.isupper():#entity is all supper abbr
            new_text=ori_text
        else:
            new_text=ori_text.lower()
        ent_eid=0
        while new_text.find(entity_text,ent_eid)>=0:
            ent_sid=new_text.find(entity_text,ent_eid)
            ent_eid=ent_sid+len(entity_text)
            entity_loc=str(ent_sid)+' '+str(ent_eid)
            # print(abbr_sid,abbr_eid)
            if entity_loc not in entity_loc_set:
                if ent_sid>0 and ent_eid<len(new_text):
                    if new_text[ent_sid-1].isalnum()==False and new_text[ent_eid].isalnum()==False:
                        final_result[str(ent_sid)+'\t'+str(ent_eid)+'\t'+ori_text[ent_sid:ent_eid]+'\t'+entity_type_major[entity_text]]=[ent_sid,ent_eid]
                        entity_loc_set.add(entity_loc)
                elif ent_sid==0 and ent_eid<len(new_text):
                    if new_text[ent_eid].isalnum()==False:
                        final_result[str(ent_sid)+'\t'+str(ent_eid)+'\t'+ori_text[ent_sid:ent_eid]+'\t'+entity_type_major[entity_text]]=[ent_sid,ent_eid]
                        entity_loc_set.add(entity_loc)
                elif ent_sid>0 and ent_eid==len(new_text):
                    if new_text[ent_sid-1].isalnum()==False :
                        final_result[str(ent_sid)+'\t'+str(ent_eid)+'\t'+ori_text[ent_sid:ent_eid]+'\t'+entity_type_major[entity_text]]=[ent_sid,ent_eid]
                        entity_loc_set.add(entity_loc)
   
    if len(final_result)!=len(ner_result):#add new entity, sort , remover overloppling
        final_result=sorted(final_result.items(), key=lambda kv:(kv[1]), reverse=False)
        mention_list=[]
        for ele in final_result:
            mention_list.append(ele[0].split('\t'))
        final_ner_result=combine_overlap(mention_list)
    else:
        final_ner_result=ner_result
    return final_ner_result
      
def combine_overlap(mention_list):
   
    entity_list=[]
    if len(mention_list)>2:
        
        first_entity=mention_list[0]
        nest_list=[first_entity]
        max_eid=int(first_entity[1])
        for i in range(1,len(mention_list)):
            segs=mention_list[i]
            if int(segs[0])>= max_eid:
                if len(nest_list)==1:
                    entity_list.append(nest_list[0])
                    nest_list=[]
                    nest_list.append(segs)
                    if int(segs[1])>max_eid:
                        max_eid=int(segs[1])
                else:
                    tem=find_max_entity(nest_list)#find max entity
                    entity_list.append(tem)
                    nest_list=[]
                    nest_list.append(segs)
                    if int(segs[1])>max_eid:
                        max_eid=int(segs[1])
                    
            else:
                nest_list.append(segs)
                if int(segs[1])>max_eid:
                    max_eid=int(segs[1])
        if nest_list!=[]:
            if len(nest_list)==1:
                entity_list.append(nest_list[0])

            else:
                tem=find_max_entity(nest_list)#find max entity
                entity_list.append(tem)
    else:
        entity_list=mention_list
        
    return entity_list

def find_max_entity(nest_list):
    max_len=0
    max_entity=[]
    for i in range(0, len(nest_list)):
        length=int(nest_list[i][1])-int(nest_list[i][0])
        if length>max_len:
                max_len=length
                max_entity=nest_list[i]
    
    return max_entity   


           
            
if __name__ == '__main__':
   
    path='//panfs/pan1/bionlplab/luol2/PubTator3/example/post-out/'
    fin=open(path+'PubmedBERT-CRF-AIO_ALL.test_preds','r',encoding='utf-8')
    all_in=fin.read().strip().split('\n\n')
    fout=open(path+'PubmedBERT-CRF-AIO_ALL-post4.test_preds','w',encoding='utf-8')
    for doc in all_in:
        lines=doc.split('\n')
        pmid=lines[0].split('|t|')[0]
        ori_text=lines[0].split('|t|')[1]+' '+lines[1].split('|a|')[1]
        ner_result={}
        for i in range(2,len(lines)):
            seg=lines[i].split('\t')
            ner_result[seg[1]+' '+seg[2]]=seg[1:]
        # abbr recognition
        final_ner=postprocess_abbr(ner_result,ori_text)
        #entity consistence
        final_ner=entity_consistency(final_ner,ori_text)
        # final_result=sorted(final_ner.items(), key=lambda kv:(kv[1]), reverse=False)
        fout.write(lines[0]+'\n'+lines[1]+'\n')
        for ele in final_ner:
            fout.write(pmid+'\t'+'\t'.join(ele)+'\n')
        fout.write('\n')
    fout.close()

        # sys.exit()
    
    
