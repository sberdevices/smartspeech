# Installation

    $ pip3 install grpcio-tools
    $ python3 -m grpc_tools.protoc -I .. --python_out=. --grpc_python_out=. ../synthesis.proto

# Usage

    $ python3 synthesize.py --jwt "<jwt>" --file "<file>" --text "<text>"
