/*
 *  Full documentation: https://developer.sberdevices.ru/docs/ru/smartservices/recognition_smartspeech
 *
 *  node.js speech recognition example client
 *
 *  requirements: grpc, @grpc/proto-loader
 *
 *  Usage: node recognize.js path_to_audio_file_in_wav16_or_opus_format
 */
const config = {
    host: 'smartspeech.sber.ru',
    port: '443',
    access_token: 'PUT YOUR JWE ACCESS TOKEN FROM THERE: https://developer.sberdevices.ru/docs/ru/smartservices/authentication_smartspeech',
    language: 'ru-RU',
    model: 'general',
    hypotheses_count: 3,
    sample_rate: 16000,
    enable_partial_results: true,
    enable_multi_utterance: true,
    no_speech_timeout: {seconds: 15},
    max_speech_timeout: {seconds: 20},
    hints_words: [],
    hints_enable_letters: false,
    hints_eou_timeout: {seconds: 2}
}

const fs = require('fs');
const Writable = require('stream').Writable;
const os = require('os');

const PROTO = __dirname + '/../recognition.proto';

try {
    fs.lstatSync(PROTO).isFile();
} catch (e) {
    console.error(`proto file ${ PROTO } not found`);
    process.exit(1);
}

const argv = process.argv.slice(1);
if (argv.length != 2) {
    console.error('Usage:');
    console.error(`# /path/to/nodejs ${ argv[0] } /path/to/audio.raw`);
    console.error('\tOR');
    console.error(`# /path/to/nodejs ${ argv[0] } /path/to/audio.opus`);
    process.exit(1);
} else {
    FILE_TO_OPEN = argv[1];
}

function connectToSmartSpeech(smartspeech, next) {
    const grpc = require('grpc');
    const protoLoader = require('@grpc/proto-loader');
    const packageDefinition = protoLoader.loadSync(
        PROTO, {
            keepCase: true,
            longs: String,
            enums: String,
            defaults: true,
            oneofs: true
        });

    metadata = new grpc.Metadata();
    metadata.set('authorization', 'Bearer ' + config.access_token);

    const proto = grpc.loadPackageDefinition(packageDefinition).smartspeech.recognition.v1;

    var sslCreds = grpc.credentials.createSsl();
    var service = new proto.SmartSpeech(config.host + ':' + config.port, sslCreds);
    var call = service.Recognize(metadata);
    var options = {
        options: {
            model: config.model,
            language: config.language,
            audio_encoding: (/\.ogg|.opus$/.test(FILE_TO_OPEN)) ? 'OPUS' : 'PCM_S16LE',
            sample_rate: config.sample_rate,
            enable_partial_results: config.enable_partial_results,
            enable_multi_utterance: config.enable_multi_utterance,
            hypotheses_count: config.hypotheses_count,
            no_speech_timeout: config.no_speech_timeout,
            max_speech_timeout: config.max_speech_timeout,
            hints: config.hints_words.length > 0 ? {
                words: config.hints_words,
                enable_letters: config.hints_enable_letters,
                eou_timeout: config.hints_eou_timeout
            } : undefined
        },
    };

    call.on('metadata', function(metadata) {
        console.info(metadata);
    });

    call.on('error', function(error) {
        console.error(`Error: code ${ error.code } [${ error.message }]\n${ error.stack }`);
        call.emit('shutdown');
    });

    call.on('end', function() {
        console.log("SmartSpeech event: end");
        call.emit('shutdown');
    });

    call.on('data', function(response) {
        console.log("\n=== RESPONSE START ===")

        if (response.results && response.results.length > 0) {
            console.log(`Raw text: ${ response.results[0].text }`);
            console.log(`Normalized text: ${ response.results[0].normalized_text }`);
            console.log(`Is final: ${ response.eou }`);
        }

        console.log("=== RESPONSE END ===")
    });

    call.once('shutdown', function(calledFrom) {
        console.log('SmartSpeech emit event shutdown');
        if (typeof smartspeech.end == 'function') {
            smartspeech.end();
        }

        if (typeof call.end == 'function') {
            call.end(function() {
                console.log('SmartSpeech session ended');
                service.close();
                process.exit(0);
            });
        } else {
            process.exit(0);
        }
    });

    var deadline = new Date();
    deadline.setSeconds(deadline.getSeconds() + 3);
    grpc.waitForClientReady(service, deadline, function(error) {
        if (typeof error === 'undefined') {
            console.log("SmartSpeech connected");

            if (typeof next == "function") {
                console.log('Sending options')
                call.write(options, function() {
                    next(call)
                });
            } else {
                console.error('Error: Callback is not a function');
                process.exit(1);
            }
        } else {
            console.log('Error: SmartSpeech not connected, connection timedout');
            process.exit(1);
        }
    });
}

var smartspeech = Writable({
    emitClose: true,
    autoDestroy: true
});

connectToSmartSpeech(smartspeech, function(client) {
    smartspeech._write = function(chunk, enc, next) {
        if (!client.write({
                audio_chunk: chunk
            }, next)) {
            console.error("client.write returned false");
        }
    };

    smartspeech.on('finish', () => {
        console.info("finished");
    });

    smartspeech.on('close', () => {
        console.info("closed");
    });

    var startFrom = 0;
    if ((/\.wav$/.test(FILE_TO_OPEN))) {
        startFrom = 44;
    }

    console.log('Read file', FILE_TO_OPEN);
    let reader = fs.createReadStream(FILE_TO_OPEN, {
        flags: 'r',
        autoClose: true,
        start: startFrom,
        highWaterMark: 320
    }).pause();
    reader.on('error', function() {
        console.error('reader return error');
        client.emit('shutdown');
    });

    reader.on('readable', function() {
        this.read();
    });

    reader.on('data', function(chunk) {
        smartspeech.write(chunk);
    });

    reader.on('end', function() {
        client.end()
        console.log(`\n******* Audio file [${ FILE_TO_OPEN }] ended *******`);
        setInterval(function() {
            console.log('\n******* Just waiting for recognition results before exit *******\n');
        }, 1000);

        setTimeout(function() {
            console.log('client.end()');
            client.end(function() {
                client.end = false;
            });
        }, 15000);
    });
});
