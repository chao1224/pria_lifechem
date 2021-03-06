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
from sklearn.grid_search import ParameterGrid
from pria_lifechem.function import *
from pria_lifechem.evaluation import *
from pria_lifechem.models.CallBacks import *
from pria_lifechem.models.deep_classification import *
from pria_lifechem.models.deep_regression import *
from pria_lifechem.models.vanilla_lstm import *
from pria_lifechem.models.tree_net import *


def run_single_classification(running_index, use_duplicate=False):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    # specify dataset
    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index+1]
    test_file_list = file_list[test_index:test_index+1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    train_pd = filter_out_missing_values(read_merged_data(train_file_list), label_list=label_name_list)
    val_pd = filter_out_missing_values(read_merged_data(val_file_list), label_list=label_name_list)
    test_pd = filter_out_missing_values(read_merged_data(test_file_list), label_list=label_name_list)

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=label_name_list)
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=label_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=label_name_list)

    print 'done data preparation'

    if use_duplicate:
        X_complement = []
        y_complement = []
        pos_count = 0
        for index in range(y_train.shape[0]):
            label = y_train[index, 0]
            if label == 1:
                pos_count += 1
                for _ in range(500):
                    X_complement.append(X_train[index])
                    y_complement.append(y_train[index])
        X_complement = np.array(X_complement)
        y_complement = np.array(y_complement)
        
        X_train = np.vstack((X_train, X_complement))
        y_train = np.vstack((y_train, y_complement))

    task = SingleClassification(conf=conf)
    task.train_and_predict(X_train, y_train, X_val, y_val, X_test, y_test, PMTNN_weight_file)
    store_data(transform_json_to_csv(config_json_file), config_csv_file)

    return


def run_single_regression(running_index):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    # specify dataset
    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index+1]
    test_file_list = file_list[test_index:test_index+1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    train_pd = filter_out_missing_values(read_merged_data(train_file_list), label_list=label_name_list)
    val_pd = filter_out_missing_values(read_merged_data(val_file_list), label_list=label_name_list)
    test_pd = filter_out_missing_values(read_merged_data(test_file_list), label_list=label_name_list)

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=label_name_list)
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=label_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=label_name_list)

    y_train_classification = reshape_data_into_2_dim(y_train[:, 0])
    y_train_regression = reshape_data_into_2_dim(y_train[:, 1])
    y_val_classification = reshape_data_into_2_dim(y_val[:, 0])
    y_val_regression = reshape_data_into_2_dim(y_val[:, 1])
    y_test_classification = reshape_data_into_2_dim(y_test[:, 0])
    y_test_regression = reshape_data_into_2_dim(y_test[:, 1])
    print 'done data preparation'

    task = SingleRegression(conf=conf)
    task.train_and_predict(X_train, y_train_regression, y_train_classification,
                           X_val, y_val_regression, y_val_classification,
                           X_test, y_test_regression, y_test_classification,
                           PMTNN_weight_file)
    store_data(transform_json_to_csv(config_json_file), config_csv_file)

    return


def run_vanilla_lstm(running_index):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    # specify dataset
    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index + 1]
    test_file_list = file_list[test_index:test_index + 1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    # TODO: No validation set for LSTM, may merge with train set
    train_pd = filter_out_missing_values(read_merged_data(train_file_list), label_list=label_name_list)
    val_pd = filter_out_missing_values(read_merged_data(val_file_list), label_list=label_name_list)
    test_pd = filter_out_missing_values(read_merged_data(test_file_list), label_list=label_name_list)

    # extract data, and split training data into training and val
    X_train, y_train = extract_SMILES_and_label(train_pd,
                                                feature_name='SMILES',
                                                label_name_list=label_name_list,
                                                SMILES_mapping_json_file=SMILES_mapping_json_file)
    X_val, y_val = extract_SMILES_and_label(val_pd,
                                            feature_name='SMILES',
                                            label_name_list=label_name_list,
                                            SMILES_mapping_json_file=SMILES_mapping_json_file)
    X_test, y_test = extract_SMILES_and_label(test_pd,
                                              feature_name='SMILES',
                                              label_name_list=label_name_list,
                                              SMILES_mapping_json_file=SMILES_mapping_json_file)
    print 'done data preparation'

    task = VanillaLSTM(conf)
    X_train = sequence.pad_sequences(X_train, maxlen=task.padding_length)
    X_val = sequence.pad_sequences(X_val, maxlen=task.padding_length)
    X_test = sequence.pad_sequences(X_test, maxlen=task.padding_length)

    task.train_and_predict(X_train, y_train, X_val, y_val, X_test, y_test, PMTNN_weight_file)
    store_config(conf, config_csv_file)

    return


def run_tree_net(running_index):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index+1]
    test_file_list = file_list[test_index:test_index+1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    train_pd = read_merged_data(train_file_list)
    val_pd = read_merged_data(val_file_list)
    test_pd = read_merged_data(test_file_list)

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=label_name_list)
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=label_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=label_name_list)

    y_train_classification = reshape_data_into_2_dim(y_train[:, 0])
    y_train_regression = reshape_data_into_2_dim(y_train[:, 1])
    y_val_classification = reshape_data_into_2_dim(y_val[:, 0])
    y_val_regression = reshape_data_into_2_dim(y_val[:, 1])
    y_test_classification = reshape_data_into_2_dim(y_test[:, 0])
    y_test_regression = reshape_data_into_2_dim(y_test[:, 1])
    print 'done data preparation'

    task = TreeNet(conf)
    task.train_and_predict_ensemble(X_train, y_train_regression, y_train_classification,
                                    X_val, y_val_regression, y_val_classification,
                                    X_test, y_test_regression, y_test_classification,
                                    PMTNN_weight_file)

    return


