#!/bin/bash

# Source the conda setup script
source /opt/conda/etc/profile.d/conda.sh

# Activate the conda environment
conda activate robot_learning

# Setup environment variables
export REPO=/home/user
export PYTHONPATH=$REPO/stlib/build/lib/python3/site-packages:$PYTHONPATH
export PYTHONPATH=$REPO/nonrigid/src:$PYTHONPATH
export SOFA_ROOT=$REPO/sofa/SOFA_v22.12.00_Linux
export PYTHONPATH=$SOFA_ROOT/plugins/SofaPython3/lib/python3/site-packages:$PYTHONPATH

# Print environment variables for debugging
echo "Python PATH: $PYTHONPATH"
echo "PATH: $PATH"
echo "SOFA_ROOT: $SOFA_ROOT"

# Check if the script argument is provided
if [ -z "$1" ]; then
    echo "No script provided. Exiting."
    exit 1
fi
conda activate robot_learning
# Execute the Python script with the provided argument
python "$1"
