from meshlib import mrmeshpy
import os
import math 
import Sofa.Simulation
import SofaRuntime, Sofa.Core,Sofa.Gui
from splib3.numerics import RigidDof
from splib3.numerics.quat import Quat
import splib3.numerics.quat
import numpy as np
from stl import mesh
import trimesh
import heapq
from enum import Enum,auto
import cProfile
import logging
from core.sofa.objects.tissue import Tissue
from core.sofa.components.forcefield import Material, ConstitutiveModel
from core.sofa.components.solver import SolverType, TimeIntegrationType
from tacto.sofa_addon.utils import stl_to_tetrahedral_vtk
def readMesh():
    your_mesh = mesh.Mesh.from_file('mesh/.stl')

def get_rotation_matrix(angles):
    roll=angles[0]
    pitch=angles[1]
    yaw=angles[2]
    # Roll (rotation around X-axis)
    R_x = np.array([[1, 0, 0],
                    [0, np.cos(roll), -np.sin(roll)],
                    [0, np.sin(roll), np.cos(roll)]])
    
    # Pitch (rotation around Y-axis)
    R_y = np.array([[np.cos(pitch), 0, np.sin(pitch)],
                    [0, 1, 0],
                    [-np.sin(pitch), 0, np.cos(pitch)]])
    
    # Yaw (rotation around Z-axis)
    R_z = np.array([[np.cos(yaw), -np.sin(yaw), 0],
                    [np.sin(yaw), np.cos(yaw), 0],
                    [0, 0, 1]])
    
    # Combined rotation matrix (ZYX order)
    R = np.dot(R_z, np.dot(R_y, R_x))
    
    return R

def transform_to_global(local_point, orientation, position):
    rotation_matrix=get_rotation_matrix(orientation)
    # Convert the point to a numpy array for easier matrix operations
    local_point = np.array(local_point)
    translation_vector = np.array(position)
    
    # Apply the transformation: rotate then translate
    global_point = np.dot(rotation_matrix, local_point) + translation_vector
    return global_point

def findClosestVerts(verts, pos, num_closest=1):
    # Calculate distances from the position to each vertex
    distances = [(i, (v[0] - pos[0])**2 + (v[1] - pos[1])**2 + (v[2] - pos[2])**2) for i, v in enumerate(verts)]
    
    # Find the `num_closest` vertices with the smallest distances
    closest_indices = [i for i, _ in heapq.nsmallest(num_closest, distances, key=lambda x: x[1])]
    
    # Retrieve the vertices corresponding to the closest indices
    closest_verts = [verts[i] for i in closest_indices]
    
    return closest_verts
mesh=None
firstEvent=True

def faceNormal(points):
    p1, p2, p3 = points
    
    # Compute the face normal
    v1 = p2 - p1
    v2 = p3 - p1
    normal = np.cross(v1, v2)
    normal = normal / np.linalg.norm(normal)
    return normal
def planeSign(plane_normal,plane_point,point):
    # Unpack the plane normal vector and point coordinates
    a, b, c = plane_normal
    x0, y0, z0 = plane_point
    x_p, y_p, z_p = point
    
    # Compute the plane equation value for the point
    d = -(a * x0 + b * y0 + c * z0)
    value = a * x_p + b * y_p + c * z_p + d
    return value
