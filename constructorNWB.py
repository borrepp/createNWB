
import os
import shutil
import numpy
from tkinter.filedialog import askopenfilename
import yamlTools
import rippleTools
import constructorTools
from hdmf.backends.hdf5.h5_utils import H5DataIO
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.file import Subject
from pynwb.device import Device
from pynwb.epoch import TimeIntervals
from pynwb.behavior import SpatialSeries, EyeTracking, PupilTracking, Position
from hdmf.common import DynamicTableRegion
from pynwb.ecephys import ElectricalSeries, SpikeEventSeries
from nwbinspector import inspect_nwbfile
import h5py
import time
import sys

# Combine Behavioral Data from *.nev (markers) & *.YAML files into a NWB file 
# file format follow YAULAB convention of the task : visual cues + 2 shakers + footbar + eye tracking + pupil diameter

version = '0.1.0'
version_date ='2024-02-14'
version_date_temp = '2024-06-18'

class Unbuffered:
    def __init__(self, stream, fwriteMode):
        self.stream = stream
        self.fwriteMode = fwriteMode
    def write(self, data):
        self.fwriteMode.write(data)    # Write the data of stdout here to a text file:
        self.stream.write(data)
        self.stream.flush()

def check_temp_date(fileName):

    yearFile = int(fileName[3:7])
    monthFile = int(fileName[8:10])
    dayFile = int(fileName[11:13])

    
    yearTemp= int(version_date_temp[0:4])
    monthTemp = int(version_date_temp[5:7])
    dayTemp = int(version_date_temp[8:])

    if yearFile>yearTemp:
        versionCompatible = True
    elif yearFile==yearTemp and monthFile>monthTemp:
        versionCompatible = True
    elif yearFile==yearTemp and monthFile==monthTemp and dayFile>=dayTemp:
        versionCompatible = True
    else:
        versionCompatible = False
    
    return versionCompatible

##################################################################################################################
# Set up environment variables and get YAML file Paths to be extracted
def get_filePaths_to_extract(folderName, fileName=None, updateFiles = False, dateUpdate=None):
    
    # Check TemporalFolder is created and available as a environment variable
    constructorTools.set_NWBtempdir_environ()
    # Clear TemporaryFolder from previous processes. 
    constructorTools.clear_NWBtempdir()

    if dateUpdate is None:
        dateUpdate = version_date
        
    yamlFiles2convert = []

    yearUpdate = int(dateUpdate[0:4])
    monthUpdate = int(dateUpdate[5:7])
    dayUpdate = int(dateUpdate[8:])

    folderName = os.path.abspath(folderName)

    if fileName is None:

        for root, _, files in os.walk(folderName):

            for name in files:

                nameSplit = os.path.splitext(name)

                if nameSplit[1]=='.yaml':

                    fileName = nameSplit[0]
                    yearFile = int(fileName[3:7])
                    monthFile = int(fileName[8:10])
                    dayFile = int(fileName[11:13])

                    if yearFile>yearUpdate:
                        versionCompatible = True
                    elif yearFile==yearUpdate and monthFile>monthUpdate:
                        versionCompatible = True
                    elif yearFile==yearUpdate and monthFile==monthUpdate and dayFile>=dayUpdate:
                        versionCompatible = True
                    else:
                        versionCompatible = False

                    filePathYAML = os.path.join(root, fileName + '.yaml')

                    if updateFiles and versionCompatible:
                        yamlFiles2convert.append(filePathYAML)
                    else:
                        if versionCompatible:
                            filePathNev = os.path.join(root, fileName + '.nev')

                            if not os.path.isfile(filePathNev):
                                extNWB = '-noNEV'
                            else:
                                extNWB = ''

                            filePathNWB = os.path.join(root, fileName + extNWB + '.nwb')

                            if not os.path.isfile(filePathNWB):
                                yamlFiles2convert.append(filePathYAML)
    else:

        filePathNev = os.path.join(folderName, fileName + '.nev')

        if not os.path.isfile(filePathNev):
            extNWB = '-noNEV'
        else:
            extNWB = ''

        filePathNWB = os.path.join(folderName, fileName +  extNWB + '.nwb')

        if not os.path.isfile(filePathNWB):
            yamlFiles2convert.append(os.path.join(folderName, fileName + '.yaml'))


    if len(yamlFiles2convert)==0:
        print('\nThere were no YAML files to convert ("updateFiles" was set to: {})\
            \nRemember that files created before {} are not compatible\n'.format(updateFiles, dateUpdate))
    
    return yamlFiles2convert
###################################################################################################################
# check if container Folder has the same name as YAML, otherwise create the folder and copy:
# *.eye, *.nev, *nsX, *.nwb
def check_folderSession(filePathYAML, copy2disk=True):

    filePath, fileNameExt = os.path.split(os.path.abspath(filePathYAML))
    fileName, _ = os.path.splitext(fileNameExt)

    #Check if files need to be moved to a temporal folder
    copyFiles = False
    if copy2disk and filePath[0:2].lower()!=os.path.abspath(__file__)[0:2].lower():
        copyFiles = True

    dir_list = os.listdir(filePath)
    files2extract = [n for n in dir_list if fileName + '.' in n or fileName + '-noNEV.nwb' in n] 

    filesNWB = [n for n in files2extract if '.nwb' in n]

    if len(filesNWB)>0:
        print('Warning: NWB file aready exists it will be overwritten:\n{}'.format(filesNWB))

    _, containerFolder = os.path.split(filePath)
    if fileName==containerFolder:
        # print('Files are already within a session Folder, no move of files will ocurr')
        folder_save = filePath
    else:
        
        folder_save = os.path.join(filePath, fileName)

        if os.path.exists(folder_save):
            # check if Files also exist IN the folder
            dir_list2 = os.listdir(folder_save)
            filesExists = [n for n in dir_list2 if fileName + '.' in n or fileName + '-noNEV.nwb' in n]
            file2replace = [f for f in files2extract if f in filesExists]
            if len(file2replace)>0:
                raise Exception('\n\nParentFolder already has a folder for this session\n\nParentFolder:{}\
                                \nParentFolder files:\n{}\
                                \nExisting FolderSession:{}\nFolderSession files:\n{}\
                                \nYou will need to combined/replace manually'.format(
                                    filePath, files2extract, folder_save, filesExists)
            )
            print('Session-Folder already exists:\n{}\nFiles will be moved to this folder'.format(folder_save))
        else:
            print('A new folder for this session will be created:\n{}'.format(folder_save))
            os.mkdir(folder_save)

        print('The following files will be moved:\n{}'.format(files2extract))

        for f in files2extract:
            shutil.move(os.path.join(filePath, f), os.path.join(folder_save, f), copy_function = shutil.copy2)
    
    if copyFiles:
        folder_read = os.environ.get('NWB_PROCESSOR_TEMPDIR')
        if folder_read is None:
            constructorTools.set_NWBtempdir_environ()
            folder_read = os.environ.get('NWB_PROCESSOR_TEMPDIR')

        files2copy = [n for n in files2extract if '.nwb' not in n]
        for f in files2copy:
            print('..... copying file {}'.format(f))
            shutil.copy2(os.path.join(folder_save, f), os.path.join(folder_read, f))
    else:
        folder_read = folder_save
    
    return folder_save, folder_read, fileName


