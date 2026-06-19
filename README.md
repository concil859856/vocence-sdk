# Vocence SDK

Official client libraries for the [Vocence](https://vocence.ai) Developer API —
voice cloning, TTS, STT, voice design, and real-time voice agents on the
Bittensor subnet.

## Languages

| Language | Path | Status |
|---|---|---|
| Python | [`python/`](python/) | v0.1 |

More language bindings (TypeScript, Go) will live as siblings under this repo.

## API Reference

The underlying REST + WebSocket surface is documented at
[vocence.ai/docs/api](https://vocence.ai/docs/api). Each SDK mirrors the
endpoints there 1:1 with idiomatic, typed methods.

## Related: `vocence-plugins`

For developers who run their own real-time voice-agent pipeline and just want
to swap in Vocence voices and recognition,
[`vocence-plugins`](https://pypi.org/project/vocence-plugins/) ships
drop-in `VocenceTTS` and `VocenceSTT` components. They conform to the
standard streaming TTS / STT abstract interfaces, so they slot into any
compatible agent framework. The two packages don't overlap:

| Use case | Use |
|---|---|
| Talk to a Vocence-hosted voice agent (REST + WebSocket to our service) | `vocence` (this SDK) |
| Build your own agent pipeline with Vocence voices + recognition | [`vocence-plugins`](https://pypi.org/project/vocence-plugins/) |

Both authenticate with the same `voc_live_…` developer key.

## License

Apache 2.0 — see [LICENSE](LICENSE).
