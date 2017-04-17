import pandas as pd
import numpy as np
from rdkit.Chem import AllChem
from rdkit import Chem
import operator
import json


'''
Transform the data from raw xlsx into csv format
'''
def transform_data(output_file_name):
    discrete_file = pd.ExcelFile('../dataset/data_preprocessing/screening_smsf_actives_2017_03_10.xlsx')
    Keck_Pria_Retest = discrete_file.parse('Keck_Pria_Retest')
    Keck_Pria_FP = discrete_file.parse('Keck_Pria_FP')
    Keck_RMI = discrete_file.parse('Keck_RMI')
    Xing_MTDH_Retest = discrete_file.parse('Xing_MTDH_Retest')
    Xing_MTDH_DR = discrete_file.parse('Xing_MTDH_DR')
    
    continuous_file = pd.ExcelFile('../dataset/data_preprocessing/screening_smsf_continuous_2017_03_10.xlsx')
    Keck_Pria_Primary = continuous_file.parse('Keck_Pria_Primary')
    Keck_RMI_cdd = continuous_file.parse('Keck_RMI_cdd')
    Xing_MTDH_cdd = continuous_file.parse('Xing_MTDH_cdd')
    
    f = open('../dataset/data_preprocessing/lifechem123_cleaned_2017_03_10.smi', 'r')
    mol_smile_dict = {}
    mol_fps_dict = {}

    for line in f:
        line = line.strip()
        row = line.split(' ')
        smiles = row[0]
        molecule_id = row[1]
        
        # Get SMILE
        mol_smile_dict[molecule_id] = smiles
        
        # Get molecule descriptor from SMILES
        # Then generate Fingerprints from molecule descriptor
        mol = Chem.MolFromSmiles(smiles)
        fingerprints = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
        mol_fps_dict[molecule_id] = fingerprints.ToBitString()
        
    mol_smile_map = sorted(mol_smile_dict.items())
    molecules = [item[0] for item in mol_smile_map]
    smiles = [item[1] for item in mol_smile_map]
    smiles_df = pd.DataFrame({'Molecule': molecules, 'SMILES': smiles})
    
    molecules = [key for key,_ in mol_fps_dict.iteritems()]
    fingerprints = [value for _,value in mol_fps_dict.iteritems()]
    fingerprints_df = pd.DataFrame({'Molecule': molecules, 'Fingerprints': fingerprints})
    
    result = pd.merge(smiles_df, fingerprints_df, on='Molecule', how='outer')
    result = pd.merge(result, Keck_Pria_Retest, on='Molecule', how='outer')
    result = pd.merge(result, Keck_Pria_FP, on='Molecule', how='outer')
    result = pd.merge(result, Keck_Pria_Primary, on='Molecule', how='outer')
    result = pd.merge(result, Keck_RMI, on='Molecule', how='outer')
    result = pd.merge(result, Keck_RMI_cdd, on='Molecule', how='outer')

    result.to_csv(output_file_name, index=None)

    return


'''
Create sample weights, for weighted model
'''
def generate_sample_weights(target_dir, k, dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    for i in range(k):
        data_pd = pd.read_csv(target_dir + 'file_{}.csv'.format(i))

        # First three labels are Molecule, SMILES, and Finterprints
        # The remaining ones are labels
        labels = data_pd.columns.tolist()[3:]
        data_pd.replace([0], 1)
        data_pd.replace([np.NaN], 0)
        data_pd.to_csv(dest_dir + 'sample_weight_{}.csv'.format(i), index=None)

    return


'''
Get the mappings for SMILES
Pre-train this for only once
'''
fixed_SMILES_mapping_json_file = '../json/SMILES_mapping.json'
def mapping_SMILES(data_pd, json_file=fixed_SMILES_mapping_json_file):
    dictionary_set = set()
    for smile in data_pd['SMILES']:
        dictionary_set = dictionary_set | set(list(smile))
    index = 1
    dictionary = {}
    for element in dictionary_set:
        dictionary[element] = index
        index += 1
    print dictionary
    print 'alphabet set size {}'.format(len(dictionary))

    with open(json_file, 'w') as f:
        json.dump(dictionary, f)

    return


if __name__ == '__main__':
    transform_data('../dataset/keck_complete.csv')