def baseNormalVec(node,XYZ=None):
    global mesh
    posOffset=[0.025,0.0,0.0]
    old_y=[0.0,0.0,0.0]
    nodePos=transform_to_global(posOffset,node.getAngles(),node.transformWrapper.getPosition())
    verticesTissue=node.parent.Tissue.Visual.VMapping.output.position.value
    trianglesTissue=node.parent.Tissue.Visual.VMapping.output.triangles.value
    tissueVerts=findClosestVerts(verticesTissue,[nodePos[0],nodePos[1],nodePos[2]])
    """
    this is to prevent sensor clipping into the tissue mesh and not getting out
    if mesh.contains([nodePos]):
        node.forceApply*=0.5
        k=node.transformWrapper.getPosition()
        node.transformWrapper.setPosition([k[0]-0.001*old_y[0],k[1]-0.001*old_y[1],k[2]-0.001*old_y[2]])
        return old_y[0],old_y[1],old_y[2]
    """
    y = nodePos - tissueVerts[0]
    normalized_y=y/np.linalg.norm(y)
    #alternative: normalized_y=faceNormal(tissueVerts)
    if XYZ is None:
        return normalized_y[0],normalized_y[1],normalized_y[2]
    #finde y and z that are orthogonal to x
    x =np.cross(normalized_y, np.array([0.0,0.0,1.0]))
    normalized_x= x / np.sqrt(np.sum(x**2))
    z =np.cross(normalized_x, normalized_y)
    normalized_z= z / np.sqrt(np.sum(z**2))
    l=[normalized_x,normalized_y,normalized_z]
    ret=[0.0,0.0,0.0]
    for i in range(len(XYZ)):
        for j in range(len(l[i])):
            ret[j]+=XYZ[i]*l[i][j]
    old_y=normalized_y
    return ret
forceY=[]

class ControllMode(Enum):
    
    forceField :int =1
    #
    position : int =2
    #directed towards the surface of the mesh
    directedForceField : int = 3 
    forceFieldAtContact : int = 4
    directedForceFieldAtContact : int =5
class ForceMode(Enum):
    # use Y force  
    dof : int = 1
    # use GenericConstraintSolver output of to accumulate normalforces 
    # (impact of certain forcefield might not be included)
    normal : int =2
    #approximate force based on nr of vertices in contact
    vertex : int = 3
def createGlue(node):
    glueNode = node.createChild('Glue')
    glueNode.createObject('MeshSTLLoader', name='stlLoader', filename='meshes/gel.stl')
    deformableMO = glueNode.createObject('MechanicalObject', name='glueMech', template='Vec3d',
                                               position='@stlLoader.position')
    
    glueNode.createObject('RigidMapping', input='@../TactoMechanics', output='@glueMech')
    glueNode.createObject('TriangleSetTopologyContainer', name='topology', 
                                triangles='@stlLoader.triangles')

