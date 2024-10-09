#!/bin/bash
docker build -f Dockerfile.base -t sofa_tacto_image .
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x $SCRIPT_DIR/tactoSofa
# Check if tactoSofa is already in the PATH
if ! command -v tactoSofa &> /dev/null; then
    echo "tactoSofa not found in PATH. Adding it to ~/.bashrc."

    # Add the script directory to the PATH in ~/.bashrc
    echo "export PATH=\$PATH:$SCRIPT_DIR" >> ~/.bashrc

    # Source the updated ~/.bashrc
    source ~/.bashrc

    echo "tactoSofa added to PATH and ~/.bashrc updated."
else
    echo "tactoSofa is already in the PATH."
fi
