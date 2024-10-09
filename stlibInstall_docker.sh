#!/bin/bash
set -x
export REPO=/home/user
export SOFA_ROOT=/home/user/sofa/SOFA_v22.12.00_Linux
export PYTHONPATH=$SOFA_ROOT/plugins/SofaPython3/lib/python3/site-packages:$PYTHONPATH
echo "in here"
cd stlib
#rm -r build
mkdir -p build && cd build
echo "Running cmake..."
source /opt/conda/etc/profile.d/conda.sh
conda activate robot_learning
cmake -DCMAKE_PREFIX_PATH:=$SOFA_ROOT -DPLUGIN_SOFAPYTHON=ON -DSOFA_BUILD_METIS=ON .. >> /dev/stdout 2>> /dev/stderr
echo "Building project..."
cmake --build . >> /dev/stdout 2>> /dev/stderr

