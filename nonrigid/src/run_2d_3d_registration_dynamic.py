###############################################################
# Pipeline construction sample
# -------------------------------------------------------------
# This sample demonstrates how to construct and run a pipeline
# with scene generation, non-rigid deformation, partial
# intraoperative surface extraction and rigid misalignment.
# Run "python3 src/run_nonrigid_displacement.py --help" for an
# overview of parameters.
# -------------------------------------------------------------
# Copyright: 2022, Micha Pfeiffer, Eleonora Tagliabue
###############################################################

import argparse
import math

from core.pipeline import Pipeline
from core.dataset import Dataset
from core.log import Log
from blocks.copy_files.copy_files_block import CopyFilesBlock
from blocks.scene_objects.scene_object_generator_block import SceneObjectGeneratorBlock
from blocks.scene_generation.random_scene_block import RandomSceneBlock
from blocks.meshing.gmsh_meshing_block import GmshMeshingBlock
from blocks.simulation.simulation_block import SimulationBlock
from blocks.simulation.sofa.simulation_scene import SofaSimulation
from blocks.displacement.rigid_displacement_block import RigidDisplacementBlock, RotationMode, RigidDisplacementMode
from blocks.displacement.calc_displacement_block import CalcDisplacementBlock
from blocks.surface_extraction.surface_extraction_block import SurfaceExtractionBlock
from blocks.add_surface_noise.add_surface_noise_block import AddSurfaceNoiseBlock
from blocks.displacement.apply_displacement_block import ApplyDisplacementBlock
from core.objects.sceneobjects import Ligament, RigidOrgan, DeformableOrgan, AbdominalWall, FixedAttachments, Force, FillFat, Tumor
from blocks.rendering.rendering_block import RenderingBlock
from blocks.us.simple_us_simulation_block import SimpleUSSimulationBlock
from core.objects.baseobject import BaseObject

######################################
## Argument parsing:
parser = argparse.ArgumentParser("Sample run script")

Pipeline.add_arguments(parser)
Dataset.add_arguments(parser)
Log.add_arguments(parser)

parser.add_argument("--patient_input_file", type=str,
                    help="Custom organ mesh to be deformed")

args = parser.parse_args()

######################################
## Initialize logging:
Log.initialize( **vars(args) )

######################################
## Data loading:
dataset = Dataset(**vars(args))
dataset.print_state()

deformable_options = {
        "young_modulus":(3000,30000),
        "poisson_ratio":(0.45,0.48),
        "tag": "liver"
    }
if args.patient_input_file:
    deformable_options["source_file"] = "patient_input_mesh_rot.obj"

def_surface = f"{DeformableOrgan.file_basename}_A.{DeformableOrgan.file_extension}"

# Initialize the pipeline:
pipeline = Pipeline(**vars(args))


# Build the pipeline by adding blocks to it.
# The order used here is important - blocks will later be run in this order as well.

# If we were given patient data, use this as a basis for the scene.
if args.patient_input_file:
    # Copy the patient data to every sample:
    copy_block = CopyFilesBlock(
            path = args.patient_input_file,
            output_filename = "patient_input_mesh.obj"
            )
    pipeline.append_block(copy_block)

    rigid_init_block = RigidDisplacementBlock(
        input_filename = copy_block.output_filename,
        output_filename = "patient_input_mesh_rot.obj",
        max_rotate = math.pi*2, 
        max_translate = 0,
        rotation_center = RotationMode.mean
        )
    pipeline.append_block( rigid_init_block )

##-------------------------------------------
## Add blocks which create the scene objects:
scene_object_block = SceneObjectGeneratorBlock()
scene_object_block.add_object_template( DeformableOrgan, deformable_options )
scene_object_block.add_object_template( AbdominalWall, {
            "outset_amplitude":(0.03, 0.07),
            "outset_frequency":(3,10)
            })
scene_object_block.add_object_template( FillFat, {
            "fat_amount":(0.4,0.8),
            })