class TactoController(Sofa.Core.Controller):
    """ This controller monitors new sphere objects.
    Press ctrl and the L key to make spheres falling!
    """
    def applyRelativetrans(self):
        verts = np.array(self.gelNode.state.position.value)  # Convert to numpy array
        pos = np.array(self.transformWrapper.getPosition())  # Convert to numpy array
        angles_rad = Quat(self.transformWrapper.getOrientation().tolist()).getEulerAngles()
        angles_rad_diff = np.array(angles_rad) - np.array(self.oldAngles)
        tmp=angles_rad_diff[0]
        angles_rad_diff[0]=angles_rad_diff[1]
        angles_rad_diff[1]=-tmp
        # Transfer points to their origin 
        originVerts = verts - np.array(self.oldPos)

        # Construct the rotation matrix
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(angles_rad_diff[0]), -np.sin(angles_rad_diff[0])],
            [0, np.sin(angles_rad_diff[0]), np.cos(angles_rad_diff[0])]
        ])

        Ry = np.array([
            [np.cos(angles_rad_diff[1]), 0, np.sin(angles_rad_diff[1])],
            [0, 1, 0],
            [-np.sin(angles_rad_diff[1]), 0, np.cos(angles_rad_diff[1])]
        ])

        Rz = np.array([
            [np.cos(angles_rad_diff[2]), -np.sin(angles_rad_diff[2]), 0],
            [np.sin(angles_rad_diff[2]), np.cos(angles_rad_diff[2]), 0],
            [0, 0, 1]
        ])

        # Combine the rotation matrices into a single rotation matrix
        rotation_matrix = Rz @ Ry @ Rx
        # leverage np vectorization to rotate and the translate
        transformed_verts = (originVerts @ rotation_matrix.T) + pos

        # Assign the transformed vertices back to the mechanical object
        self.gelNode.state.position.value = transformed_verts.tolist()

        self.oldAngles=[angles_rad[0],angles_rad[1],angles_rad[2]]
        self.oldPos=[pos[0],pos[1],pos[2]]
    def addBasics(self,node):
        plugins=['SofaRigid']
        plugins.append('SofaConstraint')
        plugins.append('Sofa.Component.Haptics')
        node.addObject('EulerImplicitSolver', name="cg_odesolver")
        if self.solver!=None:
            node.addObject(self.solver.objectName,iterations=self.solver.iterations, tolerance=self.solver.tolerance, threshold=self.solver.threshold)
        else:
            node.addObject("CGLinearSolver",iterations=20, tolerance=1e-2, threshold=1e-2)
        node.addObject('RequiredPlugin', pluginName=plugins)
    def addVisuals(self,node):
        visual=node.addChild("Visual")
        visual.addObject("OglModel",name="VisualModel",src="@../../TactoMeshLoader")
        visual.addObject('RigidMapping')
    def makefixedVerts(self):
        threshhold=0.018
        outar=[]
        for i,vert in enumerate(self.gelNode.state.position.value):
            if vert[0]<threshhold:
                outar.append(i)
        result = ' '.join(map(str, outar))
        return result
    def addCollision(self,node):
        """
        collision = node.addChild('collision')

        collision.addObject('MeshTopology', src="@../../TactoMeshLoader")
        collision.addObject('MechanicalObject')
        #node.addObject('FixedConstraint', name="FixedConstraint", indices="0")
        collision.addObject('TriangleCollisionModel',contactStiffness=self.stiffness)
        #collision.addObject('LineCollisionModel')
        #collision.addObject('PointCollisionModel')
        collision.addObject('RigidMapping')
        """
        material=Material(
                                young_modulus = 1e5,
                                poisson_ratio = 0.35,
                                constitutive_model = ConstitutiveModel.COROTATED,
                                mass_density = 100
                            )
        self.gelNode = node.addObject(Tissue( self.parent,
                                #simulation_mesh_filename="meshes/preop_volume.vtk",
                                simulation_mesh_filename=stl_to_tetrahedral_vtk("meshes/gel.stl","meshes/mesh_gel_out.vtk"),#"meshes/preop_volume.vtk",
                                material= material,
                                node_name="collisionGel",
                                tactoName="collisionGel",
                                check_displacement=False,
                                #grid_resolution=[8,2,6], # for simulation with hexa
                                solver=self.solver,
                                analysis=TimeIntegrationType.EULER,
                                surface_mesh="meshes/gel.stl", # e.g. surface for visualization or collision
                                view=True,
                                position=[0,0,0],
                                orientation=[0,0,0],
                                collision=True,
                                contact_stiffness=100,
                                massDensity=material.mass_density))
        #createGlue(node)
        fixedVerts=[]
        self.gelNode.node.addObject('FixedConstraint', name="FixedConstraint", indices=self.makefixedVerts())
        #gelNode.node.addObject('RigidMapping',mapForces=0,input='@../TactoMechanics', output='@MechanicalObject_state')
        #merge.addObject("BarycentricMapping", name="VMapping", input="@../collisionGel/MechanicalObject_state", output="@mergeMech")
        self.gel=self.gelNode.node
        #self.gelNode.node.addObject('ConstantForceField', name="CFF", totalForce=[0.1, 0.0, 0.0, 0, 0, 0, 0])
        return self.gelNode.node.Collision
    def getDofForce(self):
        force= self.gel.state.force.array()
        forceRet=0.0
        for dof in force:
            forceRet+=(np.sum(np.array(dof))/len(dof))
        self.forceBuf.append(forceRet)
        if len(self.forceBuf)==4:
            self.forceBuf.pop(0)
            return np.sum(np.array(self.forceBuf))# use the last three force messurements to smooth out the data delivered to tacto
        return self.forceBuf[0]
    def getNormalForce(self):
        forcesNorm = self.parent.GCS.constraintForces.value
        acc=0.0
        for i in forcesNorm:
            if i>0:
                acc+=i
        return acc*100
    #approximate force based on nr of vertices in contact
    def getCollisionEstimatedForce(self):
        nr_contacts=0
        ret=0
        for listener in self.listeners:
            nr_contacts+=listener.getNumberOfContacts()
            self.contacts=nr_contacts
            ret=nr_contacts/50
            if nr_contacts>100:
                ret=100
        return ret
    
    def onAnimateEndEvent(self, __):
        global firstEvent
        if firstEvent==True:
            self.transformWrapper.setPosition(self.init_state)
            firstEvent=False
        if self.controllMode==ControllMode.directedForceFieldAtContact:
            x,y,z=baseNormalVec(self)
            self.node.CFF.totalForce.value=[x*self.forceApply, y*self.forceApply, z*self.forceApply, 0, 0, 0]
        sendForce=abs(self.forceDict[self.forceMode]())
        if self.controllMode==ControllMode.forceField or self.controllMode==ControllMode.forceFieldAtContact or self.controllMode==ControllMode.directedForceFieldAtContact or self.controllMode==ControllMode.directedForceField:
            vel=self.rigidobject.velocity.value[0]
            sumVelo=abs(np.sum(np.array(vel)))
            if sumVelo >1e-6:
                #print("HOW AM I HERE")
                #self.rigidobject.velocity.value = [0,0,0]
                
                k=self.node.CFF.totalForce.value
                self.forceApply=0.0
                #print(f' Force before: {k}')
                
                sum=0
                
                self.rigidobject.velocity.value=[[0, 0, 0, 0, 0, 0]]
                self.node.CFF.totalForce.value=[0, 0, 0, 0, 0, 0]
                
                #print(f' Force after: {self.node.CFF.totalForce.value}')
        
        
        if self.getCollisionEstimatedForce()==0 or self.mode==1:
            sendForce=0.0
        self.applyRelativetrans()
        #print(f'update tacto {self.tactoName}')
        self.dataSender.update(self.tactoName,self.transformWrapper.getPosition(),self.getAngles(),sendForce,mesh=None)
        #print(f'update sofa {self.sofaObjects[0].tactoName}')
        
    def reset(self):
        self.transformWrapper.setPosition(self.init_state)
        self.rigidobject.velocity.value=[[0, 0, 0, 0, 0, 0]]
        self.node.CFF.totalForce.value=[0, 0, 0, 0, 0, 0]
        self.forceApply=0.0
    def __init__(self, name:str,meshfile : str,parent:Sofa.Core.Node,sofaObjects=None,stiffness=5.0,senderD=None,solver=None,position=[0.0,0.0,0.0],orientation=[0,0,0,0],forceMode :ForceMode=ForceMode.dof, controllMode:ControllMode=ControllMode.position ):
        Sofa.Core.Controller.__init__(self)
        self.iteration = 0
        self.solver=solver
        self.forceMode=forceMode
        self.parent=parent
        self.dataSender=senderD
        self.stiffness=stiffness
        self.parent.addObject("MeshSTLLoader",name="TactoMeshLoader",triangulate="true",filename=meshfile)
        self.parent.addObject("MeshSTLLoader",name="GelMeshLoader",triangulate="true",filename="meshes/gel.stl")
        self.node=self.parent.addChild(name)
        self.tactoName=name
        self.contacts=0
        rotQ=Quat.createFromEuler(list(orientation))
        self.init_state=[position[0],position[1],position[2],rotQ[0],rotQ[1],rotQ[2],rotQ[3]]
        self.addBasics(self.node)
        self.rigidobject=self.node.addObject("MechanicalObject",template="Rigid3d",name="TactoMechanics",position=self.init_state)
        self.oldAngles=[0,0,0]
        self.oldPos=[0,0,0]
        self.node.addObject("UniformMass",vertexMass=[1., 1., [1., 0., 0., 0., 1., 0., 0., 0., 1.][:]])
        self.addVisuals(self.node)
        self.collision=self.addCollision(self.node)
        #self.node.addObject("RestShapeSpringsForceField",stiffness='100000',angularStiffness='100000',external_rest_shape='@TactoMechanics',points='0',external_points='0')
        #self.node.addObject("LCPForceFeedback",name="LPCs",forceCoef="1.0")
        self.sofaObjects=sofaObjects
        self.listeners =[self.node.addObject(
            "ContactListener",
            collisionModel1=objects.node.getChild("Collision").getObject("CollisionModel").getLinkPath(),
            collisionModel2=self.collision.CollisionModel.getLinkPath(),
        )for objects in sofaObjects]
        #cProfile.run('self.onAnimateEndEvent()')
        self.forceApply=10000.0
        self.forceBuf=[]
        self.key=""
        self.XYZ=[1.0,0.0,0.0]
        self.scaleIncr=0.1
        self.scale=0.01
        self.transformWrapper=RigidDof(self.rigidobject)
        #self.dataSender.update("Sensor",self.transformWrapper.getPosition(),self.getAngles())
        self.controllMode=controllMode
        if self.controllMode==ControllMode.position:
            self.node.addObject('FixedConstraint', name="FixedConstraint", indices="0")
        self.node.addObject('ConstantForceField', name="CFF", totalForce=[0.0, 0.0, 0.0, 0, 0, 0, 0])
        self.node.addObject('UncoupledConstraintCorrection')
        self.mode=0
        self.forceDict={ForceMode.dof:self.getDofForce,ForceMode.normal:self.getNormalForce,ForceMode.vertex:self.getCollisionEstimatedForce}
        self.modeSelect=['Translate','Rotate','Scale']
        self.ModeDict = {'Translate' : self.trans,
           'Rotate' : self.rot,
           'Scale' :self.scaleF
        }
        print("To use Controller always use STRG + (key)")
        print("Change Mode with STRG+M available Modes are: Translate, Rotate and Scale")
        print("Scale refers to the size of the operation (Translate,Rotate) executed not the scale of the Sensor")
        print("If in Translate or Rotate Mode use x, y and z to select the direction of the operation")
        print("Use + / - to translate,rotate and change the Scale of the Operation in the respective Mode")
    def radTodeg(self,angle):
         return (angle*180)/math.pi
    def degtoRad(self,angle):
        return angle*math.pi/180
    def changePos(self):
        t=self.transformWrapper.getPosition()
        print(f'Position before: {t}')
        if self.key=='+':
            self.transformWrapper.setPosition([t[0]+self.XYZ[0]*self.scale, t[1]+self.XYZ[1]*self.scale, t[2]+self.XYZ[2]*self.scale])
        if self.key=='-':
            x=t[0]-self.XYZ[0]*self.scale
            self.transformWrapper.setPosition([t[0]-self.XYZ[0]*self.scale, t[1]-self.XYZ[1]*self.scale, t[2]-self.XYZ[2]*self.scale])
        t1=self.transformWrapper.getPosition()
        print(f'Position after: {t1}')
    def applyForce(self,vec):
        ar=[]
        if self.key=='+':
                for i in vec:
                    ar.append(i*10*self.scale*100)
        if self.key=='-':
                for i in vec:
                    ar.append(-i*10*self.scale*100)
        self.node.CFF.totalForce.value=ar
    def trans(self):
        if self.controllMode==ControllMode.forceField:
            self.applyForce(self.XYZ+[0,0,0])
            return 

        if self.controllMode==ControllMode.directedForceField:
            x,y,z=baseNormalVec(self,self.XYZ)
            self.applyForce([x,y,z,0,0,0])
        if self.controllMode==ControllMode.position:
            self.changePos()
        if self.controllMode==ControllMode.forceFieldAtContact:
            if self.contacts==0:
                self.changePos()
            else:
                self.applyForce(self.XYZ+[0,0,0])
        if self.controllMode==ControllMode.directedForceFieldAtContact:
            if self.contacts==0:
                self.changePos()
            else:
                x,y,z=baseNormalVec(self,self.XYZ)
                self.applyForce([x,y,z,0,0,0])
    def scaleF(self):
        scalebef=self.scale
        print(self.scaleIncr)
        if self.key=='+':
            switch=math.floor(math.log10(self.scale))
            self.scaleIncr=(10**switch)
            self.scale+=self.scaleIncr
            self.scale=round(self.scale,-switch+1)
            #self.scale=round(self.scale,4)
        if self.key=='-':
            switch=math.floor(math.log10(self.scale-(1e-9)))
            self.scaleIncr=(10**switch)
            if self.scale<=0.0001:
                print("ScaleValueToShort")
                return
            self.scale-=self.scaleIncr
            self.scale=round(self.scale,-switch+1)
            #self.scale=round(self.scale,4)
        print(f'Change Scale of Operations (T/R) from {scalebef} to {self.scale} ')
    def getAngles(self):
        eulerAngles= Quat(self.transformWrapper.getOrientation().tolist()).getEulerAngles()
        return [round(self.radTodeg(el),4) for el in eulerAngles]
    def rot(self):
        if self.controllMode==ControllMode.forceField or self.controllMode==ControllMode.directedForceField:
            self.applyForce([0,0,0]+self.XYZ)
            return 
        if self.controllMode==ControllMode.directedForceFieldAtContact or self.controllMode==ControllMode.forceFieldAtContact:
            if self.contacts!=0:
                self.applyForce([0,0,0]+self.XYZ)
            return 
        print(f'Angles before Rotate: {self.getAngles()}')
        #axis=[int(self.XYZ[0]),int(self.XYZ[1]),int(self.XYZ[2])]
        val=100*self.scale
        if val>180.0:
            val=val%180
            val=-180+val
        print(f'Rotate by {val} degree (10*scale)')
        if self.key=='+':
            self.transformWrapper.rotateAround(self.XYZ,self.degtoRad(val))
        if self.key=='-':
            self.transformWrapper.rotateAround(self.XYZ,self.degtoRad(-val))
        print(f'Angles after Rotate: {self.getAngles()}')
        #Todo
        return
        #splib3.numerics.quat.createFromEuler()
    def onKeypressedEvent(self, event):
        # Press L key triggers the creation of new objects in the scene
        keypressed=event['key']
        print(f' Key pressed = {keypressed}')
        if event['key'] == 'M':
            self.mode =(self.mode+1)%3
            modestr=self.modeSelect[self.mode]
            print(f'Change Mode to {modestr}')
        if event['key']=='X' and not self.XYZ==[1.0,0.0,0.0]:
            self.XYZ=[1.0,0.0,0.0]
            print(f'"Mode: {self.modeSelect[self.mode]} in Direction {keypressed}')
        if event['key']=='Y' and not self.XYZ==[0.0,1.0,0.0]:
            self.XYZ=[0.0,1.0,0.0]
            print(f'"Mode: {self.modeSelect[self.mode]} in Direction {keypressed}')
        if event['key']=='Z' and not self.XYZ==[0.0,0.0,1.0]:
            self.XYZ=[0.0,0.0,1.0]
            print(f'"Mode: {self.modeSelect[self.mode]} in Direction {keypressed}')
        if event['key']=='-' or event['key']=='+':
            self.key=event['key'] 
            self.ModeDict[self.modeSelect[self.mode]]()
        self.iteration+=1
        if event['key']=='K':
            self.reset()
        #self.setPosition([0, 1.0, 0, 0, 0, 0, 1])
        if event['key']=='L':
            self.createNewSphere()
        
    def createNewSphere(self):
        root = self.getContext()
        newSphere = root.addChild('FallingSphere-'+str(self.iteration))
        newSphere.addObject('EulerImplicitSolver', name="cg_odesolver", rayleighStiffness=0.1, rayleighMass=0.1)
        newSphere.addObject('CGLinearSolver', threshold='1e-09', tolerance='1e-09', iterations='200')
        MO = newSphere.addObject('MechanicalObject', position=[0, 1.5+0.5*self.iteration, 0, 0, 0, 0, 1], name=f'Particle-{self.iteration}', template='Rigid3d')
        Mass = newSphere.addObject('UniformMass', totalMass=0.001)
        Force = newSphere.addObject('ConstantForceField', name="CFF", totalForce=[0, -1, 0, 0, 0, 0] )
        Sphere = newSphere.addObject('SphereCollisionModel', name="SCM", simulated=1,moving=1,radius=0.02,contactStiffness=10.0 )
        self.iteration = self.iteration+1
        newSphere.init()
        
        self.iteration = self.iteration+1