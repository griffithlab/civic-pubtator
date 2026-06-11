# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 09:08:09 2021

@author: luol2
"""
import sys
import tensorflow as tf
from transformers import TFAutoModel
from tensorflow.keras.layers import Input, TimeDistributed, Dropout, Dense
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

# Import your custom class
# from my_custom_bert import TFBertWrapper
from src_python.GeneNER.represent_ner import Hugface_RepresentationLayer

class LRSchedule_LINEAR(tf.keras.optimizers.schedules.LearningRateSchedule):
    def __init__(self, init_lr=5e-5, init_warmup_lr=0.0,
                 final_lr=5e-7, warmup_steps=0, decay_steps=0):
        super().__init__()
        self.init_lr = init_lr
        self.init_warmup_lr = init_warmup_lr
        self.final_lr = final_lr
        self.warmup_steps = warmup_steps
        self.decay_steps = decay_steps

    def __call__(self, step):
        step = tf.cast(step, tf.float32)  # Ensure step is float32

        # Linear warm-up
        if self.warmup_steps > 0:
            warmup_lr = (self.init_lr - self.init_warmup_lr) / self.warmup_steps * step + self.init_warmup_lr
        else:
            warmup_lr = tf.constant(1000.0, dtype=tf.float32)  # Ensuring type consistency

        # Linear decay
        decay_lr = tf.math.maximum(
            self.final_lr,
            self.init_lr - (step - self.warmup_steps) / self.decay_steps * (self.init_lr - self.final_lr)
        )

        return tf.math.minimum(warmup_lr, decay_lr)

##################################
# Custom BERT wrapper from above #
##################################
class TFBertWrapper(tf.keras.layers.Layer):
    def __init__(self, model_name_or_path, vocab_len=None, from_pt=True, **kwargs):
        super().__init__(**kwargs)
        self.bert = TFAutoModel.from_pretrained(model_name_or_path, from_pt=from_pt)
        if vocab_len is not None:
            self.bert.resize_token_embeddings(self.rep.subword_vocab_size)

        self._trainable_weights = self.bert.trainable_variables
        self._non_trainable_weights = self.bert.non_trainable_variables

        #
        # The most important step:
        #   Pass the weights manually from bert to encoder. However, the Gradient can't be loaded.
        #
        #for w in self._trainable_weights:
        #    clean_name = w.name.replace("/", "_").replace(":", "_")
        #    self.add_variable(name=clean_name, shape=w.shape, trainable=True, initializer=tf.keras.initializers.Constant(w.numpy()))
        #for w in self._non_trainable_weights:
        #    clean_name = w.name.replace("/", "_").replace(":", "_")
        #    self.add_variable(name=clean_name, shape=w.shape, trainable=False, initializer=tf.keras.initializers.Constant(w.numpy()))

        # Debugging: Print first weight values (NOT just shapes)
        #print("-----------------------> Checking first few parameter values in BERT")
        #for var in self.bert.trainable_variables[:5]:  # Print first 5 weight matrices
        #    print(f"Name: {var.name}, Shape: {var.shape}")
        #    print(f"Values (first 5 elements): {var.numpy().flatten()[:5]}")
        
        self.trainable = True  # Ensure BERT is trainable

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
# Actual NER Model Class         #
##################################
class HUGFACE_NER():
    def __init__(self, model_files):
        self.model_type = 'HUGFACE'
        self.maxlen = 256
        self.checkpoint_path = model_files['checkpoint_path']
        self.label_file = model_files['labelfile']
        self.lowercase = model_files['lowercase']
        self.from_pt = model_files['from_pt']

        # Representation (tokenizer, label vocab, etc.)
        self.rep = Hugface_RepresentationLayer(
            self.checkpoint_path,
            self.label_file,
            lowercase=self.lowercase
        )

    def build_encoder(self):
        #print('...vocab len:', self.rep.vocab_len)
        #print('...checkpoint_path:', self.checkpoint_path)
        # 1) Create our BERT wrapper
        self.bert_wrapper = TFBertWrapper(
            model_name_or_path=self.checkpoint_path,
            vocab_len=None,  # or self.rep.vocab_len if you have custom tokens
            from_pt=self.from_pt
        )

        self.bert_wrapper.bert.summary()
        #print("Encoder Weights:", bert_model.trainable_weights)  

        # 2) Define Keras Input layers
        x1_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='input_ids')
        x2_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='token_type_ids')
        x3_in = Input(shape=(self.maxlen,), dtype=tf.int32, name='attention_mask')

        dummy_input_ids = tf.zeros((1, self.maxlen), dtype=tf.int32)
        dummy_token_type_ids = tf.zeros((1, self.maxlen), dtype=tf.int32)
        dummy_attention_mask = tf.zeros((1, self.maxlen), dtype=tf.int32)
        _ = self.bert_wrapper((dummy_input_ids, dummy_token_type_ids, dummy_attention_mask))  # Run once to initialize weights

        #print(f"-----------------------> Checking trainable variables in self.bert_wrapper (before encoder model): {len(self.bert_wrapper.bert.trainable_weights)}")
        #for var in self.bert_wrapper.bert.trainable_variables[:5]:  # Print first 5 for debugging
        #    print(f"Name: {var.name}, Shape: {var.shape}, Values (first 5 elements): {var.numpy().flatten()[:5]}")
        #print(f"-----------------------> Checking non_trainable variables in self.bert_wrapper (before encoder model): {len(self.bert_wrapper.bert.non_trainable_weights)}")
        #for var in self.bert_wrapper.bert.non_trainable_variables[:5]:  # Print first 5 for debugging
        #    print(f"Name: {var.name}, Shape: {var.shape}, Values (first 5 elements): {var.numpy().flatten()[:5]}")

        # 3) Pass them as a tuple to the wrapper
        x = self.bert_wrapper((x1_in, x2_in, x3_in))
        
        # Ensure `TFBertWrapper` is correctly included in Keras
        #self.bert_wrapper.build((None, self.maxlen))
        self.bert_wrapper.trainable = True  # Explicitly mark trainable
        
        # Define the encoder model correctly
        self.encoder = Model(inputs=[x1_in, x2_in, x3_in], outputs=x, name='hugface_encoder')
        self.encoder.trainable = True
        
        #print(f"-----------------------> Layers in self.encoder:")
        #for layer in self.encoder.layers:
        #    print(layer.name, type(layer))

        #print(f"-----------------------> Trainable weights in encoder: {len(self.encoder.trainable_weights)}")
        #for var in self.encoder.trainable_weights[:5]:  # Print first 5 weights
        #    print(f"Name: {var.name}, Shape: {var.shape}, Values (first 5 elements): {var.numpy().flatten()[:5]}")
            
        #print(f"-----------------------> Non-Trainable weights in encoder: {len(self.encoder.non_trainable_weights)}")
        #for var in self.encoder.non_trainable_weights[:5]:  # Print first 5 weights
        #    print(f"Name: {var.name}, Shape: {var.shape}, Values (first 5 elements): {var.numpy().flatten()[:5]}")
        
        # Force Keras to register weights
        self.encoder.compile(optimizer='adam', loss='mse')  
        #print("-----------------------> self.encoder.summary()")
        self.encoder.summary()

        #sys.exit(0)

    def build_softmax_decoder(self):
        # 1) Re-declare the input layers
        x1_in = Input(shape=(self.maxlen,), dtype=tf.int32)
        x2_in = Input(shape=(self.maxlen,), dtype=tf.int32)
        x3_in = Input(shape=(self.maxlen,), dtype=tf.int32)

        # 2) Pass them through the encoder
        features = self.encoder([x1_in, x2_in, x3_in])

        # 3) Additional dense layers for NER
        features = TimeDistributed(Dense(128, activation='relu'), name='dense2')(features)
        features = Dropout(0.1)(features)

        # 4) Output softmax
        output = TimeDistributed(Dense(self.rep.label_table_size, activation='softmax'), name='softmax')(features)
        self.model = Model(inputs=[x1_in, x2_in, x3_in], outputs=output, name="hugface_softmax")

        # 5) Compile
        lr_schedule = LRSchedule_LINEAR(
            init_lr=1e-5,
            init_warmup_lr=1e-7,
            final_lr=5e-6,
            warmup_steps=0,
            decay_steps=1000
        )
        opt = Adam(learning_rate=lr_schedule)
        self.model.compile(
            optimizer=opt,
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        self.model.summary()

    def load_model(self, model_file):
        self.model.load_weights(model_file)
        self.model.summary()
        print('load HUGFACE model done!')