###################################################################################################################
# Add eye tracking data into the NWBfile using the behaviour module.
def nwb_add_eyeData(nwb_behavior_module, filePath, dictYAML, 
                    nsFile=None,
                    analogEye = None,
                    eyeTrackID=None,
                    eyeXYComments=None,                    
                    pupilDiameterComments = None,
                    verbose=False
                    ):
    
    if eyeTrackID is None:
        eyeTrackID = yamlTools.labInfo['EyeTrackingInfo']['EyeTracked']
    
    if eyeXYComments is None:
        eyeXYComments = yamlTools.labInfo['EyeTrackingInfo']['XYComments']
    
    if pupilDiameterComments is None:
        pupilDiameterComments = yamlTools.labInfo['EyeTrackingInfo']['PupilDiameterComments']
    
    ###############################################################
    #               Add EYE-PC data -eyeTracking
    ############################################################### 
    exists_PCEYE_containers = False

    eyeData_h5paths = []
    eyeData_h5objs = []

    if os.path.isfile(filePath + '.eye'):

        eyePCstartTime = yamlTools.getEyeStartTime(filePathEYE = filePath + '.eye', verbose=False)

        if eyePCstartTime is not None:

            eyePC_offsetNEV = constructorTools.get_eyePC_offset(dictYAML, eyePCstartTime, nsFile)
            eyePC_aligned2nev = yamlTools.getEyeData(filePathEYE = filePath + '.eye', offsetSecs = eyePC_offsetNEV)

            ###############################################################
            #                      Add PC-eyeTracking
            ############################################################### 
            if verbose:
                print('\nextracting [X, Y] eye Data from PC file.....')
            eyeTrackingPC = SpatialSeries(
                name= eyeTrackID + '_eyePC_XY',
                description = '(horizontal, vertical) {} eye position'.format(eyeTrackID),
                comments = eyeXYComments + ' Data were recorded on the behavioral-PC',
                data = H5DataIO(
                    data = numpy.array([eyePC_aligned2nev['x'], eyePC_aligned2nev['y']]).transpose(), 
                    compression = True
                    ),
                reference_frame = "(0, 0) is the center of animal's eye gaze",
                timestamps = eyePC_aligned2nev['time'],
                unit = 'degrees',
                )

            eyeTracking = EyeTracking(spatial_series=eyeTrackingPC)
            del eyeTrackingPC

            ###############################################################
            #                   Add PC-pupilDiamater
            ###############################################################
            if verbose:
                print('\nextracting pupil diameter from PC file.....')
            pupilPC = TimeSeries(
                name = eyeTrackID + '_pupilPC',
                description = 'pupil diameter in pixels units. Obtained by video recording of the {} eye'.format(eyeTrackID),
                comments = pupilDiameterComments + ' Data were recorded on the behavioral-PC',
                data = H5DataIO(
                    data = eyePC_aligned2nev['pupil'], 
                    compression = True
                    ),
                timestamps = eyePC_aligned2nev['time'],
                unit = 'pixels',
                continuity = 'continuous',
                )

            pupildiameter = PupilTracking(time_series=pupilPC)
            del pupilPC

            exists_PCEYE_containers = True

    ###############################################################
    #                  Add RIPPLE-eyeTracking 
    ###############################################################
    exists_nsEYE_tracking = False
    if nsFile is not None:
        extractAnalogEye_horizontal = False
        if analogEye is None:
            extractAnalogEye_horizontal = True
        else:
            extractAnalogEye_horizontal = analogEye['exists_eyeHorizontal']

        if extractAnalogEye_horizontal:

            nsEye_horizontal = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='eyeHorizontal')
            nsEye_horizontal_INFO = nsEye_horizontal.get_info()

            if verbose:
                print('\nextracting [X] eyeData from Ripple.....')

            eye_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsEye_horizontal_INFO['index']], 
                            tempName='eyeHorizontal', 
                            itemCount=nsEye_horizontal_INFO['item_count'], 
                            verbose=verbose)
            
            eye_h5 = h5py.File(name=eye_h5path, mode="r")

            eyeTrackingNS = SpatialSeries(
                name= eyeTrackID + '_eyeRipple_X',
                description = nsEye_horizontal_INFO['description'] + '({} eye'.format(eyeTrackID),
                comments = eyeXYComments + ' Data were recorded on Ripple System (chanName:' + nsEye_horizontal_INFO['chanName'] + ')',
                data = H5DataIO(eye_h5["dataSet"]),
                reference_frame = "(0) is the horizontal-center of animal's eye gaze",
                starting_time = 0.0,
                rate = nsEye_horizontal_INFO['samplingRate'],
                unit = nsEye_horizontal_INFO['units'],
                conversion = nsEye_horizontal_INFO['convertionFactor'],
                )
            
            eyeData_h5paths.append(eye_h5path)
            eyeData_h5objs.append(eye_h5)

            if exists_PCEYE_containers:
                eyeTracking.add_spatial_series(spatial_series=eyeTrackingNS)
            else:
                eyeTracking = EyeTracking(spatial_series=eyeTrackingNS)

            del eyeTrackingNS

            exists_nsEYE_tracking = True

    if exists_PCEYE_containers or exists_nsEYE_tracking:
        nwb_behavior_module.add(eyeTracking)

        del eyeTracking

    ###############################################################
    #                    Add Ripple-pupilDiamater
    ###############################################################
    exists_nsPUPIL_tracking = False
    if nsFile is not None:
        extractAnalogEye_pupil = False
        if analogEye is None:
            extractAnalogEye_pupil = True
        else:
            extractAnalogEye_pupil = analogEye['exists_eyePupil']

        if extractAnalogEye_pupil:

            nsPupilDiameter = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='pupilDiameter')
            nsPupilDiameter_INFO = nsPupilDiameter.get_info()

            if verbose:
                print('\nextracting pupil diameter from Ripple.....')
            
            pupil_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsPupilDiameter_INFO['index']], 
                            tempName='pupilDiameter', 
                            itemCount=nsPupilDiameter_INFO['item_count'], 
                            verbose=verbose)
            
            pupil_h5 = h5py.File(name=pupil_h5path, mode="r")

            pupilNS = TimeSeries(
                name = eyeTrackID + '_pupilRipple',
                description = nsPupilDiameter_INFO['description'] +'({} eye'.format(eyeTrackID),
                comments = pupilDiameterComments + ' Data were recorded on Ripple System (chanName:' + nsPupilDiameter_INFO['chanName'] + ')',
                data = H5DataIO(pupil_h5["dataSet"]),
                starting_time = 0.0,
                rate = nsPupilDiameter_INFO['samplingRate'],
                unit = nsPupilDiameter_INFO['units'],
                conversion = nsPupilDiameter_INFO['convertionFactor'],
                )
            
            eyeData_h5paths.append(pupil_h5path)
            eyeData_h5objs.append(pupil_h5)

            if exists_PCEYE_containers:
                pupildiameter.add_timeseries(time_series=pupilNS)
            else:
                pupildiameter = PupilTracking(time_series=pupilNS)

            del pupilNS

            exists_nsPUPIL_tracking = True

    if exists_nsPUPIL_tracking or exists_PCEYE_containers:
        nwb_behavior_module.add(pupildiameter)

        del pupildiameter
    
    return eyeData_h5objs, eyeData_h5paths


