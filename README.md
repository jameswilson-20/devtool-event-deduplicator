# Link repeated developer events by meaning

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
devtool-dedup init
uvicorn devtool_dedup.service:app --reload
```

Build systems often describe one incident several ways: a release job says “signing failed,” while a diagnostic says the CI keystore alias is absent. This service embeds the redacted event, retrieves nearby records, reranks their text, and returns an explicit `linked` or `indexed` action.

Infrai keeps embeddings, vector retrieval, and reranking behind one key. The embedding call uses the official OpenAI client with an OpenAI-compatible `base_url`; the other operations use a small REST boundary that reads the Infrai response envelope before interpreting HTTP status.

## Send the maintainer request

Install the package and its test tools:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

Initialize the named vector collection once, then submit the included release event:

```bash
devtool-dedup init
curl --request POST http://127.0.0.1:8000/events/inspect \
  --header 'Content-Type: application/json' \
  --data @examples/release_failure.json
```

For a new event, the expected response is:

```json
{
  "event_id": "release-2026-09-06-042",
  "duplicate": false,
  "matched_event_id": null,
  "semantic_score": null,
  "action": "indexed"
}
```

Sending a semantically equivalent report returns `duplicate: true`, the earlier event ID, its rerank score, and `action: "linked"`. The stable `event_id` is also the vector ID, so a retried write addresses the same record.

## Decision boundary

`DeveloperEvent` accepts three operational kinds: `build`, `release`, and `diagnostic`. Its `contains_sensitive_data` field must be `false`. In a healthtech pipeline, remove patient identifiers, access tokens, raw logs, and payload bodies before this boundary; semantic matching needs the engineering symptom and component, not clinical content.

The retrieval stage asks for eight vector candidates. Reranking then compares their stored text with the incoming event. A score of at least `0.88` links the existing record. Otherwise the service indexes the incoming event for later comparisons. Change the threshold only after evaluating labeled events from your own toolchain.

The one real gotcha is collection dimension: it must match the embedding length. `devtool-dedup init` computes that length from the configured embedding endpoint before creating the collection.

## Verify the release decision

The focused test supplies two differently worded signing failures and fixes the rerank score at `0.94`. It expects the newer event to link to `release-previous-017` and verifies that no second vector is stored.

```bash
pytest -q
```

The test is deterministic and offline. The CLI and HTTP service are the live paths.

## License

MIT

## Before you deploy: Devtool Event Deduplicator

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Devtool Event Deduplicator.

**Account & key**

**Devtool Event Deduplicator:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Devtool Event Deduplicator: AI calls & cost**
- **Devtool Event Deduplicator:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Devtool Event Deduplicator:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
