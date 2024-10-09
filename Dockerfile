FROM sofa_tacto_image AS build





#USER root

# Change ownership of the relevant files
#RUN chown -R user:user /home/user
USER user
COPY --chown=user:user . /home/user
WORKDIR /home/user

RUN /opt/conda/bin/conda init bash
COPY --chown=user:user start.sh /home/user/start.sh
#RUN ./start.sh
    # Create a script to run the Python script with the activated conda environment
# Entry point to ensure Conda and environment are loaded before running the script
#ENTRYPOINT ["bash", "-c", "source ~/.bashrc && while true; do sleep 1000; done"]
ENTRYPOINT ["./start.sh"]
#ENTRYPOINT ["bash", "-c", "source /root/.bashrc && source ~/.bashrc && python examples/sofa_examples/robot_learning_main.py"]
#ENTRYPOINT ["bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate robot_learning  && cd examples && python demo_pybullet_digit.py"]