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
import tetgen
import gmsh
import pyvista as pv
#import tacto  # Import TACTO
import vtk
import hydra
from tacto.sofa_addon.dataTransport import TransportData, Sender,DataReceiver
# Choose in your script to activate or not the GUI
USE_GUI = True
import trimesh
tmpMeshes=[]
def stl_to_tetrahedral_vtk(stl_path, vtk_output_path):
        if os.path.exists(vtk_output_path):
            print(f"File already exists: {vtk_output_path}")
            return vtk_output_path  # Or handle as needed

        gmsh.initialize()
        gmsh.open(stl_path)

        # This is how you set options for gmsh:
        # TODO: Make these configurable!
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.01)

        # Print the model name and dimension:
        #print('Model ' + gmsh.model.getCurrent() + ' (' +
        #    str(gmsh.model.getDimension()) + 'D)')

        n = gmsh.model.getDimension()
        s = gmsh.model.getEntities(n)
        l = gmsh.model.geo.addSurfaceLoop([s[i][1] for i in range(len(s))])
        gmsh.model.geo.addVolume([l])
        gmsh.model.geo.synchronize()

        gmsh.model.mesh.generate(dim=3)
        gmsh.model.mesh.optimize(method="Netgen", force=True)

        # Print the model name and dimension:
        #print('Model ' + gmsh.model.getCurrent() + ' (' +
        #    str(gmsh.model.getDimension()) + 'D)')
        gmsh.write(vtk_output_path)
        return vtk_output_path
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
                                young_modulus = 200000.0,
                                poisson_ratio = 0.47273863208820904,
                                constitutive_model = ConstitutiveModel.COROTATED,
                                mass_density = .2
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
        tissue = root.addObject(Tissue(
                                root,
                                simulation_mesh_filename="meshes/preop_volume.vtk",
                                #simulation_mesh_filename=stl_to_tetrahedral_vtk(meshRootDir+obj.mesh,meshRootDir+"mesh_out.vtk"),#"meshes/preop_volume.vtk",
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
                                contact_stiffness=1.0,
                                massDensity=10.0,
                                senderD=dataSend
                                )
                            )
        tissueList.append(tissue)

    root.addObject(TactoController(name = sensorObj.name,sofaObjects=tissueList,meshfile=meshRootDir+sensorObj.mesh,senderD=dataSend,parent=root,solver=solver,stiffness=10.0,position=sensorObj.position,orientation=sensorObj.orientation,forceMode=ForceMode.dof,controllMode=ControllMode.position))
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
    tactoProc=Process(target=tacto.sofa_addon.tactoEnvironment.tactoLaunch,args=(IPC.getTactoConnects(),digits,))#sendSetupAndStart
    
    
    tactoProc.start()
    sofaProc.start()
    
    tactoProc.join()
    sofaProc.join()