scene_object_block.add_object_template( RigidOrgan )
scene_object_block.add_object_template( RigidOrgan )
scene_object_block.add_object_template( RigidOrgan, {
            "ex_likelyhood":0.2
            })
scene_object_block.add_object_template( Ligament, {
            "stiffness":(100,250),
            "rest_length_factor":(0.5, 1.2)
            })
scene_object_block.add_object_template( Ligament, {
            "ex_likelyhood":0.7,
            "stiffness":(100,250),
            "rest_length_factor":(0.5, 1.2)
            })
scene_object_block.add_object_template( Ligament, {
            "ex_likelyhood":0.5,
            "stiffness":(100,250),
            "rest_length_factor":(0.5, 1.2)
            })
scene_object_block.add_object_template( FixedAttachments, {
            "surface_amount":(0.02, 0.07)
            })
scene_object_block.add_object_template( FixedAttachments, {
            "ex_likelyhood":0.2, "surface_amount":(0.02, 0.05), 
            })
n_tumors = 30
for i in range(n_tumors):
    scene_object_block.add_object_template( Tumor, {
                "structure_tag": "liver",
                "size_x": (0.005, 0.03),
                "size_y": (0.005, 0.03),
                "size_z": (0.005, 0.03),
                })
pipeline.append_block( scene_object_block )


scene_gen_block = RandomSceneBlock( pipeline.pipeline_blocks )
pipeline.append_block(scene_gen_block)

meshing_block = GmshMeshingBlock(
        input_filename = def_surface,
        output_filename = "preop_volume.vtk",
        )
pipeline.append_block(meshing_block)

FPS = 30
frame_time = 1/FPS
max_simulation_time = 2 # in seconds
max_num_frames = int(max_simulation_time*FPS)
simulation_block = SimulationBlock(
        simulation_filename = meshing_block.output_filename,
        surface_filename = def_surface,
        output_filename = "deformed.vtu",
        simulation_class=SofaSimulation,
        launch_gui=pipeline.launch_sofa_gui,
        export_time = frame_time,
        max_simulation_time = max_simulation_time,
    )
pipeline.append_block(simulation_block)

surface_extraction_block_0 = SurfaceExtractionBlock(
        input_filename = simulation_block.output_filename,
        output_filename = "intraop_surface.obj",
        surface_amount = (1, 1),        # Extract full surface!!
        )
pipeline.append_block(surface_extraction_block_0)

surface_extraction_block_intraop = SurfaceExtractionBlock(
        input_filename = def_surface,
        output_filename = "partial_surface.obj",
        surface_amount = (0.15, 0.6),
        w_normal = (0.5,0.75),
        w_distance = (0.75,1),
        w_noise = (0,0.3),
        )
pipeline.append_block(surface_extraction_block_intraop)

calc_displ_block = CalcDisplacementBlock(
        initial_mesh_filename="preop_volume.vtk",
        displaced_mesh_filename=simulation_block.output_filename,
        output_filename="preop_volume_with_displacement.vtu"
        )
pipeline.append_block(calc_displ_block)

apply_displ_block = ApplyDisplacementBlock(
        input_filename = "partial_surface.obj",
        input_displacement_filename = "preop_volume_with_displacement.vtu",
        output_filename = "partial_surface_intraop.obj",
        )
pipeline.append_block( apply_displ_block )

apply_displ_block = ApplyDisplacementBlock(
        input_filename = "abdominal_wall_A.obj",
        input_displacement_filename = "preop_volume_with_displacement.vtu",
        output_filename = "abdominal_wall_intraop_A.obj",
        radius = 0.05
        )
pipeline.append_block( apply_displ_block )

apply_displ_block = ApplyDisplacementBlock(
        input_filename = "abdominal_wall_fat_A.obj",
        input_displacement_filename = "preop_volume_with_displacement.vtu",
        output_filename = "abdominal_wall_fat_intraop_A.obj",
        radius = 0.05
        )
pipeline.append_block( apply_displ_block )