###################################################################################################################
# Add ALL the analog INPUTS related to Stimuli (Except reward)
def nwb_add_nsAnalog_stimuli(nwbFile, dictYAML, nsFile,
                analogAccl=None, 
                analogFix=None, 
                analogVisualEvents=None, 
                analogTemp = None,
                verbose=False):
    
    analogStim_h5objs = []
    analogStim_h5paths = []

    # Extract Shaker Command and Accelerometer
    if analogAccl is not None:
        analogAccl['shakerInfo'] = yamlTools.expYAML.getTactorInfo(dictYAML)
        if analogAccl['exists']:
            shakerDict = {
                'leftCommand' : None, 
                'rightCommand' : None, 
                'leftAccelerometer' : analogAccl['shakerInfo']['leftAcclSensitivity'], 
                'rightAccelerometer' : analogAccl['shakerInfo']['rightAcclSensitivity']
                }
            for chanName, sensitivity in shakerDict.items():

                if verbose:
                    print('\nextracting Analog "{}" signal.............'.format(chanName))

                nsCommand = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName=chanName,
                                                        acclSensitivity=sensitivity)
                nsCommand_INFO = nsCommand.get_info()

                nsCommand_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsCommand_INFO['index']], 
                            tempName=chanName, 
                            itemCount=nsCommand_INFO['item_count'], 
                            verbose=verbose)
            
                nsCommand_h5 = h5py.File(name=nsCommand_h5path, mode="r")

                nwbFile.add_stimulus(TimeSeries(
                        name = nsCommand_INFO['chanName'],
                        description = nsCommand_INFO['description'],
                        data =  H5DataIO(nsCommand_h5["dataSet"]),
                        starting_time = 0.0,
                        rate = nsCommand_INFO['samplingRate'],
                        unit = nsCommand_INFO['units'],
                        conversion = nsCommand_INFO['convertionFactor'],
                        ))
                del nsCommand, nsCommand_INFO

                analogStim_h5objs.append(nsCommand_h5)
                analogStim_h5paths.append(nsCommand_h5path)

    if analogFix is not None:
        if analogFix['exists']:

            if verbose:
                    print('\nextracting Analog "fixON" signal............')

            nsCommand = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='fixON')
            nsCommand_INFO = nsCommand.get_info()

            nsCommand_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsCommand_INFO['index']], 
                            tempName='fixON', 
                            itemCount=nsCommand_INFO['item_count'], 
                            verbose=verbose)
            
            nsCommand_h5 = h5py.File(name=nsCommand_h5path, mode="r")
            
            nwbFile.add_stimulus(TimeSeries(
                name = nsCommand_INFO['chanName'],
                description = nsCommand_INFO['description'],
                data =  H5DataIO(nsCommand_h5["dataSet"]),
                starting_time = 0.0,
                rate = nsCommand_INFO['samplingRate'],
                unit = nsCommand_INFO['units'],
                conversion = nsCommand_INFO['convertionFactor'],
                ))
            
            del nsCommand, nsCommand_INFO

            analogStim_h5objs.append(nsCommand_h5)
            analogStim_h5paths.append(nsCommand_h5path)
    
    if analogVisualEvents is not None:
        if analogVisualEvents['exists']:

            if verbose:
                    print('\nextracting Analog "visualON" signal............')
            
            nsCommand = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='visualON')
            nsCommand_INFO = nsCommand.get_info()

            nsCommand_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsCommand_INFO['index']], 
                            tempName='visualON', 
                            itemCount=nsCommand_INFO['item_count'], 
                            verbose=verbose)
            
            nsCommand_h5 = h5py.File(name=nsCommand_h5path, mode="r")

            nwbFile.add_stimulus(TimeSeries(
                name = nsCommand_INFO['chanName'],
                description = nsCommand_INFO['description'],
                data =  H5DataIO(nsCommand_h5["dataSet"]),
                starting_time = 0.0,
                rate = nsCommand_INFO['samplingRate'],
                unit = nsCommand_INFO['units'],
                conversion = nsCommand_INFO['convertionFactor'],
                ))
            
            del nsCommand, nsCommand_INFO

            analogStim_h5objs.append(nsCommand_h5)
            analogStim_h5paths.append(nsCommand_h5path)

    if analogTemp is not None:

        if analogTemp['exists']:

            if verbose:

                print('\nextracting Thermistor signals............')

            temp_chanNames = []
            descriptionTemp = 'Thermistor descriptions:'
            itemsTempCount = 0
            tempInfoSet = False

            for tempID in analogTemp['thermistorIDs']:

                temp_chanNames.append(tempID)

                analogTemp_info = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName=tempID).get_info()

                if not tempInfoSet:

                    itemsTempCount = analogTemp_info['item_count']
                    rateTemp = analogTemp_info['samplingRate']
                    unitsTemp = analogTemp_info['units']
                    convFactorTemp = analogTemp_info['convertionFactor']

                    tempInfoSet = True
                
                descriptionTemp += '\n{}'.format(analogTemp_info['description'])

                del analogTemp_info

            
            nsCommand_h5path = constructorTools.temp_TimeSeries_hdf5_analog_cls(
                nsFile, 
                analog_chanNames = temp_chanNames, 
                tempName = 'thermistors',
                itemCount = itemsTempCount, 
                verbose=True)
                
            nsCommand_h5 = h5py.File(name=nsCommand_h5path, mode="r")

            nwbFile.add_stimulus(
                TimeSeries(
                    name = 'thermistors',
                    description = descriptionTemp,
                    data =  H5DataIO(nsCommand_h5["dataSet"]),
                    starting_time = 0.0,
                    rate = rateTemp,
                    unit = unitsTemp,
                    conversion = convFactorTemp,
                )
            )

            analogStim_h5objs.append(nsCommand_h5)
            analogStim_h5paths.append(nsCommand_h5path)
            

    return analogStim_h5objs, analogStim_h5paths

