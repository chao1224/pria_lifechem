import argparse
import pandas as pd
import csv
import numpy as np
import json
import keras
import sys
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.layers.normalization import BatchNormalization
from keras.optimizers import SGD, Adam
from sklearn.cross_validation import StratifiedShuffleSplit

# Add path from parent folder
sys.path.insert(0, '..')
# Add path from current folder
sys.path.insert(0, '.')
from function import *
from evaluation import *

class single_classification:
    def __init__(self, conf):

        self.conf = conf
        self.input_layer_dimension = 1024
        self.output_layer_dimension = 1

        self.early_stopping_patience = conf['fitting']['early_stopping']['patience']
        self.early_stopping_option = conf['fitting']['early_stopping']['option']
        self.early_stopping_option = 'auc'

        self.fit_nb_epoch = conf['fitting']['nb_epoch']
        self.fit_batch_size = conf['fitting']['batch_size']
        self.fit_verbose = conf['fitting']['verbose']

        self.compile_loss = conf['compile']['loss']
        self.compile_optimizer_option = conf['compile']['optimizer']['option']
        if self.compile_optimizer_option == 'sgd':
            sgd_lr = conf['compile']['optimizer']['sgd']['lr']
            sgd_momentum = conf['compile']['optimizer']['sgd']['momentum']
            sgd_decay = conf['compile']['optimizer']['sgd']['decay']
            sgd_nestrov = conf['compile']['optimizer']['sgd']['nestrov']
            self.compile_optimizer = SGD(lr=sgd_lr, momentum=sgd_momentum, decay=sgd_decay, nesterov=sgd_nestrov)
        else:
            adam_lr = conf['compile']['optimizer']['adam']['lr']
            adam_beta_1 = conf['compile']['optimizer']['adam']['beta_1']
            adam_beta_2 = conf['compile']['optimizer']['adam']['beta_2']
            adam_epsilon = conf['compile']['optimizer']['adam']['epsilon']
            self.compile_optimizer = Adam(lr=adam_lr, beta_1=adam_beta_1, beta_2=adam_beta_2, epsilon=adam_epsilon)

        self.batch_is_use = conf['batch']['is_use']
        if self.batch_is_use:
            batch_normalizer_epsilon = conf['batch']['epsilon']
            batch_normalizer_mode = conf['batch']['mode']
            batch_normalizer_axis = conf['batch']['axis']
            batch_normalizer_momentum = conf['batch']['momentum']
            batch_normalizer_weights = conf['batch']['weights']
            batch_normalizer_beta_init = conf['batch']['beta_init']
            batch_normalizer_gamma_init = conf['batch']['gamma_init']
            self.batch_normalizer = BatchNormalization(epsilon=batch_normalizer_epsilon,
                                                       mode=batch_normalizer_mode,
                                                       axis=batch_normalizer_axis,
                                                       momentum=batch_normalizer_momentum,
                                                       weights=batch_normalizer_weights,
                                                       beta_init=batch_normalizer_beta_init,
                                                       gamma_init=batch_normalizer_gamma_init)
        self.EF_ratio_list = conf['enrichment_factor']['ratio_list']

        return

    def setup_model(self):
        model = Sequential()
        if self.batch_is_use:
            batch_normalizer = self.batch_normalizer
        layers = self.conf['layers']
        layer_number = len(layers)
        for i in range(layer_number):
            init = layers[i]['init']
            activation = layers[i]['activation']
            if i == 0:
                hidden_units = int(layers[i]['hidden_units'])
                dropout = float(layers[i]['dropout'])
                model.add(Dense(hidden_units, input_dim=self.input_layer_dimension, init=init, activation=activation))
                model.add(Dropout(dropout))
            elif i == layer_number - 1:
                if self.batch_is_use:
                    model.add(self.batch_normalizer)
                model.add(Dense(self.output_layer_dimension, init=init, activation=activation))
            else:
                hidden_units = int(layers[i]['hidden_units'])
                dropout = float(layers[i]['dropout'])
                model.add(Dense(hidden_units, init=init, activation=activation))
                model.add(Dropout(dropout))

        return model

    def train_and_predict(self,
                          X_train, y_train,
                          X_val, y_val,
                          X_test, y_test,
                          PMTNN_weight_file):
        model = self.setup_model()
        if self.early_stopping_option == 'auc':
            early_stopping = KeckCallBackOnAUC(X_train, y_train, X_val, y_val, patience=self.early_stopping_patience)
            callbacks = [early_stopping]
        elif self.early_stopping_option == 'precision':
            early_stopping = KeckCallBackOnPrecision(X_train, y_train, X_val, y_val,
                                                     patience=self.early_stopping_patience)
            callbacks = [early_stopping]
        else:
            callbacks = []

        model.compile(loss=self.compile_loss, optimizer=self.compile_optimizer)
        model.fit(X_train, y_train,
                  nb_epoch=self.fit_nb_epoch,
                  batch_size=self.fit_batch_size,
                  verbose=self.fit_verbose,
                  shuffle=True,
                  callbacks=callbacks)
        model.save_weights(PMTNN_weight_file)

        if self.early_stopping_option == 'auc' or self.early_stopping_option == 'precision':
            model = early_stopping.get_best_model()
        y_pred_on_train = model.predict(X_train)
        y_pred_on_val = model.predict(X_val)
        y_pred_on_test = model.predict(X_test)

        print
        print('train precision: {}'.format(precision_auc_single(y_train, y_pred_on_train)))
        print('train roc: {}'.format(roc_auc_single(y_train, y_pred_on_train)))
        print('train bedroc: {}'.format(bedroc_auc_single(y_train, y_pred_on_train)))
        print
        print('validation precision: {}'.format(precision_auc_single(y_val, y_pred_on_val)))
        print('validation roc: {}'.format(roc_auc_single(y_val, y_pred_on_val)))
        print('validation bedroc: {}'.format(bedroc_auc_single(y_val, y_pred_on_val)))
        print
        print('test precision: {}'.format(precision_auc_single(y_test, y_pred_on_test)))
        print('test roc: {}'.format(roc_auc_single(y_test, y_pred_on_test)))
        print('test bedroc: {}'.format(bedroc_auc_single(y_test, y_pred_on_test)))
        print

        for EF_ratio in self.EF_ratio_list:
            n_actives, ef, ef_max = enrichment_factor_single(y_test, y_pred_on_test, EF_ratio)
            print('ratio: {}, EF: {},\tactive: {}'.format(EF_ratio, ef, n_actives))

        return

    def predict_with_existing(self,
                              X_train, y_train,
                              X_val, y_val,
                              X_test, y_test,
                              PMTNN_weight_file):
        model = setup_model()
        model.load_weights(PMTNN_weight_file)

        y_pred_on_train = model.predict(X_train)
        y_pred_on_val = model.predict(X_val)
        y_pred_on_test = model.predict(X_test)


        print
        print('train precision: {}'.format(precision_auc_single(y_train, y_pred_on_train)))
        print('train roc: {}'.format(roc_auc_single(y_train, y_pred_on_train)))
        print('train bedroc: {}'.format(bedroc_auc_single(y_train, y_pred_on_train)))
        print
        print('validation precision: {}'.format(precision_auc_single(y_val, y_pred_on_val)))
        print('validation roc: {}'.format(roc_auc_single(y_val, y_pred_on_val)))
        print('validation bedroc: {}'.format(bedroc_auc_single(y_val, y_pred_on_val)))
        print
        print('test precision: {}'.format(precision_auc_single(y_test, y_pred_on_test)))
        print('test roc: {}'.format(roc_auc_single(y_test, y_pred_on_test)))
        print('test bedroc: {}'.format(bedroc_auc_single(y_test, y_pred_on_test)))
        print

        return

    def get_EF_score_with_existing_model(self,
                                         X_test, y_test,
                                         file_path, EF_ratio):
        model = setup_model()
        model.load_weights(file_path)
        y_pred_on_test = model.predict(X_test)
        n_actives, ef, ef_max = enrichment_factor_single(y_test, y_pred_on_test, EF_ratio)
        print('test precision: {}'.format(precision_auc_single(y_test, y_pred_on_test)))
        print('test auc: {}'.format(roc_auc_single(y_test, y_pred_on_test)))
        print('EF: {},\tactive: {}'.format(ef, n_actives))

        return


