#This Repo Repository aims to provide soft tissue behaviour for DIGIT tactile sensor Simulations.
##Installation
this is a pure docker Installation -- for a Installation on your local System refer to README.md
ensure your nvidia and cuda drivers are installed:
check 
```
nvidia-smi
```
Ensure x11 forwarding permissions for docker are set (and X11 installed on your system)
```
xhost +SI:localuser:root
xhost +SI:localuser:$(whoami)
```

Make docker nvidia driver compatible

```
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
```
apply changes
```
sudo systemctl restart docker
```

##Build
```
chmod +x ./build.sh
./build.sh
```
builds the dockerImage and all its dependencies including sofa, tacto, nonrigid-repository (for mesh data generation) ...

##Run 
 
```
chmod +x ./sofaTacto.sh
export 
./sofaTacto.sh --python_filename -- for example
./sofaTacto.sh examples/sofa_examples/robot_learning_main.py
```