###################################################################################################################
# Add FootBar Aanalog signals and FootbarEvents.
def nwb_add_footData(nwbFile, nsFile,
                    analogFeet=None,
                    verbose = True):
    
    feet_h5objs = []
    feet_h5paths = []

    if analogFeet is not None:

        if analogFeet['exists']:
            if verbose:
                print('\nextracting Analog "FootBar" signal............')
            
            nsLeftFeet = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='leftFoot')
            nsLeftFeet_INFO = nsLeftFeet.get_info()
            nsRightFeet = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='rightFoot')
            nsRightFeet_INFO = nsRightFeet.get_info()

            feet_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[nsLeftFeet_INFO['index'], nsRightFeet_INFO['index']], 
                            tempName='FootBar', 
                            itemCount=nsLeftFeet_INFO['item_count'], 
                            verbose=verbose)
            
            feet_h5 = h5py.File(name=feet_h5path, mode="r")

            footBarPosition = Position(
                name='FootPosition',
                spatial_series = SpatialSeries(
                    name= 'LeftRight_footBar',
                    description = "(Left, Right) 5V signal wich indicates that subject's feet are not holding the footbar",
                    comments = nsLeftFeet_INFO['description'] + ' ' + nsRightFeet_INFO['description'],
                    data = H5DataIO(feet_h5["dataSet"]),
                    reference_frame = "0V indicates holding, 5V indicates release",
                    starting_time = 0.0,
                    rate = nsLeftFeet_INFO['samplingRate'],
                    unit = nsLeftFeet_INFO['units'],
                    conversion = nsLeftFeet_INFO['convertionFactor'],
                    )
                )
            
            nwbFile.processing['behavior'].add(footBarPosition)

            feet_h5objs.append(feet_h5)
            feet_h5paths.append(feet_h5path)

            ###############################################################
            # ADD FootBar Epochs/Intervals
            ###############################################################
            if verbose:
                print('\nextracting "FootBar" INTERVALS ............')
            
            dictFootEvents = constructorTools.get_feetEvents(nsFile, 
                            chunkSizeSecs = analogFeet['chunkSizeSecs'], 
                            showPlot = analogFeet['showPlot'])
            
            feet_events = TimeIntervals(
                name="feetEvents",
                description="intervals for each foot response: (release Left, release Right, release Both, hold Both)",
            )
            
            ###############################################################
            # first: add colum names
            feet_events.add_column(name='feetResponseID', description="Numerical-ID of the foot Response: [0, 1, 2, 3]")
            feet_events.add_column(name='feetResponse', description="Description of the foot Response: ['holdBoth', 'releaseLeft', 'releaseRight', 'releaseBoth']")
            
            ###############################################################
            # second: ADD FootEvents
            for n in range(len(dictFootEvents)):
                feet_events.add_row(**dictFootEvents[n])
            
            nwbFile.add_time_intervals(feet_events)
    
    return feet_h5objs, feet_h5paths

def nwb_add_rewardData(nwbFile, nsFile,
                analogReward=None,
                verbose = True):
    
    reward_h5objs = [] 
    reward_h5paths = []

    if analogReward is not None:
        if analogReward['exists']:
            if verbose:
                    print('\nextracting Analog "rewardON" signal............')

            analogReward_cls = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='rewardON')
            analogReward_cls_INFO = analogReward_cls.get_info()

            rw_h5path = constructorTools.temp_TimeSeries_hdf5(nsFile, 
                            entityIndexes=[analogReward_cls_INFO['index']], 
                            tempName='rewardON', 
                            itemCount=analogReward_cls_INFO['item_count'], 
                            verbose=verbose)
            
            rw_h5 = h5py.File(name=rw_h5path, mode="r")

            nwbFile.add_stimulus(TimeSeries(
                name = analogReward_cls_INFO['chanName'],
                description = analogReward_cls_INFO['description'],
                data = H5DataIO(rw_h5["dataSet"]),
                starting_time = 0.0,
                rate = analogReward_cls_INFO['samplingRate'],
                unit = analogReward_cls_INFO['units'],
                conversion = analogReward_cls_INFO['convertionFactor'],
                ))
            
            reward_h5objs.append(rw_h5) 
            reward_h5paths.append(rw_h5path)

            ###############################################################
            # ADD REWARD Epochs/Intervals
            ###############################################################
            if verbose:
                print('\nextracting "Reward" INTERVALS ............')

            analogReward_cls = rippleTools.AnalogIOchannel(nsFile=nsFile, chanName='rewardON')

            dictRewardEvents = constructorTools.get_rewardEvents(analogReward_cls, 
                            chunkSizeSecs = analogReward['chunkSizeSecs'], 
                            showPlot = analogReward['showPlot'])
            
            if len(dictRewardEvents)>0:
                            
                reward_events = TimeIntervals(
                    name="rewardEvents",
                    description=  "intervals when the reward was ON: (It is to include those times when the reward was delivered manually)",
                )
                
                ###############################################################
                # first: add colum names
                reward_events.add_column(name='label', description="Description of the reward event: rewardON")
                reward_events.add_column(name='labelID', description="Numerical-ID of the reward event: 1")
                
                
                ###############################################################
                # second: ADD FootEvents
                for n in range(len(dictRewardEvents)):
                    reward_events.add_row(**dictRewardEvents[n])
                
                nwbFile.add_time_intervals(reward_events)
    
    return reward_h5objs, reward_h5paths


