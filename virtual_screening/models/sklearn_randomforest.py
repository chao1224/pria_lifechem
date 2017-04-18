import argparse
import pandas as pd
import csv
import numpy as np
import json
import sys
sys.path.insert(0, '..')  # Add path from parent folder
sys.path.insert(0, '.')  # Add path from current folder
from function import *
from evaluation import *
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.externals import joblib
from sklearn.grid_search import ParameterGrid

rnd_state=1337
np.random.seed(seed=rnd_state)

class SKLearn_RandomForest:
    def __init__(self, conf):
        self.conf = conf
        self.input_layer_dimension = 1024
        self.label_names = conf['label_names']
        self.EF_ratio_list = conf['enrichment_factor']['ratio_list']
        
        self.process_id = int(os.environ.get('process'))        
        if self.process_id == None:
            print('Error: No environemnt variable process exists.')
            return 
        else:
            print('process id:', self.process_id)
        
        cnt = 0
        for param in ParameterGrid(conf['params']):
            if cnt != self.process_id:
                cnt += 1
                continue
            
            self.param = param
            self.n_estimators = param['n_estimators']
            self.max_features = param['max_features']
            self.min_samples_leaf = param['min_samples_leaf']
            self.class_weight = param['class_weight']
            print('Testing set:', param)            
            break
        
        if self.max_features == "None":
            self.max_features = None
        if self.class_weight == "None":
            self.class_weight = None
        
        self.model_dict = {}
        return

    def setup_model(self):
        for i in [0,1,3]:
            self.model_dict[self.label_names[i]] = RandomForestClassifier(n_estimators=self.n_estimators, 
                                           max_features=self.max_features, 
                                           min_samples_leaf=self.min_samples_leaf, 
                                           n_jobs=-1, 
                                           class_weight=self.class_weight,
                                           random_state=rnd_state,
                                           oob_score=False, 
                                           verbose=1) 
        for i in [2,4]:
            self.model_dict[self.label_names[i]] = RandomForestRegressor(n_estimators=self.n_estimators, 
                                           max_features=self.max_features, 
                                           min_samples_leaf=self.min_samples_leaf, 
                                           n_jobs=-1, 
                                           class_weight=self.class_weight,
                                           random_state=rnd_state,
                                           oob_score=False, 
                                           verbose=1) 
        return
        
        
    def train_and_predict(self,
                          X_train, y_train,
                          X_val, y_val,
                          X_test, y_test,
                          model_file):
                              
        self.setup_model()
        
        X_train = np.concatenate((X_train, X_val))
        y_train = np.concatenate((y_train, y_val))
        
        p = np.random.permutation(len(X_train))
        X_train = X_train[p,:]
        y_train = y_train[p,:]
        p = np.random.permutation(len(X_test))
        X_test = X_test[p,:]
        y_test = y_test[p,:]
        
        for i, label in (range(len(self.label_names)), self.label_names):
            y = y_train[:,i]
            indexes = np.where(np.isnan(y))[0]
                
            y = np.delete(y, indexes, axis=0)
            X = np.delete(X_train, indexes, axis=0)
            self.model_dict[label].fit(X, y)
            
            joblib.dump(self.model_dict[label], model_file+'_'+label+'.pkl')
        return

    def predict_with_existing(self,
                              X_train, y_train,
                              X_val, y_val,
                              X_test, y_test,
                              model_file):  
                                  
        X_train = np.concatenate((X_train, X_val))
        y_train = np.concatenate((y_train, y_val))
        
        y_pred_on_train = np.zeros(shape=y_train.shape)
        y_pred_on_test = np.zeros(shape=y_test.shape)
        
        y_train[:,2] = y_train[:,0]
        y_train[:,4] = y_train[:,3]
        y_test[:,2] = y_test[:,0]
        y_test[:,4] = y_test[:,3]
        
        for i, label in (range(len(self.label_names)), self.label_names):     
            model = joblib.load(model_file+'_'+label+'.pkl')
            
            y_pred_on_train[:,i] =  model.predict_proba(X_train)[:,1].reshape(X_train.shape[0],1)
            
            y_pred_on_test[:,i] = model.predict_proba(X_test)[:,1].reshape(X_test.shape[0],1)
            
            if i in [0,1,3]:
                y_train[np.where(np.isnan(y_train[:,i]))[0],i] = -1
                y_test[np.where(np.isnan(y_test[:,i]))[0],i] = -1
         
        y_train = np.insert(y_train, 3, y_train[:,1], axis=1)
        y_test = np.insert(y_test, 3, y_test[:,1], axis=1)
        
        y_pred_on_train = np.insert(y_pred_on_train, 3, y_pred_on_train[:,2], axis=1)
        y_pred_on_test = np.insert(y_pred_on_test, 3, y_pred_on_test[:,2], axis=1)
        
        print
        print('train precision: {}'.format(precision_auc_multi(y_train, y_pred_on_train, range(y_train.shape[1]), np.mean)))
        print('train roc: {}'.format(roc_auc_multi(y_train, y_pred_on_train, range(y_train.shape[1]), np.mean)))
        print('train bedroc: {}'.format(bedroc_auc_multi(y_train, y_pred_on_train, range(y_train.shape[1]), np.mean)))
        print
        print('test precision: {}'.format(precision_auc_multi(y_test, y_pred_on_test, range(y_train.shape[1]), np.mean)))
        print('test roc: {}'.format(roc_auc_multi(y_test, y_pred_on_test, range(y_train.shape[1]), np.mean)))
        print('test bedroc: {}'.format(bedroc_auc_multi(y_test, y_pred_on_test, range(y_train.shape[1]), np.mean)))
        print
        
        label_list = ['Keck_Pria_AS_Retest', 'Keck_Pria_FP_data', 
                      'Keck_Pria_Continuous_AS_Retest', 'Keck_Pria_Continuous_FP_data',
                      'Keck_RMI_cdd', 'FP counts % inhibition']
        nef_auc_mean = np.mean(np.array(nef_auc(y_train, y_pred_on_train, self.EF_ratio_list, label_list))) 
        print('train nef auc: {}'.format(nef_auc_mean))
        nef_auc_mean = np.mean(np.array(nef_auc(y_test, y_pred_on_test, self.EF_ratio_list, label_list))) 
        print('test nef auc: {}'.format(nef_auc_mean))
        return

    def save_model_evaluation_metrics(self,
                              X, y_true,
                              model_file,
                              metric_dir,
                              label_names=None):
        
        if not os.path.exists(metric_dir):
            os.makedirs(metric_dir)   
        
        y_pred = np.zeros(shape=y.shape)
        
        y_true[:,2] = y_true[:,0]
        y_true[:,4] = y_true[:,3]
        
        for i, label in (range(len(self.label_names)), self.label_names):     
            model = joblib.load(model_file+'_'+label+'.pkl')
            
            y_pred[:,i] =  model.predict_proba(X)[:,1].reshape(X.shape[0],1)
            
            if i in [0,1,3]:
                y_true[np.where(np.isnan(y_true[:,i]))[0],i] = -1
        
        y_true = np.insert(y_true, 3, y_true[:,1], axis=1)
        y_pred = np.insert(y_pred, 3, y_pred[:,2], axis=1)
        
        label_list = ['Keck_Pria_AS_Retest', 'Keck_Pria_FP_data', 
                      'Keck_Pria_Continuous_AS_Retest', 'Keck_Pria_Continuous_FP_data',
                      'Keck_RMI_cdd', 'FP counts % inhibition']
        evaluate_model(y_true, y_pred, metric_dir, label_list)        
        return
        
    def save_model_info(self, config_csv_file):
        
        if not os.path.exists(config_csv_file):
            os.makedirs(config_csv_file)   
       
        
        data = str(self.param)
        with open(config_csv_file, 'w') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            for d in data:
                writer.writerow([d])
        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_json_file', action="store", dest="config_json_file", required=True)
    parser.add_argument('--model_dir', action="store", dest="model_dir", required=True)
    parser.add_argument('--dataset_dir', action="store", dest="dataset_dir", required=True)
    #####
    given_args = parser.parse_args()
    config_json_file = given_args.config_json_file
    model_dir = given_args.model_dir
    dataset_dir = given_args.dataset_dir
    #####
    model_file = model_dir+'rf_clf'
    config_csv_file = model_dir+'model_config.csv'
    #####
    scratch_dir = os.environ.get('_CONDOR_JOB_IWD')
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)    
    
    # specify dataset
    directory = dataset_dir
    file_list = []
    k=5
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
    
    train_pd = read_merged_data(output_file_list[0:2])
    test_pd = read_merged_data([output_file_list[4]])
    val_pd = read_merged_data([output_file_list[3]])
    
    labels = ['Keck_Pria_AS_Retest', 'Keck_Pria_FP_data', 'Keck_Pria_Continuous',
              'Keck_RMI_cdd', 'FP counts % inhibition']

    # extract data, and split training data into training and val
    X_train, y_train = extract_feature_and_label(train_pd,
                                                 feature_name='Fingerprints',
                                                 label_name_list=labels)
    
    X_val, y_val = extract_feature_and_label(val_pd,
                                             feature_name='Fingerprints',
                                             label_name_list=labels)
                                               
    X_test, y_test = extract_feature_and_label(test_pd,
                                               feature_name='Fingerprints',
                                               label_name_list=labels)
    print('done data preparation')
    
    

    with open(config_json_file, 'r') as f:
        conf = json.load(f)
    task = SKLearn_RandomForest(conf=conf)
    task.train_and_predict(X_train, y_train, X_val, y_val, X_test, y_test, model_file)
    task.save_model_params(config_csv_file)
    
    #####
    task.save_model_evaluation_metrics(np.concatenate((X_train, X_val)), 
                                       np.concatenate((y_train, y_val)), model_file,
                                      model_dir+'train_metrics/',
                                      label_names=labels)
    task.save_model_evaluation_metrics(X_test, y_test, model_file,
                                      model_dir+'test_metrics/',
                                      label_names=labels)