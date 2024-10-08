from meshlib import mrmeshpy
import Sofa.Simulation
import logging
import SofaRuntime, Sofa.Core,Sofa.Gui
import os
import Sofa.Simulation
import SofaRuntime, Sofa.Core,Sofa.Gui
from core.sofa.objects.tissue import Tissue
from core.sofa.components.forcefield import Material, ConstitutiveModel
from core.sofa.components.solver import SolverType, TimeIntegrationType
import tacto
import pybulletX as px
from tacto.sofa_addon.TactoController import TactoController,ControllMode,ForceMode
import tacto.sofa_addon.SofaRootConfig
from multiprocessing import Process, Pipe
from threading import Thread
#from core.sofa.components.solver import TimeIntegrationType, ConstraintCorrectionType, SolverType, add_solver
from tacto.sofa_addon.SofaRootConfig import Environment,Solver
import tacto.sofa_addon.tactoEnvironment
import numpy as np
from tacto.sofa_addon.utils import stl_to_tetrahedral_vtk
import pyvista as pv
#import tacto  # Import TACTO
import vtk
import hydra
from tacto.sofa_addon.dataTransport import TransportData, Sender,DataReceiver
# Choose in your script to activate or not the GUI
USE_GUI = True
import trimesh
tmpMeshes=[]

vtkMesh=None
material=None
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
solver=tacto.sofa_addon.SofaRootConfig.Solver(objectName="CGLinearSolver",iterations=30, tolerance=1e-3, threshold=1e-3)
logger = logging.getLogger('SOFA-Simulation')
def createScene(root,dataSend,setupReceive):
    log = logging.getLogger(__name__)
    global solver
    global tmp_mesh
    env=Environment(root)
    log.info("after env")
    material=Material(
                                young_modulus = 1e5,
                                poisson_ratio = 0.4,
                                constitutive_model = ConstitutiveModel.COROTATED,
                                mass_density = 100.0
                            )
    

    #root.addObject('MeshObjLoader', name="LiverSurface", filename="mesh/liver-smooth.obj")
    from time import sleep
    log.info("after env3")
    
    while setupReceive.latest_data.sofaOjectDict=={}:
        sleep(0.1)
        log.info("not found")
        
        #print("not found")
        pass
    log.info("after env2")
    tissueList=[]
    log.info(setupReceive.latest_data.sofaOjectDict)
    meshRootDir="meshes/"
    objectlist=[]
    sensorObj=None
    tmp_mesh =""
    for objName in setupReceive.latest_data.sofaOjectDict:
        obj=setupReceive.latest_data.sofaOjectDict[objName]
        if obj.forces==-1.0:
            objectlist.append(obj)
            
        else:
            sensorObj=obj
    
            log.info(meshRootDir+obj.mesh)
    
    for obj in objectlist:
        tmpMeshes.append(obj.mesh)
        print("OBJECT MESH")
        print(obj.mesh)
        tissue = root.addObject(Tissue(
                                root,
                                #simulation_mesh_filename="meshes/preop_volume.vtk",
                                simulation_mesh_filename=stl_to_tetrahedral_vtk(meshRootDir+obj.mesh,meshRootDir+obj.mesh+".vtk"),#"meshes/preop_volume.vtk",
                                material= material,
                                node_name="Tissue",
                                tactoName=obj.name,
                                check_displacement=False,
                                #grid_resolution=[8,2,6], # for simulation with hexa
                                solver=solver,
                                analysis=TimeIntegrationType.EULER,
                                surface_mesh=meshRootDir+obj.mesh, # e.g. surface for visualization or collision
                                view=True,
                                position=obj.position,
                                orientation=obj.orientation,
                                collision=True,
                                contact_stiffness=10.0,
                                massDensity=material.mass_density,
                                senderD=dataSend
                                )
                            )
        tissueList.append(tissue)
    
    tactoController=root.addObject(TactoController(name = sensorObj.name,sofaObjects=tissueList,meshfile=meshRootDir+sensorObj.mesh,
                                                   senderD=dataSend,parent=root,solver=solver,
                                                   stiffness=0.01,position=sensorObj.position,orientation=sensorObj.orientation,
                                                   forceMode=ForceMode.dof,controllMode=ControllMode.position))
    
    #print(type(tissue))
    #createCollisionMesh(root)


# Check if file exists before removing
    return root
class connects:
    toSofa, fromTacto = Pipe()
    toTacto, fromSofa = Pipe()
    def getSofaConnects(self):
        return self.toTacto,self.fromTacto
    def getTactoConnects(self):
        return self.toSofa,self.fromSofa
def sofaSimLoop(connects):
    (toTacto,fromTacto)=connects
    log = logging.getLogger(__name__)
    dataSend=Sender(toTacto)
    setupReceive=DataReceiver(fromTacto)
    root = Sofa.Core.Node("root")
    setupReceive.start()
    createScene(root,dataSend,setupReceive)
    dataSend.start()
    Sofa.Simulation.init(root)
    Sofa.Gui.GUIManager.Init("myscene", "qglviewer")
    Sofa.Gui.GUIManager.createGUI(root, __file__)
    Sofa.Gui.GUIManager.SetDimension(1080, 1080)
    Sofa.Gui.GUIManager.MainLoop(root)
    Sofa.Gui.GUIManager.closeGUI()
    setupReceive.join()
    dataSend.join()  
    global tmp_mesh
    for i in tmp_mesh:
        if os.path.exists(i):
            os.remove(i)
        #containsSendingAnd ContainingPipes getting Initialized in Sensor
    #aim should be only setting up pipe and processes and objects specified by config name in main rest handled by 
    #even better setting up a sofaTacto=SofaTactoStart(sensor=sensorObj) 
    #sofaTacto.start()
def init(digits):
    import SofaRuntime
    import Sofa.Gui
    
    IPC=connects()
    

    sofaProc=Process(target=sofaSimLoop,args=(IPC.getSofaConnects(),))#waitsForSetupbasedOn config files
    sofaProc.start()
    #tacto.sofa_addon.tactoEnvironment.tactoLaunch(IPC.getTactoConnects(),digits)
    
    tactoProc=Process(target=tacto.sofa_addon.tactoEnvironment.tactoLaunch,args=(IPC.getTactoConnects(),digits,))#sendSetupAndStart
    
    
    tactoProc.start()
    
    
    tactoProc.join()
    sofaProc.join()