def nwb_add_electrodeTable(nwbFile, dictYAML, nsFile, verbose=False):

    electrodesDict, electrodeGroups, devices = constructorTools.getNWB_rawElectrodes(dictYAML, nsFile, verbose=verbose)

    if verbose:
        print('\ncreating Electrode Devices ......')

    # create devices
    devicesList = []
    devicesNames = []
    for d in devices:
        devicesList.append(
            nwbFile.create_device(
                name= d['name'],
                description = d['description'],
                manufacturer = d['manufacturer']
                )
            )
        devicesNames.append(d['name'])

    if verbose:
        print('\ncreating Electrode Groups ......')
    
    elecGroupList=[]
    elecGroupList_id = []
    for g in electrodeGroups:
        elecGroupList.append(nwbFile.create_electrode_group(
            name = g['name'],
            description = g['description'],
            location = g['location'],
            device = devicesList[devicesNames.index(g['deviceName'])],
            position = g['position']
        ))
        elecGroupList_id.append(g['group_id'])

    # Create new column Names for ElectrodeTable
    #
    # nsKeys2keep = ['entity_type', 'entity_index', 'id', 'port_id', 'frontEnd_id', 'frontEnd_electrode_id',
    #     'units', 'item_count', 'sample_rate', 'resolution', 'probe_info',
    #     'high_freq_corner', 'high_freq_order', 'high_filter_type',
    #     'low_freq_corner', 'low_freq_order', 'low_filter_type',
    #     ]
    # ymlKeys2add = ['deviceName', 'device_id', 'location', 'rel_id',
    #     'x', 'y', 'z', 'rel_x', 'rel_y', 'rel_z',
    #     ]
    # default_NWBelectrodeColumnNames = ['x', 'y', 'z', 'imp', 'location', 'filtering', 'group', 'id',
    #     'rel_x', 'rel_y', 'rel_z', 'reference']
    
    columns2add = {
        'rel_id': 'Electrode ID within the electrode group / device',
        'frontEnd_electrode_id': 'Electrode ID within the FrontEnd where the device was connected',
        'frontEnd_id': "FrontEnd ID where the electrode's device was connected",
        'port_id': "Port ID where the electrode's FrontEnd was connected",
        'high_freq_corner': 'High pass filter corner frequency in Hz', 
        'high_freq_order': 'High pass filter order.', 
        'high_filter_type': "High pass filter type: None, Butterworth, Chebyshev",
        'low_freq_corner': 'Low pass filter corner frequency in Hz',
        'low_freq_order': 'Low pass filter order.', 
        'low_filter_type': "Low pass filter type: None, Butterworth, Chebyshev"
    }
    
    for key, value in columns2add.items():
        nwbFile.add_electrode_column(
            name = key,
            description = value
        )
    
    if verbose:
        print('\ncreating Electrode Table ......')

    for e in electrodesDict:
        nwbFile.add_electrode(
            group = elecGroupList[elecGroupList_id.index(e['group_id'])], 
            id = e['id'], 
            rel_id = e['rel_id'],
            frontEnd_electrode_id = e['frontEnd_electrode_id'],
            frontEnd_id = e['frontEnd_id'],
            port_id = e['port_id'],
            x = e['ap'], 
            y = e['dv'], 
            z = e['ml'], 
            imp = None, 
            location = e['location'], 
            filtering = None, 
            rel_x = e['rel_ap'], 
            rel_y = e['rel_dv'], 
            rel_z = e['rel_ml'], 
            reference = None,
            high_freq_corner = e['high_freq_corner'], 
            high_freq_order = e['high_freq_order'], 
            high_filter_type = e['high_filter_type'],
            low_freq_corner = e['low_freq_corner'],
            low_freq_order = e['low_freq_order'], 
            low_filter_type = e['low_filter_type']
        )

def nwb_add_rawElectrode(nwbFile, nsFile, dictYAML, verbose=False):

    if nwbFile.electrodes is None:
        nwb_add_electrodeTable(nwbFile, dictYAML, nsFile, verbose=verbose)
    
    electrodesDict, _, _ = constructorTools.getNWB_rawElectrodes(dictYAML, nsFile, verbose=False)

    print('\nAdding Neural Data...\n')

    electrodes_h5objs = []
    electrodes_h5paths = []

    for i in range(len(electrodesDict)):

        e = electrodesDict[i]
        e_h5path = constructorTools.temp_TimeSeries_hdf5(
                                nsFile = nsFile, 
                                entityIndexes= [e['entity_index']], 
                                tempName= '{}{}-{}-raw{}'.format(
                                    e['port_id'], 
                                    e['frontEnd_id'], 
                                    e['frontEnd_electrode_id'], 
                                    e['id']
                                    ), 
                                itemCount= int(e['item_count']),
                                verbose = verbose,
                    )

        e_h5 = h5py.File(name=e_h5path, mode="r")

        electrodes_h5objs.append(e_h5)
        electrodes_h5paths.append(e_h5path)
        
        if e['units']=='mV':
            convertion2V = 1/1000
        elif e['units']=='V':
            convertion2V = 1.0
        elif e['units']=='uV':
            convertion2V = 1/1000000


        nwbFile.add_acquisition(
            ElectricalSeries(
                name = 'raw-{}{}-{}-{}'.format(e['port_id'], e['frontEnd_id'], e['frontEnd_electrode_id'], e['id']),
                data = H5DataIO(e_h5["dataSet"]),
                electrodes = DynamicTableRegion(name='electrodes', data=[i], description=e['probe_info'], table=nwbFile.electrodes),  
                filtering = '{} HighFreq Filter (order:{}, freq-corner:{}); {} LowFreq Filter (order:{}, freq-corner:{})'.format(
                        e['high_filter_type'], e['high_freq_order'], e['high_freq_corner'],
                        e['low_filter_type'], e['low_freq_order'], e['low_freq_corner']
                        ), 
                resolution=e['resolution']*convertion2V, 
                conversion=convertion2V,  
                starting_time=0.0, 
                rate=e['sample_rate'], 
                comments='This ElectricalSeries corresponds to the raw neural data collected with Trellis software (Ripple)', 
                description=e['probe_info']
            ))
        
    return electrodes_h5objs, electrodes_h5paths

