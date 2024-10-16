# Copyright (c) Facebook, Inc. and its affiliates.

# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import collections
import logging
import os
import warnings
from dataclasses import dataclass

import cv2
import numpy as np
import pybullet as p
import trimesh
from urdfpy import URDF
import pyrender
import pybulletX as px
from .renderer import Renderer
from typing import List
logger = logging.getLogger(__name__)


def _get_default_config(filename):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)


def get_digit_config_path():
    return _get_default_config("config_digit.yml")


def get_digit_shadow_config_path():
    return _get_default_config("config_digit_shadow.yml")


def get_omnitact_config_path():
    return _get_default_config("config_omnitact.yml")

def swap(l1,i,l2,j):
    tmp=l1[i]
    l1[i]=l2[j]
    l2[j]=tmp
def degtoRad(angle):
    import math
    return angle*math.pi/180
def register(linkobj,dataReceive):
    if linkobj.sofaName=="":
            for obj in dataReceive.get().tolist():
                if obj.name=="Tissue" and linkobj.obj_id==2:
                    linkobj.sofaName=obj.name
                if obj.name=="Sensor" and linkobj.link_id==-1 and linkobj.obj_id==1:
                    linkobj.sofaName=obj.name
def getSofaName(linkobj):
    if linkobj.link_id==-1 and linkobj.obj_id==1:
        return "Sensor"
    if linkobj.obj_id==2:
        return "Tissue"
    return ""
def equalArray(ar1,ar2):
    for i in range(len(ar1)):
        if ar1[i] != ar2[i]:  # Compare elements at the same index
            return False
    return True
def tissueHandle(link,sofaObject):
    pos=sofaObject.position
    new_pos=[pos[0],pos[1],pos[2]]
    new_pos[2]+=2.0
    orient=[degtoRad(i) for i in sofaObject.orientation]
    if sofaObject.mesh is not None:
        #print("updatingMesh")
        link.mesh=sofaObject.mesh
        
        #print(self.mesh)
        vertices = sofaObject.mesh.vertices.tolist()  # Convert to list
        indices = sofaObject.mesh.faces.flatten().tolist()     # Convert to list
        #print(vertices)
        #print(indices)
        new_visual_shape = p.createVisualShape(
            shapeType=p.GEOM_MESH, 
            vertices=vertices, 
            indices=indices
        )
        new_collision_shape = p.createCollisionShape(shapeType=p.GEOM_MESH, vertices=vertices, 
            indices=indices)
        old_id=link.pybullet_id

        link.pybullet_id = p.createMultiBody(basePosition=new_pos,baseOrientation=orient,baseVisualShapeIndex=new_visual_shape, baseCollisionShapeIndex=new_collision_shape)
        
        
        p.removeBody(old_id)
    if link.cam_name is not None:
        link.oldlinkForces=link.force  
        
        if link.force is None or link.force<1e-5:

            link.force=link.oldlinkForces
        comparray=pos+orient
        if len(link.lastPos)>0 and not equalArray(link.lastPos,comparray):

            p.resetBasePositionAndOrientation(link.pybullet_id, new_pos, p.getQuaternionFromEuler(orient))
        link.force =0.0
    from time import sleep
    #sleep(0.01)         
    
    return new_pos,orient 
def sensorHandle(link,sofaObject,pos,orient):
    link.force=sofaObject.forces
    p.resetBasePositionAndOrientation(link.obj_id, pos, p.getQuaternionFromEuler(orient))
    return pos,orient
def default(link,sofaObject,pos,orient):
    return pos,orient