# define custom classes
# following class is used for keras to compute the AUC each epoch
# and do early stoppping based on that
class KeckCallBackOnAUC(keras.callbacks.Callback):
    def __init__(self, X_train, y_train, X_val, y_val,
                 patience=0,
                 file_path='best_model.weights'):
        super(keras.callbacks.Callback, self).__init__()
        self.curr_roc = 0
        self.best_roc = 0
        self.counter = 0
        self.patience = patience
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.file_path = file_path

    def on_train_begin(self, logs={}):
        self.nb_epoch = self.params['nb_epoch']
        self.curr_roc = roc_auc_single(self.y_val, self.model.predict(self.X_val))
        self.best_roc = self.curr_roc

    def on_epoch_end(self, epoch, logs={}):
        self.curr_roc = roc_auc_single(self.y_val, self.model.predict(self.X_val))
        if self.curr_roc < self.best_roc:
            if self.counter >= self.patience:
                self.model.stop_training = True
            else:
                self.counter += 1
        else:
            self.counter = 0
            self.best_roc = self.curr_roc
            self.model.save_weights(self.file_path)
            
        train_roc = roc_auc_single(self.y_train, self.model.predict(self.X_train))
        train_bedroc = bedroc_auc_single(self.y_train, self.model.predict(self.X_train))
        train_pr = precision_auc_single(self.y_train, self.model.predict(self.X_train))
        curr_bedroc = bedroc_auc_single(self.y_val, self.model.predict(self.X_val))
        curr_pr = precision_auc_single(self.y_val, self.model.predict(self.X_val))
        print('Epoch %d/%d' % (epoch + 1, self.nb_epoch))
        print 'Train\tAUC[ROC]: %.6f\tAUC[BEDROC]: %.6f\tAUC[PR]: %.6f' % \
              (train_roc, train_bedroc, train_pr)
        print 'Val\tAUC[ROC]: %.6f\tAUC[BEDROC]: %.6f\tAUC[PR]: %.6f' % \
              (self.curr_roc, curr_bedroc, curr_pr)
        print

    def get_best_model(self):
        self.model.load_weights(self.file_path)
        return self.model

    def get_best_auc(self):
        return self.best_roc