def nwb_add_rawElectrodeGroup(nwbFile, nsFile, dictYAML, verbose=False):

    if nwbFile.electrodes is None:
        nwb_add_electrodeTable(nwbFile, dictYAML, nsFile, verbose=verbose)
    
    electrodesDict, electrodeGroups, _ = constructorTools.getNWB_rawElectrodes(dictYAML, nsFile, verbose=False)

    print('\nAdding Neural Data...\n')

    electrodeGroups_h5objs = []
    electrodeGroups_h5paths = []

    for eg in electrodeGroups:

        group_h5path, groupInfo = constructorTools.create_rawElectrodeGroup_hdf5(electrodesDict, nsFile, 
                                                                groupID=eg['group_id'], verbose=True)

        if verbose:
            print('Importing..... : raw signal from {}\n'.format(eg['name']))

        group_h5 = h5py.File(name=group_h5path, mode="r")

        if groupInfo['units']=='mV':
            convertion2V = 1/1000
        elif groupInfo['units']=='V':
            convertion2V = 1.0
        elif groupInfo['units']=='uV':
            convertion2V = 1/1000000

        nwbFile.add_acquisition(
            ElectricalSeries(
                name = 'raw-{}'.format(eg['name']),
                data = H5DataIO(group_h5["dataSet"]), 
                electrodes = DynamicTableRegion(name='electrodes', data=groupInfo['electrode_index'], 
                                                description=eg['name'], table=nwbFile.electrodes),  
                filtering = '{} HighFreq Filter (order:{}, freq-corner:{}); {} LowFreq Filter (order:{}, freq-corner:{})'.format(
                        groupInfo['high_filter_type'], groupInfo['high_freq_order'], groupInfo['high_freq_corner'],
                        groupInfo['low_filter_type'], groupInfo['low_freq_order'], groupInfo['low_freq_corner']
                        ), 
                resolution=groupInfo['resolution']*convertion2V, 
                conversion=convertion2V,  
                starting_time=0.0, 
                rate=groupInfo['sample_rate'], 
                comments='This ElectricalSeries corresponds to the raw neural data collected with Trellis software (Ripple)', 
                description=eg['description']
            ))
        
        electrodeGroups_h5objs.append(group_h5)
        electrodeGroups_h5paths.append(group_h5path)
    
    return electrodeGroups_h5objs, electrodeGroups_h5paths
        

def nwb_add_stimElectrodesWaveForms(nwbFile, nsFile, dictYAML, verbose=False):

    if nwbFile.electrodes is None:
        nwb_add_electrodeTable(nwbFile, dictYAML, nsFile, verbose=verbose)
    
    electrodesDict, _, _ = constructorTools.getNWB_rawElectrodes(dictYAML, nsFile, verbose=False)
    stimElectrodes = rippleTools.get_stimElectrodeInfo(nsFile)

    for i in range(len(stimElectrodes)):

        indexElec = [e for e in range(len(electrodesDict)) if electrodesDict[e]['id']==stimElectrodes[i]['id']]

        if len(indexElec)==0:
            raise Exception('Electrode {} was not found in ElectrodeTable, \nElectrodes ID in Table: \n'.format(
                stimElectrodes[i]['id'], [e['id'] for e in electrodesDict]
                ))
        elif len(indexElec)>1:
            raise Exception('Electrode {} was found more than once in ElectrodeTable, \n Verify Electrodes ID in Table: \n'.format(
                stimElectrodes[i]['id'], [e['id'] for e in electrodesDict]
                ))
            
        # print(electrodesDict[indexElec[0]], '\n')

        chanStim = rippleTools.SegmentStimChannel(nsFile=nsFile, electrode_id=stimElectrodes[i]['id'])
        chanStimInfo = chanStim.get_info()

        if verbose:
            print('\nExtracting microStimulation Waveforms..... : stim-{}{}-{}-{}'.format(
                chanStimInfo['port_id'], chanStimInfo['frontEnd_id'], chanStimInfo['frontEnd_electrode_id'], chanStimInfo['id']
                ))
            
        if chanStimInfo['units']=='mV':
            convertion2V = 1/1000
        elif chanStimInfo['units']=='V':
            convertion2V = 1.0
        elif chanStimInfo['units']=='uV':
            convertion2V = 1/1000000

        # print(chanStimInfo, '\n')

        data = chanStim.get_data(index=range(chanStimInfo['item_count']), verbose=verbose)

        nwbFile.add_stimulus(SpikeEventSeries(
            name='stim-{}{}-{}-{}'.format(chanStimInfo['port_id'], chanStimInfo['frontEnd_id'], chanStimInfo['frontEnd_electrode_id'], chanStimInfo['id']),
            # data = data['waveForms'], 
            # timestamps = data['timeStamps'], 
            data = H5DataIO( data=data['waveForms'], compression = True), 
            timestamps = H5DataIO( data=data['timeStamps'], compression = True), 
            electrodes = DynamicTableRegion(name='electrodes', 
                                            data=indexElec, 
                                            description='This is channel {} ({})'.format(chanStimInfo['id'], chanStimInfo['label_id']), 
                                            table=nwbFile.electrodes),  
            resolution=chanStimInfo['resolution']*convertion2V, 
            conversion=convertion2V, 
            comments="This SpikeEventSeries corresponds to the electrical microstimulation Waveforms delivered through this electrode\nFurther details in Trellis software documentation from Ripple", 
            description= "Microstimulation waveforms from electrode {} ({}).\nSamples per Waveform: [min={}, max={}]\nOriginal amplitude units: {}\nAmplitude Range: [min={}, max={}]".format(
                chanStimInfo['id'], chanStimInfo['probe_info'], chanStimInfo['min_sample_count'], chanStimInfo['max_sample_count'], 
                chanStimInfo['units'], chanStimInfo['min_val'], chanStimInfo['max_val']
                ), 
            control=None, 
            control_description=None, 
            offset=0.0
            ))

