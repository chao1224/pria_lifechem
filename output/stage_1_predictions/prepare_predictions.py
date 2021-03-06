import numpy as np
import os

model_name_list = [
    'single_classification_22',
    'single_classification_42',
    'single_regression_2',
    'single_regression_11',
    'multi_classification_15',
    'multi_classification_18',
    'sklearn_rf_390014_12',
    'sklearn_rf_390014_13',
    'sklearn_rf_390014_14',
    'sklearn_rf_390014_24',
    'sklearn_rf_390014_25',
    'sklearn_rf_390014_72',
    'sklearn_rf_390014_96',
    'sklearn_rf_390014_97',
    'deepchem_irv_5',
    'deepchem_irv_10',
    'deepchem_irv_20',
    'deepchem_irv_40',
    'deepchem_irv_80',
    'dockscore_hybrid',
    'dockscore_fred',
    'dockscore_dock6',
    'dockscore_rdockint',
    'dockscore_rdocktot',
    'dockscore_surflex',
    'dockscore_ad4',
    'dockscore_plants',
    'dockscore_smina',
    'consensus_dockscore_max',
    'consensus_bcs_efr1_opt',
    'consensus_bcs_rocauc_opt',
    'consensus_dockscore_median',
    'consensus_dockscore_mean'
]

fold_num = [
    20, 20, 20, 20, 20, 20,
    5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5
]

task_list = ['cross_validation_Keck_Pria_AS_Retest', 'cross_validation_Keck_FP', 'cross_validation_RMI']

for model in model_name_list:
    for task in task_list:
        outdir = '{}/{}'.format(task, model)
        if not os.path.exists(outdir):
            os.makedirs(outdir)

for i in range(len(model_name_list)):
    model = model_name_list[i]
    for j in range(fold_num[i]):
        file_path = '{}/fold_{}.npz'.format(model, j)
        data = np.load(file_path)
        for t in range(len(task_list)):
            y_test = data['y_test'][:, t]
            y_pred_on_test = data['y_pred_on_test'][:, t]
            outfile = '{}/{}/fold_{}.npz'.format(task_list[t], model, j)
            np.savez_compressed(outfile, y_test=y_test, y_pred_on_test=y_pred_on_test)