for i in range( n_tumors ):
    char_id = BaseObject.int_id_to_char(i)
    apply_displ_block = ApplyDisplacementBlock(
            input_filename = f"tumor_{char_id}.obj",
            input_displacement_filename = "preop_volume_with_displacement.vtu",
            output_filename = f"tumor_intraop_{char_id}.obj",
            radius = 0.05
            )
    pipeline.append_block( apply_displ_block )


us_block = SimpleUSSimulationBlock(
        internal_filenames = ["tumor_intraop_A.obj", "tumor_intraop_B.obj"],
        surface_filename = "partial_surface.obj",
        simulation_block = simulation_block,
        )
pipeline.append_block( us_block )

# Create a list of all objects we want to appear in the 2d renders.
# Assign properties (like color) to each of them.
# Note that these may partially overlap with the scene objects defined earlier, but
# don't have to, which makes this a little more complicated than just passing the
# scene objects.
target_object = {"filepattern":"intraop_surface.obj", "color":(0.6,0.3,0.1,1), "frame_start":1, "frame_end":max_num_frames }
objs_to_render = []
objs_to_render.append( {"filepattern":"abdominal_wall_intraop_A.obj", "color":(0.8,0.3,0.1,1), "frame_start":1, "frame_end":max_num_frames } )
objs_to_render.append( {"filepattern":"abdominal_wall_fat_intraop_A.obj", "color":(0.8,0.7,0.2,1), "frame_start":1, "frame_end":max_num_frames } )
for i in range( n_tumors ):
    char_id = BaseObject.int_id_to_char(i)
    color = (0.7+float(i)/n_tumors*0.3,1,0.1,1)
    objs_to_render.append( {"filepattern":f"tumor_intraop_{char_id}.obj", "color":color, "frame_start":1, "frame_end":max_num_frames } )
objs_to_render.append( {"filepattern":"attached_organ_A.obj", "color":(0.5,0.5,0.5,1) } )
objs_to_render.append( {"filepattern":"attached_organ_B.obj", "color":(0.55,0.55,0.55,1) } )
#objs_to_render.append( {"filepattern":f"partial_surface_intraop.obj", "color":(0.5,0.9,0.5,1) } )
#, "render_late":True } )
#objs_to_render.append( {"filepattern":f"{RigidOrgan.filepattern()}.", color=(0.5,0.5,0.5,1) } )
rendering_block = RenderingBlock( target_object, objs_to_render, max_num_frames=max_num_frames,
        simulation_block = simulation_block )
pipeline.append_block( rendering_block )


# voxelizationBlock = VoxelizationBlock(
#         inputs = [
#             {"filename": calc_displ_block.output_filename, "signed": True, "with_arrays": True},
#             ],
#         output_filename = "voxelized.vts"
#         )
# pipeline.append_block(voxelizationBlock)


######################################
## List of plots we want the pipeline to create:
pipeline.add_plot( {
        "type":"HISTOGRAM",
        "key":"stats|CalcDisplacementBlock_0|mean_displacement",
        "display_name":"Mean Displacement (m)"
    } )
pipeline.add_plot( {
        "type":"HISTOGRAM",
        "key":"stats|CalcDisplacementBlock_0|max_displacement",
        "display_name":"Max Displacement (m)"
    } )
pipeline.add_plot( {
        "type":"HISTOGRAM",
        "key":"stats|SurfaceExtractionBlock_1|partial_surface_area",
        "display_name":"Surface area (m^2)"
    } )
pipeline.add_plot( {
        "type":"HISTOGRAM",
        "key":"stats|SurfaceExtractionBlock_0|intraop_surface_num_points",
        "display_name":"Number of points"
    } )
pipeline.add_plot( {
        "type":"SCATTER",
        "y_key":"stats|CalcDisplacementBlock_0|mean_displacement",
        "x_key":"stats|CalcDisplacementBlock_0|mean_displacement",
        "display_name":"Mean Displacement (m)"
    } )


######################################
# Execute the pipeline, run each block for each sample in dataset:
pipeline.run( dataset )


