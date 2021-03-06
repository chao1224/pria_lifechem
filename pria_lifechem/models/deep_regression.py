import argparse
import pandas as pd
import csv
import numpy as np
import json
import keras
import sys
from itertools import groupby
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.layers.normalization import BatchNormalization
from keras.optimizers import SGD, Adam
from sklearn.cross_validation import StratifiedShuffleSplit
from pria_lifechem.function import read_merged_data, extract_feature_and_label, \
    reshape_data_into_2_dim, store_data, transform_json_to_csv
from pria_lifechem.evaluation import roc_auc_single, bedroc_auc_single, \
    precision_auc_single, enrichment_factor_single


def get_sample_weight(task, y_data):
    if task.weight_schema == 'no_weight':
        sw = [1.0 for t in y_data]
    elif task.weight_schema == 'weighted_sample':
        values = set(map(lambda x: int(x), y_data))
        values = dict.fromkeys(values, 0)

        data = sorted(y_data)
        for k,g in groupby(data, key=lambda x: int(x[0])):
            temp_group = [t[0] for t in g]
            values[k] = len(temp_group)
        sum_ = reduce(lambda x, y: x + y, values.values())
        sw = map(lambda x: 1.0 * sum_ / values[int(x[0])], y_data)
    else:
        raise ValueError('Weight schema not included. Should be among [{}, {}].'.
                         format('no_weight', 'weighted_sample'))
    sw = np.array(sw)
    # Only accept 1D sample weights
    # sw = reshape_data_into_2_dim(sw)
    return sw