costumFctDict={"Sensor":sensorHandle,"Tissue":tissueHandle,"":default}
@dataclass
class Link:
    obj_id: int  # ID used for Tacto (pyrender and initially pybullet)
    link_id: int  # pybullet link ID (-1 means base)
    cid: int  # physicsClientId
    name:str
    internalPos=None
    internalRot=None
    initSofaPos=None
    lastPos=[]
    oldlinkForces=0.0
    force=None
    mesh=None
    cam_name=None
    sofaName=""
    pybullet_id: int #ID used explicitly for pybullet
    def __init__(self,obj_id,link_id,cid,cam_name=None):
        self.obj_id=obj_id
        self.link_id=link_id
        self.cid=cid
        self.cam_name=cam_name
        self.pybullet_id=self.obj_id
        self.name="{}_{}".format(obj_id, link_id)

    def get_pose(self,dataReceive=None):
        global costumFctDict
        
        #for k,v in dic:
            #print(v)
        p.setRealTimeSimulation(0)
        if self.link_id < 0:
            # get the base pose if link ID < 0
            position, orientation = p.getBasePositionAndOrientation(
                self.pybullet_id, physicsClientId=self.cid
            )
        else:
            # get the link pose if link ID >= 0
            position, orientation = p.getLinkState(
                self.pybullet_id, self.link_id, physicsClientId=self.cid
            )[:2]

        orientation = p.getEulerFromQuaternion(orientation, physicsClientId=self.cid)
        if self.internalPos==None and self.internalRot==None:
            self.internalPos=position
            self.internalRot=orientation
        
        #print(f'{self.link_id}+ obj Id: {self.obj_id}')
        """
        if( is digit sensor):
        
        
        print(dataReceive.latest_data)
        for i in range(3):
            dataReceive.latest_data.position[i]*=10
        """  
            
        #print(dataReceive.get())
        #print(position,orientation)
        #return dataReceive.get().position,dataReceive.get().orientation
        #print(str(position)+ " 1")
        pos=None
        orient=None
        import time  
        if dataReceive==None:
            #print("receiveNone")
            return position, orientation
        if dataReceive.latest_data is None:
            #print("receiveDataNone")
            return position, orientation
        if self.name not in dataReceive.latest_data.getDict():
            return position, orientation

        obj =dataReceive.latest_data.getDict()[self.name]
        pos,orient=tissueHandle(self,obj)
        self.lastPos=pos+orient

        return pos,orient
class setupObject:
    def __init__(self,**params):
        self.params=params
class setupCamera:
    def __init__(self,linkIds,**params):
        self.params=params
        self.linkIds=linkIds
class Setup:
    setup_camera: setupCamera
    setup_objects: List[setupObject]
    reset_params = None

    def __init__(self):
        self.setup_objects = []

    def resetDebugVisualizerCamera(self, **params):
        self.reset_params = params

    def add_camera(self, linkIds, **params):
        self.setup_camera = setupCamera(linkIds, **params)

    def add_object(self, **params):
        self.setup_objects.append(setupObject(**params))


