# represent_sa.py
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 30 19:54:17 2021

@author: luol2

Input representation for species assignment model.
"""

import os, sys
import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences
from transformers import AutoTokenizer

class Hugface_RepresentationLayer(object):
    
    def __init__(self, tokenizer_name_or_path, label_file, lowercase=True):
        """
        :param tokenizer_name_or_path: path or name of the model's tokenizer
        :param label_file: path to a file of classification labels (one per line)
        :param lowercase: whether to lowercase text (for certain BERT variants)
        """
        self.model_type = 'bert'
        
        # 1) Load subword tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_name_or_path,
            use_fast=True,
            do_lower_case=lowercase
        )
        
        # (Optional) Add custom tokens for argument tags, if needed
        # If you do NOT want these tokens, feel free to comment them out.
        #self.tokenizer.add_tokens([
        #    "arg1s","arg1e",
        #    "gene1s","gene1e",
        #    "species1s","species1e"
        #])

        # 2) Load classification labels
        self.label_2_index = {}
        self.index_2_label = {}
        self.load_label_vocab(label_file, self.label_2_index, self.index_2_label)
        self.label_table_size = len(self.label_2_index)  # e.g. 2 for binary, 5 for multi-class, etc.
        
        # 3) Subword vocabulary size for BERT embeddings
        self.subword_vocab_size = len(self.tokenizer)
        # (This is what you'd pass to self.bert.resize_token_embeddings(...) if you have a custom extended subword vocab.)
    
    def load_label_vocab(self, fea_file, fea_index, index_2_label):
        """
        Each line in fea_file is one label, e.g. "O", "B-ARG2", etc.
        """
        with open(fea_file, 'r', encoding='utf-8') as fin:
            all_text = fin.read().strip().split('\n')
        
        for i, label in enumerate(all_text):
            fea_index[label] = i
            index_2_label[str(i)] = label

    def generate_label_list(self, bert_tokens, labels, word_index):
        """
        Example logic for aligning subword tokens with label indices.
        This is a simplified approach. The details may vary in your usage.
        """
        label_list = ['O'] * len(word_index)
        if len(word_index) != len(bert_tokens):
            print('index != tokens', word_index, bert_tokens)
            sys.exit()
        
        for i in range(len(word_index)):
            if word_index[i] is not None:
                label_list[i] = labels[word_index[i]]

        label_list_index = []
        bert_text_label = []
        for i, tok in enumerate(bert_tokens):
            # Convert label to index
            label_id = self.label_2_index.get(label_list[i], 0)
            label_list_index.append(label_id)
            bert_text_label.append([tok, label_list[i]])
        return label_list_index, bert_text_label

    def load_data_hugface(self, instances, labels=None, word_max_len=100, label_type='softmax'):
        """
        Convert raw tokenized text + label sequences into BERT inputs (input_ids, token_type_ids, attention_mask)
        plus label arrays.

        :param instances: A list of sentences, each sentence is a list of (word, label) pairs
        :param labels: Not strictly needed if your label is in each (word, label) pair
        :param word_max_len: The max sequence length
        :param label_type: 'softmax' or other types
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

            # 1) Tokenize
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
            if len(bert_tokens) >= maxT:
                over_num += 1

            x_index.append(token_result['input_ids'])
            if self.model_type in {"gpt2", "roberta"}:
                x_seg.append([0]*len(token_result['input_ids']))
            else:
                x_seg.append(token_result['token_type_ids'])
            x_mask.append(token_result['attention_mask'])

            # 2) Convert labels to subword-level
            label_ids, bert_text_label = self.generate_label_list(bert_tokens, label_list, word_index)
            y_list.append(label_ids)
            bert_text_labels.append(bert_text_label)

        # 3) Pad all sequences to max length
        x1_np = pad_sequences(x_index, word_max_len, value=0, padding='post', truncating='post')
        x2_np = pad_sequences(x_seg, word_max_len, value=0, padding='post', truncating='post')
        x3_np = pad_sequences(x_mask, word_max_len, value=0, padding='post', truncating='post')
        y_np = pad_sequences(y_list, word_max_len, value=0, padding='post', truncating='post')

        # 4) If label_type='softmax', expand dims for BERT token classification
        if label_type == 'softmax':
            y_np = np.expand_dims(y_np, axis=2)
        elif label_type == 'crf':
            # If you were using a CRF, you'd handle differently
            pass

        return [x1_np, x2_np, x3_np], y_np, bert_text_labels


if __name__ == '__main__':
    pass