# define custom classes
# following class is used for keras to compute the precision each epoch
# and do early stoppping based on that
class KeckCallBackOnPrecision(keras.callbacks.Callback):
    def __init__(self, X_train, y_train, X_val, y_val,
                 patience=0,
                 file_path='best_model.weights'):
        super(keras.callbacks.Callback, self).__init__()
        self.curr_pr = 0
        self.best_pr = 0
        self.counter = 0
        self.patience = patience
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.file_path = file_path

    def on_train_begin(self, logs={}):
        self.nb_epoch = self.params['nb_epoch']
        self.curr_pr = precision_auc_single(self.y_val, self.model.predict(self.X_val))
        self.best_pr = self.curr_pr

    def on_epoch_end(self, epoch, logs={}):
        self.curr_pr = precision_auc_single(self.y_val, self.model.predict(self.X_val))
        if self.curr_pr < self.best_pr:
            if self.counter >= self.patience:
                self.model.stop_training = True
            else:
                self.counter += 1
        else:
            self.counter = 0
            self.best_pr = self.curr_pr
            self.model.save_weights(self.file_path)

        train_roc = roc_auc_single(self.y_train, self.model.predict(self.X_train))
        train_bedroc = bedroc_auc_single(self.y_train, self.model.predict(self.X_train))
        train_pr = precision_auc_single(self.y_train, self.model.predict(self.X_train))
        curr_roc = roc_auc_single(self.y_val, self.model.predict(self.X_val))
        curr_bedroc = bedroc_auc_single(self.y_val, self.model.predict(self.X_val))
        print('Epoch %d/%d' % (epoch + 1, self.nb_epoch))
        print 'Train\tAUC[ROC]: %.6f\tAUC[BEDROC]: %.6f\tAUC[PR]: %.6f' %\
              (train_roc, train_bedroc, train_pr)
        print 'Val\tAUC[ROC]: %.6f\tAUC[BEDROC]: %.6f\tAUC[PR]: %.6f' %\
              (curr_roc, curr_bedroc, self.curr_pr)
        print

    def get_best_model(self):
        self.model.load_weights(self.file_path)
        return self.model

    def get_best_auc(self):
        return self.best_pr


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--config_json_file', action="store", dest="config_json_file", required=True)
    parser.add_argument('--PMTNN_weight_file', action="store", dest="PMTNN_weight_file", required=True)
    parser.add_argument('--config_csv_file', action="store", dest="config_csv_file", required=True)
    given_args = parser.parse_args()
    config_json_file = given_args.config_json_file
    PMTNN_weight_file = given_args.PMTNN_weight_file
    config_csv_file = given_args.config_csv_file

    print sys.path

    # specify dataset
    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('file_{}.csv'.format(i))

    # merge training and test dataset
    dtype_list = {'Molecule': np.str,
                  'SMILES': np.str,
                  'Fingerprints': np.str,
                  'Keck_Pria_AS_Retest': np.int64,
                  'Keck_Pria_FP_data': np.int64,
                  'Keck_Pria_Continuous': np.float64,
                  'Keck_RMI_cdd': np.float64}
    output_file_list = [directory + f_ for f_ in file_list]
    print output_file_list[:4]
    train_pd = read_merged_data(output_file_list[0:1])
    print output_file_list[4]
    test_pd = read_merged_data([output_file_list[4]])

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=['Keck_Pria_AS_Retest'])
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=['Keck_Pria_AS_Retest'])
    cross_validation_split = StratifiedShuffleSplit(y_train, 1, test_size=0.15, random_state=1)
    for t_index, val_index in cross_validation_split:
        X_t, X_val = X_train[t_index], X_train[val_index]
        y_t, y_val = y_train[t_index], y_train[val_index]
    print 'done data preparation'

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    task = single_classification(conf=conf)
    task.train_and_predict(X_t, y_t, X_val, y_val, X_test, y_test, PMTNN_weight_file)
    task.store_data(transform_json_to_csv(config_json_file), config_csv_file)