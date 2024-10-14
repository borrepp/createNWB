import os
from scipy import io as scipy_io
from pynwb import NWBHDF5IO



base_folder = 'Y:/Data_Albus/Albus_NeuralData/Albus-S1' # Path where to search for NWB files
folder_save = 'Y:/Data_Albus/Albus_NeuralData/Albus-S1-Trials' # Path where to save *-trials.df & *-trials.mat (any subdirectory will that exists within base_folder will be mimic within the folder_save)

updateFiles = False # True / False if you want to re-write the *-trials files in the final destination


# If folder_save is None, it will save the files in the same folder as the original NWB
if folder_save is None:
    folder_save = base_folder

# Check if final folder destination exists, otherwise it will create it
if not os.path.exists(folder_save):
    os.makedirs(folder_save)

# Walk through all the folders and subfolders to find *.nwb files
for root, _, files in os.walk(base_folder):

    for name in files:
        nameSplit = os.path.splitext(name)

        if nameSplit[1]=='.nwb':
        
            fileName = nameSplit[0]

            filePath_save = os.path.join(folder_save + root[len(base_folder)::])
            trialsPath = os.path.join(filePath_save, fileName + '-trials')

            if (not os.path.exists(trialsPath + '.df') or not os.path.exists(trialsPath + '.mat')) or updateFiles:

                if not os.path.exists(filePath_save):
                    os.makedirs(filePath_save)
                
                nwbPath = os.path.join(root, fileName + '.nwb')

                print('\nextracting Trials from file : ', fileName + '.nwb')
                print('readingPath : ', nwbPath, '\nsavingPath : ', trialsPath)

                fNWBio = NWBHDF5IO(nwbPath, mode="r")
                nwbfile = fNWBio.read()
                trialsNWB = nwbfile.trials.to_dataframe()

                # Save binary dataframe  "*.df"
                trialsNWB.to_pickle(trialsPath + '.df', compression=None)

                # Save matlab 
                scipy_io.savemat(trialsPath + '.mat', {'data': trialsNWB.to_dict(orient='records')}, oned_as='column')

                fNWBio.close()
                