#!/usr/bin/env python3

import argparse
import itertools
import time

import grpc

import recognition_pb2
import recognition_pb2_grpc

import requests
import pyaudio
import wave
import uuid
import base64

CHUNK_SIZE = 2048
SLEEP_TIME = 0.1

ENCODING_PCM = 'pcm'

ENCODINGS_MAP = {
    ENCODING_PCM: recognition_pb2.RecognitionOptions.PCM_S16LE,
    'opus': recognition_pb2.RecognitionOptions.OPUS,
    'mp3': recognition_pb2.RecognitionOptions.MP3,
    'flac': recognition_pb2.RecognitionOptions.FLAC,
    'alaw': recognition_pb2.RecognitionOptions.ALAW,
    'mulaw': recognition_pb2.RecognitionOptions.MULAW,
}


def auth(client_id, client_secret):
    auth_code = base64.b64encode(bytes(f"{client_id}:{client_secret}", "ascii")).decode('ascii')
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {auth_code}"
        }
    res = requests.post('https://salute.online.sberbank.ru:9443/api/v2/oauth', headers=headers, data="scope=SBER_SPEECH")
    if res.ok:
        data = res.json()
        return res.json().get("access_token", None)
    else:
        print(f"Error {res.status_code}, {res.text}")
        return None

def try_printing_request_id(md):
    for m in md:
        if m.key == 'x-request-id':
            print('RequestID:', m.value)


def generate_audio_chunks(path, mic, recognition_options, chunk_size=CHUNK_SIZE, sleep_time=SLEEP_TIME):
    if path:
        with open(path, 'rb') as f:
            for data in iter(lambda: f.read(chunk_size), b''):
                yield recognition_pb2.RecognitionRequest(audio_chunk=data)
                time.sleep(sleep_time)
    elif mic:
        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1,
            rate=recognition_options.sample_rate, input=True,
            frames_per_buffer=CHUNK_SIZE)
        print("Recording...")
        while True:
            data = stream.read(CHUNK_SIZE)
            yield recognition_pb2.RecognitionRequest(audio_chunk=data)
    else:
        print("User --file or --mic argument")
        exit(1)


def recognize(args):
    token = None
    if not hasattr(args, "token"):
        if not hasattr(args, "client_id") and not hasattr(args, "client_secret"):
            print("Use token or client_id + client_secret arguments.")
            exit(1)
        else:
            token = auth(args.client_id, args.client_secret)
    else:
        token = args.token

    ssl_cred = grpc.ssl_channel_credentials()
    token_cred = grpc.access_token_call_credentials(token)

    channel = grpc.secure_channel(
        args.host,
        grpc.composite_channel_credentials(ssl_cred, token_cred),
    )

    stub = recognition_pb2_grpc.SmartSpeechStub(channel)

    con = stub.Recognize(itertools.chain(
        (recognition_pb2.RecognitionRequest(options=args.recognition_options),),
        generate_audio_chunks(args.file, args.mic, args.recognition_options),
    ))

    try:
        for resp in con:
            if not resp.eou:
                print('Got partial result:')
            else:
                print('Got end-of-utterance result:')

            for i, hyp in enumerate(resp.results):
                print('  Hyp #{}: {}'.format(i + 1, hyp.normalized_text if args.normalized_result else hyp.text))

            if resp.eou and args.emotions_result:
                print('  Emotions: pos={}, neu={}, neg={}'.format(
                    resp.emotions_result.positive,
                    resp.emotions_result.neutral,
                    resp.emotions_result.negative,
                ))
    except grpc.RpcError as err:
        print('RPC error: code = {}, details = {}'.format(err.code(), err.details()))
    except Exception as exc:
        print('Exception:', exc)
    else:
        print('Recognition has finished')
    finally:
        try_printing_request_id(con.initial_metadata())
        channel.close()


class Arguments:
    NOT_RECOGNITION_OPTIONS = {'host', 'token', 'client_id', 'client_secret', 'file', 'mic', 'normalized_result', 'emotions_result'}
    NOT_RECOGNITION_OPTIONS.update({'ca', 'cert', 'key'})  # diff
    DURATIONS = {'no_speech_timeout', 'max_speech_timeout', 'eou_timeout'}
    REPEATED = {'words'}
    HINTS_PREFIX = 'hints_'

    def __init__(self):
        super().__setattr__('recognition_options', recognition_pb2.RecognitionOptions())

    def __setattr__(self, key, value):
        if key in self.NOT_RECOGNITION_OPTIONS:
            super().__setattr__(key, value)
        elif key.startswith(self.HINTS_PREFIX):
            key = key[len(self.HINTS_PREFIX):]
            self._set_option(self.recognition_options.hints, key, value)
        else:
            self._set_option(self.recognition_options, key, value)

    def _set_option(self, obj, key, value):
        if key in self.DURATIONS:
            getattr(obj, key).FromJsonString(value)
        elif key in self.REPEATED:
            if value:
                getattr(obj, key).extend(value)
        else:
            setattr(obj, key, value)


def create_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--host', default='smartspeech.sber.ru', help='host:port of gRPC endpoint')
    parser.add_argument('--token', required=False, default=argparse.SUPPRESS, help='access token')
    parser.add_argument('--client_id', required=False, default=argparse.SUPPRESS, help='client id (instead of token)')
    parser.add_argument('--client_secret', required=False, default=argparse.SUPPRESS, help='client id (instead of token)')
    parser.add_argument('--file', required=False, default="", help='audio file for recognition')
    parser.add_argument('--mic', action='store_true', help=' ')

    parser.add_argument('--normalized-result', action='store_true', help='show normalized text')
    parser.add_argument('--emotions-result', action='store_true', help='show emotions result')

    parser.add_argument('--audio-encoding', default=ENCODINGS_MAP[ENCODING_PCM], type=lambda x: ENCODINGS_MAP[x], help=str(list(ENCODINGS_MAP)))
    parser.add_argument('--sample-rate', default=16000, type=int, help='PCM only')
    parser.add_argument('--model', default='general', help=' ')
    parser.add_argument('--hypotheses-count', default=1, type=int, help=' ')
    parser.add_argument('--enable-profanity-filter', action='store_true', help=' ')
    parser.add_argument('--enable-multi-utterance', action='store_true', help=' ')
    parser.add_argument('--enable-partial-results', action='store_true', help=' ')
    parser.add_argument('--no-speech-timeout', default='7s', help=' ')
    parser.add_argument('--max-speech-timeout', default='20s', help=' ')
    parser.add_argument('--hints-words', nargs='*', default=[], help=' ')
    parser.add_argument('--hints-enable-letters', action='store_true', help=' ')
    parser.add_argument('--hints-eou-timeout', default='0s', help=' ')
    parser.add_argument('--channels-count', default=1, type=int, help=' ')

    return parser


def main():
    parser = create_parser()

    recognize(parser.parse_args(namespace=Arguments()))


if __name__ == '__main__':
    main()