class SingleRegression:
    def __init__(self, conf):
        self.conf = conf
        self.input_layer_dimension = 1024
        self.output_layer_dimension = 1

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
        self.weight_schema = conf['class_weight_option']

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
                          X_train, y_train_regression, y_train_classification,
                          X_val, y_val_regression, y_val_classification,
                          X_test, y_test_regression, y_test_classification,
                          PMTNN_weight_file):
        model = self.setup_model()
        sw = get_sample_weight(self, y_train_regression)
        print 'Sample Weight\t', sw

        model.compile(loss=self.compile_loss, optimizer=self.compile_optimizer)
        model.fit(x=X_train, y=y_train_regression,
                  nb_epoch=self.fit_nb_epoch,
                  batch_size=self.fit_batch_size,
                  verbose=self.fit_verbose,
                  sample_weight=sw,
                  validation_data=[X_val, y_val_regression],
                  shuffle=True)
        model.save_weights(PMTNN_weight_file)

        y_pred_on_train = model.predict(X_train)
        y_pred_on_val = model.predict(X_val)
        if X_test is not None:
            y_pred_on_test = model.predict(X_test)

        print
        print('train precision: {}'.format(precision_auc_single(y_train_classification, y_pred_on_train)))
        print('train roc: {}'.format(roc_auc_single(y_train_classification, y_pred_on_train)))
        print('train bedroc: {}'.format(bedroc_auc_single(y_train_classification, y_pred_on_train)))
        print
        print('validation precision: {}'.format(precision_auc_single(y_val_classification, y_pred_on_val)))
        print('validation roc: {}'.format(roc_auc_single(y_val_classification, y_pred_on_val)))
        print('validation bedroc: {}'.format(bedroc_auc_single(y_val_classification, y_pred_on_val)))
        print
        if X_test is not None:
            print('test precision: {}'.format(precision_auc_single(y_test_classification, y_pred_on_test)))
            print('test roc: {}'.format(roc_auc_single(y_test_classification, y_pred_on_test)))
            print('test bedroc: {}'.format(bedroc_auc_single(y_test_classification, y_pred_on_test)))
            print

        if X_test is not None:
            for EF_ratio in self.EF_ratio_list:
                n_actives, ef, ef_max = enrichment_factor_single(y_test_classification, y_pred_on_test, EF_ratio)
                nef = ef / ef_max
                print('ratio: {}, EF: {},\tactive: {}'.format(EF_ratio, ef, n_actives))
                print('ratio: {}, NEF: {}'.format(EF_ratio, nef))

        return

    def predict_with_existing(self,
                              X_train, y_train_regression, y_train_classification,
                              X_val, y_val_regression, y_val_classification,
                              X_test, y_test_regression, y_test_classification,
                              PMTNN_weight_file):
        model = self.setup_model()
        model.load_weights(PMTNN_weight_file)

        y_pred_on_train = model.predict(X_train)
        y_pred_on_val = model.predict(X_val)
        if X_test is not None:
            y_pred_on_test = model.predict(X_test)

        print
        print('train precision: {}'.format(precision_auc_single(y_train_classification, y_pred_on_train)))
        print('train roc: {}'.format(roc_auc_single(y_train_classification, y_pred_on_train)))
        print('train bedroc: {}'.format(bedroc_auc_single(y_train_classification, y_pred_on_train)))
        print
        print('validation precision: {}'.format(precision_auc_single(y_val_classification, y_pred_on_val)))
        print('validation roc: {}'.format(roc_auc_single(y_val_classification, y_pred_on_val)))
        print('validation bedroc: {}'.format(bedroc_auc_single(y_val_classification, y_pred_on_val)))
        print
        if X_test is not None:
            print('test precision: {}'.format(precision_auc_single(y_test_classification, y_pred_on_test)))
            print('test roc: {}'.format(roc_auc_single(y_test_classification, y_pred_on_test)))
            print('test bedroc: {}'.format(bedroc_auc_single(y_test_classification, y_pred_on_test)))
            print

        if X_test is not None:
            for EF_ratio in self.EF_ratio_list:
                n_actives, ef, ef_max = enrichment_factor_single(y_test_classification, y_pred_on_test, EF_ratio)
                nef = ef / ef_max
                print('ratio: {}, EF: {},\tactive: {}'.format(EF_ratio, ef, n_actives))
                print('ratio: {}, NEF: {}'.format(EF_ratio, nef))

        return

    def get_EF_score_with_existing_model(self,
                                         X_test, y_test, y_test_classification,
                                         file_path, EF_ratio):
        model = self.setup_model()
        model.load_weights(file_path)
        y_pred_on_test = model.predict(X_test)
        print('test precision: {}'.format(precision_auc_single(y_test_classification, y_pred_on_test)))
        print('test roc: {}'.format(roc_auc_single(y_test_classification, y_pred_on_test)))
        print('test bedroc: {}'.format(bedroc_auc_single(y_test_classification, y_pred_on_test)))
        print

        n_actives, ef, ef_max = enrichment_factor_single(y_test_classification, y_pred_on_test, EF_ratio)
        nef = ef / ef_max
        print('EF: {},\tactive: {}'.format(ef, n_actives))
        print('NEF: {}'.format(nef))

        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_json_file', action="store", dest="config_json_file", required=True)
    parser.add_argument('--PMTNN_weight_file', action="store", dest="PMTNN_weight_file", required=True)
    parser.add_argument('--config_csv_file', action="store", dest="config_csv_file", required=True)
    given_args = parser.parse_args()
    config_json_file = given_args.config_json_file
    PMTNN_weight_file = given_args.PMTNN_weight_file
    config_csv_file = given_args.config_csv_file

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

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
    print output_file_list[0:4]
    train_pd = read_merged_data(output_file_list[0:4])
    print output_file_list[4]
    test_pd = read_merged_data([output_file_list[4]])

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=label_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=label_name_list)
    y_train_classification = reshape_data_into_2_dim(y_train[:, 0])
    y_train_regression = reshape_data_into_2_dim(y_train[:, 1])
    y_test_classification = reshape_data_into_2_dim(y_test[:, 0])
    y_test_regression = reshape_data_into_2_dim(y_test[:, 1])

    cross_validation_split = StratifiedShuffleSplit(y_train_classification, 1, test_size=0.2, random_state=1)

    for t_index, val_index in cross_validation_split:
        X_t, X_val = X_train[t_index], X_train[val_index]
        y_t_classification, y_val_classification = y_train_classification[t_index], y_train_classification[val_index]
        y_t_regression, y_val_regression = y_train_regression[t_index], y_train_regression[val_index]
    print 'done data preparation'

    task = SingleRegression(conf=conf)
    task.train_and_predict(X_t, y_t_regression, y_t_classification,
                           X_val, y_val_regression, y_val_classification,
                           X_test, y_test_regression, y_test_classification,
                           PMTNN_weight_file)
    task.predict_with_existing(X_t, y_t_regression, y_t_classification,
                               X_val, y_val_regression, y_val_classification,
                               X_test, y_test_regression, y_test_classification,
                               PMTNN_weight_file)
    task.get_EF_score_with_existing_model(X_test, y_test, y_test_classification,PMTNN_weight_file, 0.01)
    store_data(transform_json_to_csv(config_json_file), config_csv_file)
