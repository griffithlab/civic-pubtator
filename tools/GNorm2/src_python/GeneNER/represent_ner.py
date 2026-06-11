# represent_ner.py
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 30 19:54:17 2021

@author: luol2

Input representation for the NER model.
"""

import os, sys
import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences
from transformers import AutoTokenizer


class Hugface_RepresentationLayer(object):
    
    def __init__(self, tokenizer_name_or_path, label_file, lowercase=True):
        """
        :param tokenizer_name_or_path: path or name of the BERT tokenizer
        :param label_file: path to label vocab (one label per line)
        :param lowercase: True if the model is uncased
        """
        # 1) Load BERT subword tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name_or_path,
            use_fast=True,
            do_lower_case=lowercase
        )

        # 2) Load label vocabulary
        self.label_2_index = {}
        self.index_2_label = {}
        self.load_label_vocab(label_file, self.label_2_index, self.index_2_label)
        self.label_table_size = len(self.label_2_index)  # e.g. number of NER tags

        # 3) Subword vocabulary size for embeddings
        self.subword_vocab_size = len(self.tokenizer)
        self.vocab_len = len(self.tokenizer)
    
    def load_label_vocab(self, fea_file, fea_index, index_2_label):
        """
        Each line in fea_file is one label, e.g. "O", "B-GENE", ...
        """
        with open(fea_file, 'r', encoding='utf-8') as fin:
            all_text = fin.read().strip().split('\n')
        
        for i, lbl in enumerate(all_text):
            fea_index[lbl] = i
            index_2_label[str(i)] = lbl

    def generate_label_list_B(self, ori_tokens, labels, word_index):
        """
        Example logic: the first subword gets B-Tag, subsequent subwords get I-Tag.
        Adjust as needed for your NER approach.
        """
        label_list = ['O'] * len(word_index)
        label_list_index = []
        old_new_token_map = []

        ori_i = 0
        i = 0
        while i < len(word_index):
            if word_index[i] is None:
                # No label
                label_list_index.append(self.label_2_index[label_list[i]])
                i += 1
            else:
                # The "first_index" = the original token index
                first_index = word_index[i]
                if first_index == ori_i:
                    old_new_token_map.append(i)
                    ori_i += 1

                # By default, the label is the same as the original token
                cur_label = labels[word_index[i]]
                label_list[i] = cur_label
                label_id = self.label_2_index.get(cur_label, 0)
                label_list_index.append(label_id)
                i += 1

                # Convert subsequent subwords for the same original token to I-Tag
                while i < len(word_index) and word_index[i] == first_index:
                    if cur_label.startswith("B-"):
                        i_label = "I-" + cur_label[2:]
                        label_id = self.label_2_index.get(i_label, 0)
                    else:
                        i_label = cur_label
                        label_id = self.label_2_index.get(i_label, 0)
                    label_list[i] = i_label
                    label_list_index.append(label_id)
                    i += 1

        bert_text_label=[]
        #print(len(old_new_token_map))
        for i in range(0,len(ori_tokens)):
            if i<len(old_new_token_map):
                bert_text_label.append([ori_tokens[i],labels[i],old_new_token_map[i]])
            else: # after token > max len
                break

        return label_list_index, bert_text_label

    def load_data_hugface(self, instances, word_max_len=100, label_type='softmax'):
        """
        Convert raw token sequences + NER labels into BERT inputs plus subword-level labels.
        :param instances: list of sentences, each sentence is [(word, label), (word, label), ...]
        """
        x_index = []
        x_seg = []
        x_mask = []
        y_list = []
        bert_text_labels = []

        max_len = 0
        over_num = 0
        ave_len = 0
        maxT = word_max_len

        for sentence in instances:
            sentence_text_list = []
            label_list = []
            for (word, lab) in sentence:
                sentence_text_list.append(word)
                label_list.append(lab)

            # Tokenize with is_split_into_words=True
            token_result = self.tokenizer(
                sentence_text_list,
                max_length=word_max_len,
                truncation=True,
                is_split_into_words=True
            )
            bert_tokens = self.tokenizer.convert_ids_to_tokens(token_result['input_ids'])
            word_index = token_result.word_ids(batch_index=0)

            ave_len += len(bert_tokens)
            if len(sentence_text_list) > max_len:
                max_len = len(sentence_text_list)
            if len(bert_tokens) == maxT:
                over_num += 1

            x_index.append(token_result['input_ids'])
            x_seg.append(token_result['token_type_ids'])
            x_mask.append(token_result['attention_mask'])

            # Convert NER labels to subword-level
            label_list_index, subword_label_info = self.generate_label_list_B(
                sentence_text_list,
                label_list,
                word_index
            )
            y_list.append(label_list_index)
            bert_text_labels.append(subword_label_info)

        # Pad sequences
        x1_np = pad_sequences(x_index, maxlen=word_max_len, value=0, padding='post', truncating='post')
        x2_np = pad_sequences(x_seg, maxlen=word_max_len, value=0, padding='post', truncating='post')
        x3_np = pad_sequences(x_mask, maxlen=word_max_len, value=0, padding='post', truncating='post')
        y_np = pad_sequences(y_list, maxlen=word_max_len, value=0, padding='post', truncating='post')

        # If label_type='softmax', expand dims for training
        if label_type == 'softmax':
            y_np = np.expand_dims(y_np, axis=2)
        
        #print ("y_np")
        #print (y_np)
        #print ("bert_text_labels")
        #print (bert_text_labels)
        return [x1_np, x2_np, x3_np], y_np, bert_text_labels


if __name__ == '__main__':
    pass