def run_multiple_classification(running_index):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    # specify dataset
    k = 5
    directory = '../../dataset/keck_pcba/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index + 1]
    test_file_list = file_list[test_index:test_index + 1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    train_pd = read_merged_data(train_file_list)
    train_pd.fillna(0, inplace=True)
    val_pd = read_merged_data(val_file_list)
    val_pd.fillna(0, inplace=True)
    # TODO: may only consider Keck label
    test_pd = read_merged_data(test_file_list)
    test_pd.fillna(0, inplace=True)

    multi_name_list = train_pd.columns[-128:].tolist()
    multi_name_list.extend(label_name_list)
    print 'multi_name_list ', multi_name_list

    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=multi_name_list)
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=multi_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=multi_name_list)

    sample_weight_dir = '../../dataset/sample_weights/keck_pcba/fold_5/'
    file_list = []
    for i in range(k):
        file_list.append('sample_weight_{}.csv'.format(i))
    sample_weight_file = [sample_weight_dir + f_ for f_ in file_list]
    sample_weight_file = np.array(sample_weight_file)
    sample_weight_pd = read_merged_data(sample_weight_file[train_index])
    _, sample_weight = extract_feature_and_label(sample_weight_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=multi_name_list)
    print 'done data preparation'

    task = MultiClassification(conf=conf)
    task.train_and_predict(X_train, y_train, X_val, y_val, X_test, y_test,
                           sample_weight=sample_weight,
                           PMTNN_weight_file=PMTNN_weight_file,
                           score_file=score_file)
    store_data(transform_json_to_csv(config_json_file), config_csv_file)

    return


def run_dnn_rf(running_index):
    if running_index >= cross_validation_upper_bound:
        raise ValueError('Process number out of limit. At most {}.'.format(cross_validation_upper_bound-1))

    with open(config_json_file, 'r') as f:
        conf = json.load(f)

    # TODO: debug
    conf['fitting']['nb_epoch'] = 200
    conf['fitting']['early_stopping']['patience'] = 50

    label_name_list = conf['label_name_list']
    print 'label_name_list ', label_name_list

    # specify dataset
    k = 5
    directory = '../../dataset/fixed_dataset/fold_{}/'.format(k)
    file_list = []
    for i in range(k):
        file_list.append('{}file_{}.csv'.format(directory, i))
    file_list = np.array(file_list)

    # read data
    test_index = running_index / 4
    val_index = running_index % 4 + (running_index % 4 >= test_index)
    complete_index = np.arange(k)
    train_index = np.where((complete_index != test_index) & (complete_index != val_index))[0]
    print train_index

    train_file_list = file_list[train_index]
    val_file_list = file_list[val_index:val_index+1]
    test_file_list = file_list[test_index:test_index+1]

    print 'train files ', train_file_list
    print 'val files ', val_file_list
    print 'test files ', test_file_list

    train_pd = read_merged_data(train_file_list)
    val_pd = read_merged_data(val_file_list)
    test_pd = read_merged_data(test_file_list)

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=label_name_list)
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=label_name_list)
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=label_name_list)
    print 'done data preparation'

    # TODO: remove debugging info
    # conf['fitting']['nb_epoch'] = 1
    task = DNN_RF(conf=conf)

    print
    print 'This is STNN'
    task.train_and_predict(X_train, y_train, X_val, y_val, X_test, y_test, PMTNN_weight_file)
    print
    print 'This is STNN+RF'
    task.get_rf(X_train, y_train, X_val, y_val, X_test, y_test)

    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_json_file', dest="config_json_file",
                        action="store", required=True)
    parser.add_argument('--PMTNN_weight_file', dest="PMTNN_weight_file",
                        action="store", required=True)
    parser.add_argument('--config_csv_file', dest="config_csv_file",
                        action="store", required=True)
    parser.add_argument('--process_num', dest='process_num', type=int,
                        action='store', required=True)
    parser.add_argument('--SMILES_mapping_json_file', dest='SMILES_mapping_json_file',
                        action='store', required=False, default= '../../json/SMILES_mapping.json')
    parser.add_argument('--score_file', dest='score_file',
                        action='store', required=False)
    parser.add_argument('--model', dest='model',
                        action='store', required=True)
    parser.add_argument('--cross_validation_upper_bound', dest='cross_validation_upper_bound', type=int,
                        action='store', required=False, default=20)
    parser.add_argument('--seed', dest='seed', type=int,
                        action='store', required=False, default=None)
    given_args = parser.parse_args()
    print 'Seed is {}'.format(given_args.seed)
    if given_args.seed is not None:
        np.random.seed(given_args.seed)

    config_json_file = given_args.config_json_file
    PMTNN_weight_file = given_args.PMTNN_weight_file
    config_csv_file = given_args.config_csv_file
    cross_validation_upper_bound = given_args.cross_validation_upper_bound

    process_num = int(given_args.process_num)
    model = given_args.model

    if model == 'single_classification':
        run_single_classification(process_num)
    elif model == 'single_regression':
        run_single_regression(process_num)
    elif model == 'vanilla_lstm':
        SMILES_mapping_json_file = given_args.SMILES_mapping_json_file
        run_vanilla_lstm(process_num)
    elif model == 'multi_classification':
        score_file = given_args.score_file
        run_multiple_classification(process_num)
    elif model == 'tree_net':
        run_tree_net(process_num)
    elif model == 'single_dnn_rf':
        run_dnn_rf(process_num)
    else:
        raise Exception('No such model! Should be among [{}, {}, {}, {}, {}].'.format(
            'single_classification',
            'single_regression',
            'vanilla_lstm',
            'multi_classification',
            'tree_net',
            'single_dnn_rf'
        ))