##############################################################################################################
#                               CREATE NWB ¡¡¡¡¡
##############################################################################################################
def createNWBfile(filePathYAML=None, 
            Stimulus_Notes=None, KeywordExperiment=None, Experimenters=None, Experiment_Description=None, related_publications=None,
            analogEye = None, analogAccl=None, analogFix=None, analogVisualEvents=None, analogFeet=None, analogReward=None, analogTemp=None,
            TimeZone=None, process_INdisk=True, raw_by_ElectrodeGroup = True, verbose=True):
    
    if verbose:
        computing_start_time = time.time()

    if TimeZone is None:
        TimeZone = yamlTools.labInfo['LabInfo']['TimeZone']

    if filePathYAML is None:
        filePathYAML = askopenfilename(
        title = 'Select a YAML file to extract',
        filetypes =[('yaml Files', '*.yaml')])
                
    if not os.path.isfile(filePathYAML):

        raise Exception("YAML-file-Path : {} doesn't exist ".format(filePathYAML))
    
    
    #################################################################################################
    # Check folderSession 
    folder_save, folder_read, fileName = check_folderSession(filePathYAML, copy2disk=process_INdisk)

    # Check compatible with Temp:
    tempCompatible = check_temp_date(fileName=fileName)
    if not tempCompatible:
        analogTemp = None

    if verbose:
        print('\n... loading YAML file {} into python-dictionary..... \n'.format(fileName))

    filePath = os.path.join(folder_read, fileName)

    orig_stdout = sys.stdout
    orig_sterr = sys.stderr

    fOutputs = open(filePath + '-logOut.txt', 'w')
    
    sys.stdout = Unbuffered(orig_stdout, fOutputs)
    sys.stderr = sys.stdout

    dictYAML = yamlTools.yaml2dict(filePath +'.yaml', verbose=False)
    session_start_time_YAML = yamlTools.expYAML.getStartDateTime(dictYAML, TimeZone)

    if not os.path.isfile(filePath +'.nev'):

        nsFile = None
        session_start_time = session_start_time_YAML
        extNWB = '-noNEV'

        # If there is no NEV file, it is assume that Analog signals were not recorded. 
        # Set all analogs to None to avoid any attempt to extract signals
        analogAccl=None
        analogFix=None
        analogVisualEvents=None
        analogFeet=None
        analogReward=None
        analogTemp=None

    else:
        nsFile = rippleTools.get_nsFile(filePath +'.nev')
        session_start_time = rippleTools.getNS_StartDateTime(nsFile, TimeZone)
        extNWB = ''

    ###############################################################
    #            CREATE Session & Experimental Metadata
    ###############################################################
    sessionInfo = yamlTools.expYAML.getSessionInfo(dictYAML,
                                        session_start_time = session_start_time,
                                        session_id = None, # Default: it will be extracted from dictYAML
                                        session_description = None, # Default: it will be extracted from dictYAML
                                        identifier=None # Default: it will be created automatically
                                        )

    sessionInfo.update(yamlTools.expYAML.getExperimentInfo(dictYAML, 
                            lab=None, # it will be extracted from MonkeyInfo or dictYAML
                            institution=None, # it will be extracted from MonkeyInfo or dictYAML
                            protocol=None, # it will be extracted from MonkeyInfo or dictYAML
                            experiment_description=Experiment_Description, # Default: it will be extracted from dictYAML
                            surgery = None, # it will be extracted from MonkeyInfo
                            experimenter = Experimenters, # It has to be an input
                            stimulus_notes = Stimulus_Notes, # It has to be an input
                            notes = None, # not in use
                            keywords = KeywordExperiment, # It has to be an input
                            related_publications = related_publications  # It has to be an input
                        ))
    
    ###############################################################
    #                       START NWB-file
    ###############################################################
    nwbfile = NWBFile(**sessionInfo)
    
    ###############################################################
    #                        ADD MODULES
    ###############################################################
    # behavior module
    behavior_module = nwbfile.create_processing_module(
        name="behavior", description="processed behavioral data"
        )
    
    ###############################################################
    #                   ADD Subject Info
    ###############################################################
    nwbfile.subject = Subject(**yamlTools.expYAML.getSubjectInfo(dictYAML, 
                            subject_id=None, # it will be extracted from MonkeyInfo or dictYAML
                            description=None, # it will be extracted from MonkeyInfo or dictYAML
                            sex=None, # it will be extracted from MonkeyInfo or dictYAML
                            species=None, # it will be extracted from MonkeyInfo or dictYAML
                            date_of_birth=None, # it will be extracted from MonkeyInfo or dictYAML
                            age=None # not use it
                        ))
    
    ###############################################################
    #            ADD Shaker device Info
    ###############################################################
    shakerInfo = yamlTools.expYAML.getTactorInfo(dictYAML)
    shakerDevice = Device(
        name= 'tactor',
        description = '{} - Model: {} - Number: {}'.format(
            shakerInfo['device']['Description'], 
            shakerInfo['device']['Model'], 
            shakerInfo['device']['ModelNumber']
            ),
        manufacturer = '{} - website: {}'.format(
            shakerInfo['device']['Company'], 
            shakerInfo['device']['Website'])
            )

    nwbfile.add_device(shakerDevice)

    ###############################################################
    #                  ADD TRIALS
    ###############################################################
    # first: add colum names
    for n, d in yamlTools.expYAML.getTrialColNames(dictYAML, analogTemp=analogTemp).items():
        if (n != 'start_time') and (n != 'stop_time'):
            nwbfile.add_trial_column(name=n, description=d)

    # second: GET TRIALS NEV
    trialsNWB_NEV = constructorTools.getNWB_trials(
        dictYAML=dictYAML, 
        nsFile=nsFile, 
        analogAccl=analogAccl, 
        analogFix=analogFix, 
        analogVisualEvents=analogVisualEvents,
        analogTemp = analogTemp,
        verbose=False)
    
    # last: ADD TRIALS
    for n in range(len(trialsNWB_NEV)):
        nwbfile.add_trial(**trialsNWB_NEV[n])

    del trialsNWB_NEV

    ###############################################################
    #                    ADD Eye DATA
    ############################################################### 
    eyeData_h5objs, eyeData_h5paths = nwb_add_eyeData(
        nwb_behavior_module=behavior_module, 
        filePath=filePath, 
        dictYAML=dictYAML, 
        nsFile=nsFile,
        analogEye = analogEye,
        eyeTrackID=analogEye['eyeTrackID'],
        eyeXYComments=analogEye['eyeXYComments'],                    
        pupilDiameterComments = analogEye['pupilDiameterComments'],
        verbose = True          
    )

    ###############################################################
    #                    ADD Foot DATA
    ############################################################### 
    if nsFile is not None:
        feet_h5objs, feet_h5paths = nwb_add_footData(
            nwbFile=nwbfile,
            nsFile=nsFile,
            analogFeet=analogFeet,
            verbose = True
        )

    ###############################################################
    #                    ADD Reward DATA
    ############################################################### 
    if nsFile is not None:
        reward_h5objs, reward_h5paths = nwb_add_rewardData(
            nwbFile=nwbfile,
            nsFile=nsFile,
            analogReward = analogReward,
            verbose = True
        )

    ###############################################################
    #               Add Analog Stimuli
    ###############################################################
    if nsFile is not None:
        analogStim_h5objs, analogStim_h5paths = nwb_add_nsAnalog_stimuli(
            nwbFile = nwbfile, 
            dictYAML = dictYAML,
            nsFile = nsFile,     
            analogAccl = analogAccl, 
            analogFix = analogFix, 
            analogVisualEvents = analogVisualEvents, 
            analogTemp = analogTemp,
            verbose = True
        )

    ###############################################################
    #       Add Raw Neural Signal
    ###############################################################
    if nsFile is not None:
        if raw_by_ElectrodeGroup:
            ###############################################################
            #       dataset per ElectrodeGroup
            ###############################################################
            electrodes_h5objs, electrodes_h5paths = nwb_add_rawElectrodeGroup(
                nwbFile = nwbfile, 
                nsFile = nsFile,
                dictYAML = dictYAML,
                verbose = True
            )
        else:
            ###############################################################
            #       dataset channel by channel
            ###############################################################
            electrodes_h5objs, electrodes_h5paths = nwb_add_rawElectrode(
                nwbFile = nwbfile, 
                dictYAML = dictYAML,
                nsFile = nsFile,
                verbose = True
            )

    ###############################################################
    #         Add Electrical MicroStimulation Waveforms
    ###############################################################
    if nsFile is not None:
        nwb_add_stimElectrodesWaveForms(
            nwbFile = nwbfile, 
            dictYAML = dictYAML, 
            nsFile = nsFile,
            verbose=True)

    ###############################################################
    #                    Write file
    ###############################################################
    nwbFilePath = os.path.join(filePath + extNWB + '.nwb')
    with NWBHDF5IO(nwbFilePath, "w") as io:
        if verbose:
            print('\nwriting NWB file..........')
        io.write(nwbfile)
    
    ###############################################################
    #       Close and delete hdf5 temporal files
    ###############################################################
    if verbose:
        print('\ndeleting Temprary HDF5 files..........')
    # EYE DATA
    for f in eyeData_h5objs:
        f.close()
    for f in eyeData_h5paths:
        os.remove(f)
    
    if nsFile is not None:
        # FEET DATA
        for f in feet_h5objs:
            f.close()
        for f in feet_h5paths:
            os.remove(f)
        # REWARD DATA
        for f in reward_h5objs:
            f.close()
        for f in reward_h5paths:
            os.remove(f)
        # ANALOG STIM
        for f in analogStim_h5objs:
            f.close()
        for f in analogStim_h5paths:
            os.remove(f)            
        # RAW ELECTRODE GROUPS
        for f in electrodes_h5objs:
            f.close()
        for f in electrodes_h5paths:
            os.remove(f)

    ###############################################################
    #              RUN nwbInspector
    ###############################################################
    resultsInspector = list(inspect_nwbfile(nwbfile_path=nwbFilePath))
    
    if len(resultsInspector)==0:
        print("congrats¡ no NWB inspector comments\n")
    else:
        print('\nNWB inspector comments:\n')
        for r in resultsInspector:
            print('Message : ', r.message)
            print('Object Name : ',r.object_name)
            print('Object Type : ',r.object_type)
            print('Severity : ',r.severity)
            print('Importance : ', r.importance, '\n')


    print("\nNWB file was successfully created¡¡\n{}\n\n".format(fileName + extNWB + '.nwb'))

    ###############################################################
    #         MOVE NWB into the original Path
    ###############################################################
    if folder_save!=folder_read:
        if verbose:
            print('\nmoving NWB into the original directory : {}\n\n'.format(folder_save))
        shutil.move(os.path.join(folder_read, fileName + extNWB + '.nwb'), 
                    os.path.join(folder_save, fileName + extNWB + '.nwb'), 
                    copy_function = shutil.copy2)
    
    if verbose:
        print('\nNWB creation took {} min\n\n'.format((time.time()-computing_start_time)/60))

    #sys.stdout = orig_stdout
    sys.stdout = orig_stdout
    sys.stderr = orig_sterr
    fOutputs.close()


    if folder_save!=folder_read:
        if verbose:
            print('\nmoving logOut into the original directory : {}\n\n'.format(folder_save))
        shutil.move(os.path.join(folder_read, fileName + '-logOut.txt'), 
                    os.path.join(folder_save, fileName + '-logOut.txt'), 
                    copy_function = shutil.copy2)

    constructorTools.clear_NWBtempdir()