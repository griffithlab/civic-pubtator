# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 09:08:09 2021

@author: luol2

Model Architecture

"""
import tensorflow as tf
from tensorflow.keras.layers import Input, TimeDistributed, Dropout, Dense
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from transformers import TFAutoModel

from src_python.SpeAss.represent_sa import Hugface_RepresentationLayer

##################################
# Custom BERT wrapper from above #
##################################
class TFBertWrapper(tf.keras.layers.Layer):
    def __init__(self, model_name_or_path, vocab_len=None, from_pt=True, **kwargs):
        super().__init__(**kwargs)
        self.bert = TFAutoModel.from_pretrained(model_name_or_path, from_pt=from_pt)
        if vocab_len is not None:
            self.bert.resize_token_embeddings(self.rep.subword_vocab_size)

    def call(self, inputs, training=False):
        input_ids, token_type_ids, attention_mask = inputs
        input_ids = tf.cast(input_ids, tf.int32)
        token_type_ids = tf.cast(token_type_ids, tf.int32)
        attention_mask = tf.cast(attention_mask, tf.int32)

        outputs = self.bert(
            input_ids=input_ids,
            token_type_ids=token_type_ids,
            attention_mask=attention_mask,
            training=training
        )
        return outputs.last_hidden_state

##################################
# SA Model Class
##################################
class HUGFACE_NER():
    def __init__(self, model_files):
        self.model_type = 'HUGFACE'
        self.maxlen = 512
        self.checkpoint_path = model_files['checkpoint_path']
        self.label_file = model_files['labelfile']
        self.lowercase = model_files['lowercase']
        self.from_pt = model_files['from_pt']
        self.rep = Hugface_RepresentationLayer(self.checkpoint_path, self.label_file, lowercase=self.lowercase)

    def build_encoder(self):
        #print('...vocab len:', self.rep.vocab_len)
        self.bert_wrapper = TFBertWrapper(
            model_name_or_path=self.checkpoint_path,
            vocab_len=None,#self.rep.vocab_len,  # or None if no extra tokens
            from_pt=self.from_pt
        )
        x1_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='input_ids')
        x2_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='token_type_ids')
        x3_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='attention_mask')

        x = self.bert_wrapper((x1_in, x2_in, x3_in))
        self.encoder = Model(inputs=[x1_in, x2_in, x3_in], outputs=x, name='hugface_encoder')
        self.encoder.summary()

    def build_softmax_decoder(self):
        x1_in = Input(shape=(self.maxlen,), dtype=tf.int32)
        x2_in = Input(shape=(self.maxlen,), dtype=tf.int32)
        x3_in = Input(shape=(self.maxlen,), dtype=tf.int32)

        features = self.encoder([x1_in, x2_in, x3_in])
        features = Dropout(0.1)(features)

        # TimeDistributed final layer
        output = TimeDistributed(Dense(self.rep.label_table_size, activation='softmax'), name='softmax')(features)

        self.model = Model(inputs=[x1_in, x2_in, x3_in], outputs=output, name="hugface_softmax")

        opt = Adam(learning_rate=5e-6)
        self.model.compile(
            optimizer=opt,
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy'],
        )
        self.model.summary()

    def load_model(self, model_file):
        self.model.load_weights(model_file)
        self.model.summary()
        print('load HUGFACE model done!')
