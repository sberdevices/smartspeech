# Installation

    $ pip3 install grpcio-tools
    $ python3 -m grpc_tools.protoc -I .. --python_out=. --grpc_python_out=. ../recognition.proto

# Usage

    $ python3 recognize.py --token "<access_token>" --file "<file>"
