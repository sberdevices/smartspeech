# Installation

    $ pip3 install grpcio-tools
    $ python3 -m grpc_tools.protoc -I .. -I ../../../task/v1 --python_out=. --grpc_python_out=. ../recognition.proto ../../../task/v1/{storage,task}.proto

# Usage

    $ python3 recognize.py --token "<access_token>" --file "<file>"
    
    $ python3 recognize_async.py --token "<access_token>" --file "<file>" --output "<result>"