class Sensor:
    def __init__(
        self,
        width=120,
        height=160,
        background=None,
        config_path=get_digit_config_path(),
        visualize_gui=True,
        show_depth=True,
        zrange=0.002,
        cid=0,
        dataReceive=None
    ):
        """

        :param width: scalar
        :param height: scalar
        :param background: image
        :param visualize_gui: Bool
        :param show_depth: Bool
        :param config_path:
        :param cid: Int
        """
        self.setup=Setup()
        self.scene_objects={}
        self.sensor_objects=[]
        self.cid = cid
        self.renderer=None
        self._width=width
        self._height=height
        self._background=background
        self.config_path=config_path
        self.visualize_gui = visualize_gui
        self.show_depth = show_depth
        self.zrange = zrange
        self.dataReceiver=dataReceive
        self.cameras = {}
        self.nb_cam = 0
        self.objects = {}
        self.object_poses = {}
        self.normal_forces = {}
        self._static = None

    @property
    def height(self):
        return self._height

    @property
    def width(self):
        return self._width

    @property
    def background(self):
        return self._background
    def setDataReceiver(self,receiver):
        self.dataReceiver=receiver
    def add_camera(self, link_ids,**params):
        """
        Add camera into tacto

        self.cameras format: {
            "cam0": Link,
            "cam1": Link,
            ...
        }
        """
        self.setup.add_camera(link_ids,**params)
    def init_renderer(self):
        self.renderer=Renderer(self._width, self._height, self._background, self.config_path)
    def init_camera(self):
        pxBody=px.Body(**self.setup.setup_camera.params)
        link_ids=self.setup.setup_camera.linkIds
        urdf=URDF.load(pxBody.urdf_path)
        logger.info(pxBody.urdf_path)
        obj_id=pxBody.id
        
        
        if not isinstance(link_ids, collections.abc.Sequence):
            link_ids = [link_ids]

        for link_id in link_ids:
            cam_name = "cam" + str(self.nb_cam)
            obj_name = "{}_{}".format(obj_id, link_id)
            self.sensor_objects.append((cam_name,obj_name,urdf))
            self.cameras[cam_name] = Link(obj_id, link_id, self.cid,cam_name=cam_name)
            self.nb_cam += 1
    def add_object(self, urdf_fn, obj_id, globalScaling=1.0):
        # Load urdf file by urdfpy
        robot = URDF.load(urdf_fn)
        logger.info(urdf_fn)
        for link_id, link in enumerate(robot.links):
            if len(link.visuals) == 0:
                continue
            link_id = link_id - 1
            # Get each links
            visual = link.visuals[0]
            obj_trimesh = visual.geometry.meshes[0]

            # Set mesh color to default (remove texture)
            obj_trimesh.visual = trimesh.visual.ColorVisuals()

            # Set initial origin (pybullet pose already considered initial origin position, not orientation)
            pose = visual.origin

            # Scale if it is mesh object (e.g. STL, OBJ file)
            mesh = visual.geometry.mesh
            if mesh is not None and mesh.scale is not None:
                S = np.eye(4, dtype=np.float64)
                S[:3, :3] = np.diag(mesh.scale)
                pose = pose.dot(S)

            # Apply interial origin if applicable
            inertial = link.inertial
            if inertial is not None and inertial.origin is not None:
                pose = np.linalg.inv(inertial.origin).dot(pose)

            # Set global scaling
            pose = np.diag([globalScaling] * 3 + [1]).dot(pose)

            obj_trimesh = obj_trimesh.apply_transform(pose)
            obj_name = "{}_{}".format(obj_id, link_id)
            self.scene_objects[obj_name]=robot
            self.objects[obj_name] = Link(obj_id, link_id, self.cid)
            position, orientation = self.objects[obj_name].get_pose(self.dataReceiver)

            # Add object in pyrender
            self.renderer.add_object(
                obj_trimesh,
                obj_name,
                position=position,  # [-0.015, 0, 0.0235],
                orientation=orientation,  # [0, 0, 0],
            )
    def resetDebugVisualizerCamera(self,**params):
        self.setup.resetDebugVisualizerCamera(**params)
    def add_body(self, **body):
        self.setup.add_object(**body)
    def run_resetDebugVisualizerCamera(self):
        p.resetDebugVisualizerCamera(**self.setup.reset_params)
        
    def init_objects(self):
        for obj in self.setup.setup_objects:

            pxbody=px.Body(**obj.params)
            self.add_object(
                pxbody.urdf_path, pxbody.id, globalScaling=pxbody.global_scaling or 1.0
            )
    def loadURDF(self, *args, **kwargs):
        warnings.warn(
            "\33[33mSensor.loadURDF is deprecated. Please use body = "
            "pybulletX.Body(...) and Sensor.add_body(body) instead\33[0m."
        )
        """
        Load the object urdf to pybullet and tacto simulator.
        The tacto simulator will create the same scene in OpenGL for faster rendering
        """
        urdf_fn = args[0]
        globalScaling = kwargs.get("globalScaling", 1.0)

        # Add to pybullet
        obj_id = p.loadURDF(physicsClientId=self.cid, *args, **kwargs)

        # Add to tacto simulator scene
        self.add_object(urdf_fn, obj_id, globalScaling=globalScaling)

        return obj_id

    def update(self):
        warnings.warn(
            "\33[33mSensor.update is deprecated and renamed to ._update_object_poses()"
            ", which will be called automatically in .render()\33[0m"
        )

    def _update_object_poses(self):
        """
        Update the pose of each objects registered in tacto simulator
        """
        
        for obj_name in self.objects.keys():
            self.object_poses[obj_name] = self.objects[obj_name].get_pose(self.dataReceiver)
            if self.objects[obj_name].mesh is not None:
                #print(type(self.objects[obj_name].mesh))
                #print(self.objects[obj_name].mesh)
                #print(type(self.renderer.current_object_nodes[obj_name].mesh))
                self.renderer.current_object_nodes[obj_name].mesh=pyrender.Mesh.from_trimesh(self.objects[obj_name].mesh)
                self.renderer.object_nodes[obj_name].mesh==self.objects[obj_name].mesh

    def get_force(self, cam_name):
        # Load contact force

        obj_id = self.cameras[cam_name].obj_id
        link_id = self.cameras[cam_name].link_id
        self.normal_forces[cam_name] = collections.defaultdict(float)
        if self.cameras[cam_name].force!=None:
            obj_name = "{}_{}".format(2, -1)
            self.normal_forces[cam_name][obj_name]=float(self.cameras[cam_name].force)
            return self.normal_forces[cam_name]
        pts = p.getContactPoints(
            bodyA=obj_id, linkIndexA=link_id, physicsClientId=self.cid
        )

        # accumulate forces from 0. using defaultdict of float

        for pt in pts:
            body_id_b = pt[2]
            link_id_b = pt[4]

            obj_name = "{}_{}".format(body_id_b, link_id_b)

            # ignore contacts we don't care (those not in self.objects)
            if obj_name not in self.objects:
                continue

            # Accumulate normal forces
            self.normal_forces[cam_name][obj_name] += pt[9]

        return self.normal_forces[cam_name]

    @property
    def static(self):
        if self._static is None:
            colors, _ = self.renderer.render(noise=False)
            depths = [np.zeros_like(d0) for d0 in self.renderer.depth0]
            self._static = (colors, depths)

        return self._static

    def _render_static(self):
        colors, depths = self.static
        colors = [self.renderer._add_noise(color) for color in colors]
        return colors, depths

    def render(self):
        """
        Render tacto images from each camera's view.
        """

        self._update_object_poses()
        colors = []
        depths = []

        for i in range(self.nb_cam):
            cam_name = "cam" + str(i)

            # get the contact normal forces

            normal_forces = self.get_force(cam_name)
            position, orientation = self.cameras[cam_name].get_pose(self.dataReceiver)
            
            self.renderer.update_camera_pose(position, orientation)
            if normal_forces:
                color, depth = self.renderer.render(position,orientation,object_poses=self.object_poses, normal_forces=normal_forces)

                # Remove the depth from curved gel
                for j in range(len(depth)):
                    depth[j] = self.renderer.depth0[j] - depth[j]
            else:
                color, depth = self._render_static()

            colors += color
            depths += depth

        return colors, depths

    def _depth_to_color(self, depth):
        gray = (np.clip(depth / self.zrange, 0, 1) * 255).astype(np.uint8)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    def updateGUI(self, colors, depths):
        """
        Update images for visualization
        """
        if not self.visualize_gui:
            return

        # concatenate colors horizontally (axis=1)
        color = np.concatenate(colors, axis=1)

        if self.show_depth:
            # concatenate depths horizontally (axis=1)
            depth = np.concatenate(list(map(self._depth_to_color, depths)), axis=1)

            # concatenate the resulting two images vertically (axis=0)
            color_n_depth = np.concatenate([color, depth], axis=0)

            cv2.imshow(
                "color and depth", cv2.cvtColor(color_n_depth, cv2.COLOR_RGB2BGR)
            )
        else:
            cv2.imshow("color", cv2.cvtColor(color, cv2.COLOR_RGB2BGR))

        cv2.waitKey(1)
