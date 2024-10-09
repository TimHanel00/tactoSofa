Warning this project currently only supports nvidia grafix cards.


Ensure x11 forwarding permissions
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
