from meshlib import mrmeshpy
import tetgen
import gmsh
import os
import Sofa
import SofaRuntime, Sofa.Core,Sofa.Gui
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
import Sofa

def createScene(rootNode):
    # --- Step 1: Create the Rigid Body (Tactile Sensor) ---
    rootNode.addObject("RequiredPlugin", pluginName=['Sofa.Component.SolidMechanics.FEM.Elastic',
    'Sofa.Component.IO.Mesh','Sofa.Component.Mass',
    'Sofa.Component.Constraint.Lagrangian.Correction',
    'Sofa.Component.MechanicalLoad',
    'Sofa.Component.Constraint.Lagrangian.Solver'])
    sensorNode = rootNode.addChild('TactileSensor')
    sensorNode.addObject('MeshSTLLoader', name='digitLoader', filename='./meshes/digit_transformed2.stl')
    sensorNode.addObject('MechanicalObject', name='sensor', template='Rigid3d',
                            position=[0, 0, 0, 0, 0, 0, 1])  # Initial position and orientation
    sensorNode.addObject('UniformMass', totalMass=1.0)
    sensorNode.addObject('UncoupledConstraintCorrection')

    # --- Step 2: Create the Deformable Gel ---
    gelNode = rootNode.addChild('Gel')
    
    # Load the gel mesh (assuming the mesh is already prepared, such as an STL or OBJ file)
    gelNode.addObject('MeshVTKLoader', name='gelLoader', filename='meshes/mesh_gel_out.vtk')
    
    # Create a MechanicalObject for the gel, which is deformable (Vec3d)
    gelNode.addObject('MechanicalObject', name='gel', template='Vec3d',
                         position='@gelLoader.position')

    # Topology for the gel (can be triangles or tetrahedrons depending on the mesh)
    gelNode.addObject('TetrahedronSetTopologyContainer', name='topology',
                         tetrahedra='@gelLoader.tetrahedra')

    # Add elasticity (deformation) to the gel using a force field (FEM model)
    gelNode.addObject('TetrahedronFEMForceField', name='FEM', youngModulus=500, poissonRatio=0.45)

    # Add mass and damping to the deformable gel object
    gelNode.addObject('UniformMass', totalMass=0.1)
    gelNode.addObject('DiagonalVelocityDampingForceField', dampingCoefficient=0.1)

    # --- Step 3: Attach the Gel to the Sensor using RigidMapping ---
    
    # RigidMapping ensures that the gel follows the sensor's translation and rotation
    gelNode.addObject('RigidMapping', 
                         input='@../TactileSensor/sensor',  # Rigid sensor input
                         output='@gel')  # Deformable gel output

    # Optional: Add solvers and constraint corrections (if needed)
    gelNode.addObject('ConstantForceField', name="CFF", totalForce=[100.0, 0.0, 0.0, 0, 0, 0, 0])
    rootNode.addObject('CGSolver', name='cgSolver', iterations=25, tolerance=1e-9)
    rootNode.addObject('GenericConstraintSolver', maxIterations=100, tolerance=1e-6)

    return rootNode
 
if __name__ == '__main__':#
    root = Sofa.Core.Node("root")
    Sofa.Simulation.init(root)
    createScene(root)
    Sofa.Gui.GUIManager.Init("myscene", "qglviewer")
    Sofa.Gui.GUIManager.createGUI(root, __file__)
    Sofa.Gui.GUIManager.SetDimension(1080, 1080)
    Sofa.Gui.GUIManager.MainLoop(root)
    Sofa.Gui.GUIManager.closeGUI()