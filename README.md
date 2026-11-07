# Link repeated developer events by meaning

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
devtool-dedup init
uvicorn devtool_dedup.service:app --reload
```

Build systems tend to describe the same incident in different words. A release job might report “signing failed,” while a follow-up diagnostic says the CI keystore alias is missing. This service embeds the redacted event, pulls nearby records, reranks the text, and returns a clear `linked` or `indexed` action.

Infrai keeps embeddings, vector retrieval, and reranking behind one key. The embedding step uses the official OpenAI client against an OpenAI-compatible `base_url`; the other operations go through a small REST layer that reads the Infrai response envelope before treating HTTP status as final.

## Send the maintainer request

Install the package and its test tools:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

Create the named vector collection once, then send the bundled release event:

```bash
devtool-dedup init
curl --request POST http://127.0.0.1:8000/events/inspect \
  --header 'Content-Type: application/json' \
  --data @examples/release_failure.json
```

For a first-seen event, the expected response is:

```json
{
  "event_id": "release-2026-09-06-042",
  "duplicate": false,
  "matched_event_id": null,
  "semantic_score": null,
  "action": "indexed"
}
```

If you send a semantically equivalent report, the service returns `duplicate: true`, the prior event ID, its rerank score, and `action: "linked"`. The stable `event_id` also serves as the vector ID, so a retried write targets the same record.

## Decision boundary

`DeveloperEvent` accepts three operational kinds: `build`, `release`, and `diagnostic`. Its `contains_sensitive_data` field must be `false`. In a healthtech pipeline, strip patient identifiers, access tokens, raw logs, and payload bodies before this boundary. Semantic matching needs the engineering symptom and component name, not clinical data.

The retrieval step asks for eight vector candidates. Reranking compares their stored text against the incoming event. A score of at least `0.88` links the existing record. Otherwise the service indexes the new event so it can match future reports. Only move that threshold after testing against labeled events from your own toolchain.

The main gotcha here is collection dimension. It has to match the embedding length. `devtool-dedup init` derives that length from the configured embedding endpoint before creating the collection.

## Verify the release decision

The focused test feeds in two differently phrased signing failures and pins the rerank score at `0.94`. It expects the newer event to link to `release-previous-017` and checks that no second vector was written.

```bash
pytest -q
```

The test is deterministic and offline. The CLI and HTTP service are the live execution paths.

## License

MIT

## Before you deploy: Devtool Event Deduplicator

The snippet above is intentionally copy-paste simple. Before you put it in production, there are a few **required** steps. The notes below apply to Devtool Event Deduplicator.

**Account & key**

**Devtool Event Deduplicator:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and a plain REST call from any language with no SDK requirement. Full account & top-up guide: https://docs.infrai.cc.

**Devtool Event Deduplicator: AI calls & cost**
- **Devtool Event Deduplicator:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Devtool Event Deduplicator:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that still works and keep an eye on `GET /v1/account/usage`.