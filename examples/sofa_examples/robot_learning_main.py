from meshlib import mrmeshpy
import tacto
import hydra
import cv2
import tacto.sofa_addon.sofaTactoLaunch as sofaTacto
import os
def changeToRootLayer():
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    new_working_dir=current_script_dir
    if current_script_dir.endswith("sofa_examples"):
# Go two directory levels up
        new_working_dir = os.path.abspath(os.path.join('..', '..',current_script_dir))
    if current_script_dir.endswith("examples"):
        new_working_dir = os.path.abspath(os.path.join('..',current_script_dir, ))
    # Change the working directory to the new directory
    os.chdir(new_working_dir)
@hydra.main(config_path="config", config_name="digit")
def main(cfg):
    bg = cv2.imread("examples/sofa_examples/config/bg_digit_240_320.jpg")
    
    digits = tacto.Sensor(**cfg.tacto)
    digits.add_camera([-1],**cfg.digit)
    digits.resetDebugVisualizerCamera(**cfg.pybullet_camera)
    
    digits.add_body(**cfg.object)
    #toSofa, fromSofa = Pipe()
    #tacto.sofa_addon.tactoEnvironment.tactoLaunch((toSofa, fromSofa),digits)
    sofaTacto.init(digits)






# Function used only if this script is called from a python environment
if __name__ == '__main__':
    main()
