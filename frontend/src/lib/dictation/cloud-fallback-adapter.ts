import type { DictationAdapter } from "@assistant-ui/react"
import { dictationApi } from "@/api/dictation"

type Unsubscribe = () => void

/**
 * Cloud fallback dictation adapter.
 *
 * Uses MediaRecorder to capture audio, then sends it to the backend
 * POST /api/v1/dictation/transcribe endpoint for transcription via
 * OpenAI Whisper. Returns a single final result (no interim/partial).
 */
export class CloudFallbackDictationAdapter implements DictationAdapter {
  private language: string

  constructor(options?: { language?: string }) {
    this.language = options?.language ?? "fr"
  }

  /** Disable typing while recording since there are no interim results. */
  disableInputDuringDictation = true

  listen(): DictationAdapter.Session {
    let status: DictationAdapter.Status = { type: "starting" }

    const speechStartCbs: Array<() => void> = []
    const speechEndCbs: Array<(r: DictationAdapter.Result) => void> = []
    const speechCbs: Array<(r: DictationAdapter.Result) => void> = []

    let mediaRecorder: MediaRecorder | null = null
    let chunks: Blob[] = []
    let resolveStop: (() => void) | null = null

    // Start recording
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm"

        mediaRecorder = new MediaRecorder(stream, { mimeType })
        chunks = []

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data)
        }

        mediaRecorder.onstop = async () => {
          // Release mic
          stream.getTracks().forEach((t) => t.stop())

          const blob = new Blob(chunks, { type: mimeType })

          try {
            const result = await dictationApi.transcribe(blob, this.language)

            const dictResult: DictationAdapter.Result = {
              transcript: result.text,
              isFinal: true,
            }
            speechCbs.forEach((cb) => cb(dictResult))
            speechEndCbs.forEach((cb) => cb(dictResult))
          } catch {
            const emptyResult: DictationAdapter.Result = {
              transcript: "",
              isFinal: true,
            }
            speechEndCbs.forEach((cb) => cb(emptyResult))
          }

          status = { type: "ended", reason: "stopped" }
          resolveStop?.()
        }

        mediaRecorder.start(250)
        status = { type: "running" }
        speechStartCbs.forEach((cb) => cb())
      })
      .catch(() => {
        status = { type: "ended", reason: "error" }
        const emptyResult: DictationAdapter.Result = {
          transcript: "",
          isFinal: true,
        }
        speechEndCbs.forEach((cb) => cb(emptyResult))
        resolveStop?.()
      })

    return {
      get status() {
        return status
      },

      stop: () =>
        new Promise<void>((resolve) => {
          resolveStop = resolve
          if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop()
          } else {
            resolve()
          }
        }),

      cancel: () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
          mediaRecorder.stream.getTracks().forEach((t) => t.stop())
          mediaRecorder.stop()
        }
        status = { type: "ended", reason: "cancelled" }
      },

      onSpeechStart: (cb: () => void): Unsubscribe => {
        speechStartCbs.push(cb)
        return () => {
          const i = speechStartCbs.indexOf(cb)
          if (i >= 0) speechStartCbs.splice(i, 1)
        }
      },

      onSpeechEnd: (
        cb: (result: DictationAdapter.Result) => void
      ): Unsubscribe => {
        speechEndCbs.push(cb)
        return () => {
          const i = speechEndCbs.indexOf(cb)
          if (i >= 0) speechEndCbs.splice(i, 1)
        }
      },

      onSpeech: (
        cb: (result: DictationAdapter.Result) => void
      ): Unsubscribe => {
        speechCbs.push(cb)
        return () => {
          const i = speechCbs.indexOf(cb)
          if (i >= 0) speechCbs.splice(i, 1)
        }
      },
    }
  }
}
