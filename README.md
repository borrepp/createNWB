# createNWB

Compile YAU-lab native files (*.yaml, *.eye, ripple-*.nev, ripple-*.nsX) into an NWB format

It requires python 3.8 (https://www.python.org/downloads/release/python-383/)
> [!NOTE]
> only tested on Windows

## Setup the environment
### Create the environment
Open a new terminal and create a virtual environment:
```
py -3.8 -m virtualenv desiredFolder\NWBenv -p python3.8
```

Activate the environment
```
desiredFolder\NWBenv\Scripts\Activate
```

### Install libraries
* NWB and YAML 
```
python -m pip install PyYAML
python -m pip install -U pynwb
python -m pip install nwbinspector
```

* Ripple library

  It requires python library for reading *.nev and *nsX files.<br />
  >Email Ripple support _support@jessimischel.zendesk.com_ to get the folder _"pyns3_beta"_
  
  Once you get the folder, copy the folder into:
  >desiredFolder\NWBenv\Lib\site-packages\

  Install pyns3_beta from main
  ```
  cd desiredFolder\NWBenv\Lib\site-packages\pyns3_beta
  python -m pip install -e .
  ```


## How to use

In process of revision how to use this first version
