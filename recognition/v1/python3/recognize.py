#!/usr/bin/env python3

import argparse
from itertools import chain

import grpc

import recognition_pb2
import recognition_pb2_grpc


HOST = 'smartspeech.sber.ru'
MAX_CHUNK_SIZE = 2048

ENCODING_PCM = 'pcm'
ENCODING_OPUS = 'opus'
ENCODINGS_MAP = {
    ENCODING_PCM: recognition_pb2.RecognitionOptions.PCM_S16LE,
    ENCODING_OPUS: recognition_pb2.RecognitionOptions.OPUS
}


def try_printing_request_id(md):
    for m in md:
        if m.key == 'x-request-id':
            print('RequestID:', m.value)


def generate_audio_chunks(path):
    with open(path, 'rb') as f:
        for data in iter(lambda: f.read(MAX_CHUNK_SIZE), b''):
            yield recognition_pb2.RecognitionRequest(audio_chunk=data)


def recognize(args):
    ssl_cred = grpc.ssl_channel_credentials()

    token_cred = grpc.access_token_call_credentials(args.jwt)

    channel = grpc.secure_channel(
        HOST,
        grpc.composite_channel_credentials(ssl_cred, token_cred),
    )

    stub = recognition_pb2_grpc.SmartSpeechStub(channel)

    con = stub.Recognize(chain(
        (recognition_pb2.RecognitionRequest(options=args.recognition_options),),
        generate_audio_chunks(args.file),
    ))

    try:
        for resp in con:
            if not resp.eou:
                print('Got partial result:')
            else:
                print('Got final result:')

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
    NOT_RECOGNITION_OPTIONS = {'file', 'jwt', 'normalized_result', 'emotions_result'}
    DURATIONS = {'no_speech_timeout', 'max_speech_timeout', 'eou_timeout'}
    REPEATED = {'words'}
    HINTS_PREFIX = 'hints_'

    __slots__ = tuple(NOT_RECOGNITION_OPTIONS) + ('recognition_options',)

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

    def __getattr__(self, item):
        if item in self.__slots__:
            return None
        raise AttributeError(item)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--file', required=True, default=argparse.SUPPRESS, help='audio file for recognition')
    parser.add_argument('--jwt', required=True, default=argparse.SUPPRESS, help='authentication token')

    parser.add_argument('--normalized-result', default=argparse.SUPPRESS, action='store_true', help='show normalized text')
    parser.add_argument('--emotions-result', default=argparse.SUPPRESS, action='store_true', help='show emotions result')

    parser.add_argument('--audio-encoding', default=ENCODINGS_MAP[ENCODING_PCM], type=lambda x: ENCODINGS_MAP[x], help='{pcm,opus}')
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

    args = parser.parse_args(namespace=Arguments())

    recognize(args)


if __name__ == '__main__':
    main()
