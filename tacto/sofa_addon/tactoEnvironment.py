
import cv2
import hydra
import pybullet as p
import pybulletX as px
import trimesh
import pyrender
from stl import mesh
import numpy as np
import tacto
import threading
import logging
from time import sleep
from tacto.sofa_addon.dataTransport import TransportData,DataReceiver,Sender
log = logging.getLogger(__name__)

def stlToPyrenderMesh(meshfile):
    stl_mesh = mesh.Mesh.from_file(meshfile)

    trimesh_mesh = trimesh.Trimesh(vertices=stl_mesh.vectors.reshape(-1, 3),
                                faces=np.arange(len(stl_mesh.vectors) * 3).reshape(-1, 3))
    pyrender_mesh = pyrender.Mesh.from_trimesh(trimesh_mesh)
def setupSendToSofa(dataSender,digits):
    for cam_name,obj_name,cam_urdf in digits.sensor_objects:
        cam_mesh=None
        position, orientation=digits.cameras[cam_name].get_pose(digits.dataReceiver)
        obj_id=digits.cameras[cam_name].obj_id
        for link in cam_urdf.links:
            for visual in link.visuals:
                pose = visual.origin
                cam_mesh=visual.geometry.mesh.filename
                log.info(cam_mesh)
        dataSender.init_object(name=obj_name,id=obj_id,pos=position,orientation=orientation,forces=0.0,mesh=cam_mesh)
    
    for obj_name in digits.scene_objects:
        obj_urdf=digits.scene_objects[obj_name]
        obj_mesh=None
        for link in obj_urdf.links:
            for visual in link.visuals:
                pose = visual.origin
                obj_mesh=visual.geometry.mesh.filename
        position, orientation=digits.objects[obj_name].get_pose(digits.dataReceiver)
        obj_id=digits.objects[obj_name].obj_id
        dataSender.init_object(name=obj_name,id=obj_id,pos=position,orientation=orientation,forces=-1.0,mesh=obj_mesh)
    
def tactoLoop(digits,dataReceive):
    while True:
        #print(dataReceive.get())
        
        color, depth = digits.render()
        digits.updateGUI(color, depth)
def tactoLaunch(connectors,digits):
    toSofa,fromSofa=connectors
    dataReceive=DataReceiver(fromSofa)
    dataSender=Sender(toSofa)
    # Load the config YAML file from examples/conf/digit.yaml

        # Initialize digits
    bg = cv2.imread("conf/bg_digit_240_320.jpg")
    digits.setDataReceiver(dataReceive)
    digits.init_renderer()
    # Initialize World
    log.info("Initializing world")
    px.init()
    digits.run_resetDebugVisualizerCamera()

    # Create and initialize DIGIT
    digits.init_camera()

    # Add object to pybullet and tacto simulator
    digits.init_objects()
    
    setupSendToSofa(dataSender,digits)
    from time import sleep
    dataSender.start()
    sleep(1)
    dataSender.stop()
    # Create control panel to control the 6DoF pose of the object
    #panel = px.gui.PoseControlPanel(obj, **cfg.object_control_panel)
    #panel.start()
    #log.info("Use the slides to move the object until in contact with the DIGIT")
    dataReceive.start()
    # run p.stepSimulation in another thread
    t = px.utils.SimulationThread(real_time_factor=1.0)
    t.start()
    thread = threading.Thread(target=tactoLoop, args=(digits,dataReceive,))
    thread.start()
    thread.join()
    dataReceive.join()
    dataSender.join()
