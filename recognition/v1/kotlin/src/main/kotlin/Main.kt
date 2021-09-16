import com.xenomachina.argparser.ArgParser
import com.xenomachina.argparser.default
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import java.io.File

class CommandLineArgs(parser: ArgParser) {
    val host by parser.storing("--host", help = "smartspeech host").default("smartspeech.sber.ru")
    val token by parser.storing("--token", help = "smartspeech access token")
    val inputFile by parser.storing("--in", help = "input file")
    val sampleRate by parser.storing("--sr", help = "input file sample rate") { toInt() }.default { 16000 }
}

fun main(args: Array<String>) = runBlocking {
    val parsedArgs = ArgParser(args).parseInto(::CommandLineArgs)
    parsedArgs.run {
        println(
            """ recognize: 
            host = $host
            token = $token
            inputFile = $inputFile
            sampleRate = $sampleRate
        """.trimIndent()
        )
    }

    val smartSpeechGrpcClient = SmartSpeechGrpcClient(parsedArgs.host) { parsedArgs.token }
    val smartSpeechConnection = smartSpeechGrpcClient.createConnection().apply {
        sampleRate = parsedArgs.sampleRate
    }

    val readFileFlow = flow {
        File(parsedArgs.inputFile).inputStream().use { input ->
            while (true) {
                val opusBuffer = ByteArray(4096)
                if (input.read(opusBuffer) <= 0) break
                emit(opusBuffer)
                delay(100)
            }
        }
    }

    val recognitionResultsFlow = smartSpeechConnection.startRecognizing(readFileFlow)
    recognitionResultsFlow.collect { result ->
        println(">> ${result.text}")
    }
}