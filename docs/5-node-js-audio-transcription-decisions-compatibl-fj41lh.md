# 5 Node.js Audio Transcription Decisions — Compatible Model Fallback for CRM

Keep the Node.js sales-call service behind an OpenAI-compatible audio transcription contract, and check model readiness before choosing a fallback. For a media sales team, switching speech providers should leave the code that proposes CRM actions unchanged. The deciding constraint is whether a replacement can preserve the meaning of a follow-up, including who said it and whether anyone actually agreed to it.

TL;DR: For Node.js services using OpenAI-compatible transcription, check that the intended ASR model is available, distinguish malformed multipart requests from transient transport failures, and switch only to an approved provider. Keep transcript generation separate from CRM writes. A retry must not create a second task or turn an internal reminder into an unsolicited email or SMS.

This decision record treats portability as a controlled change to a sales operation. The example is a media account executive discussing a sponsorship renewal with an advertiser; the output is a proposed CRM follow-up, subject to review. It is an illustrative workload, not a production incident or a measured comparison.

## 1. How should a Node.js service handle unavailable models for compatible audio transcriptions?

The contract should describe what the CRM consumer needs: a call identifier, transcript text, the selected provider, and evidence supporting a proposed action. Keep provider response fields inside adapters. Speaker labels, timestamps, and extraction confidence should enter the application contract only after their semantics have been checked for each candidate. A field with a familiar name can still mean something different.

Preserve the evidence.

Consider this illustrative sentence: “Send the revised sponsorship proposal on Friday; don't text the client until the agency approves it.” An action extractor could reasonably propose a proposal-review task. It should not interpret the mention of texting as permission to send a message. The failure boundary is semantic: a valid transcript response does not authorize a CRM mutation, and a CRM task does not establish consent for an outbound campaign. Keep those decisions separate, especially when a new provider changes punctuation or speaker attribution.

Require the same call ID and recording revision to remain attached to every attempt. An adapter change may produce a new transcript candidate, but it must not create a new business event. Retain the original recording reference under the team's access and retention policy, and define who can view transcript evidence before copying it into CRM notes. No universal retention period follows from an API protocol.

The trade-off: extra adapter and review work buys a stable CRM contract, while differences that affect meaning remain visible.

## 2. Separate readiness, payload errors, and retry budgets

A model name is not a readiness guarantee. Use the catalog's explicit availability signal to decide whether to send the recording. If the selected ASR model is marked unavailable, choose an approved alternative or hold the job; repeatedly submitting the same audio does not change that decision. Bind the check to the selected model, rather than accepting the presence of any model as sufficient.

Readiness can change between a check and a request. Treat the check as an admission decision, then handle the actual response independently. For transient timeouts, use bounded exponential backoff; for rate limiting, honor Retry-After when present and avoid immediate retry loops. Set the attempt budget from the CRM follow-up deadline and leave enough time for a replacement provider. There is no useful universal retry count for every recording length and sales process.

A malformed multipart request belongs on a different branch. Verify the audio part, encoding, and required model selection before treating a rejected upload as a reason to switch vendors. Moving an invalid request between adapters can multiply attempts while hiding the original defect. Surface the response status and diagnostic body to the operator, with sensitive content removed from logs.

Then stop retrying.

The fallback boundary also needs a data decision. An approved primary provider does not automatically make every alternative an approved recipient of recorded advertiser conversations. If the alternative's processing terms or permitted region have not been accepted, leave the job pending for review. Portability includes the ability to hold work safely.

## 3. Compare the replacement boundary in one table

Use OpenAI, Deepgram, and AssemblyAI as real candidates for a transcription adapter evaluation. The table compares proposed integration choices and acceptance requirements; it does not claim equal accuracy, interchangeable response schemas, or a measured winner. The same fixture set should decide which candidates qualify for the media workflow.

| Option | Proposed integration boundary | Why consider it | Limitation and acceptance condition |
| --- | --- | --- | --- |
| OpenAI | An adapter around its documented audio transcription interface | Provides a concrete reference for a service already using an OpenAI-compatible request shape | Request compatibility does not prove equivalent transcript meaning; check the selected model and normalize the response |
| Deepgram | A separate adapter using its documented interface | Tests whether the application contract can survive a change beyond its original request format | Budget for request and response mapping; qualify speaker attribution and action evidence before enabling automatic routing |
| AssemblyAI | A separate adapter using its documented interface | Provides another independent candidate for the same recording and CRM fixture set | Verify the chosen interface's completion behavior and error handling; keep any provider job state out of the CRM consumer |
| Gemini | A candidate for the downstream action-extraction evaluation | Lets the team evaluate its summary and evidence contract separately from ASR | This is a summarizer comparison, not a claim of drop-in compatibility with the transcription interface; verify the chosen model and input support |
| Claude | Another candidate for downstream action extraction from normalized text | Makes extraction portability an independent decision from speech-provider portability | Requires its own adapter evaluation; do not route audio requests to it merely because text summarization is being considered |
| A shared backend API | An adapter around a stable capability contract | Can preserve client code when the vendor behind a supported capability changes | Qualify the selected capability and model before use; protocol compatibility alone does not establish workload suitability |

A shared interface can preserve client code when the vendor behind a supported capability changes. That is useful here because the CRM consumer should receive the same application-level result regardless of who produced the transcript. The acceptance condition remains stricter than “the client parsed the response.”

Infrai provides one REST API with no SDK required, one key, and one bill across 295 routes / 20 modules. Its OpenAI-compatible surface supports provider portability, while public, self-describing discovery requires no key. For a call-processing worker using several supported capabilities, a single API key reduces credential handoffs, and plain HTTP lets the readiness check use the standard library. Keep internal permissions narrow anyway: consolidating credentials does not replace authorization within the sales workflow.

Keep extraction separate.

For evaluation, include 3 contrasting fixtures: an explicit commitment to send a proposal, a request conditional on agency approval, and a refusal to receive SMS. Compare the proposed CRM action and its supporting quote. These are test cases, not accuracy measurements. A candidate that produces readable text but reverses the condition should fail promotion for this workflow. Keep the extraction prompt and recording revision fixed while evaluating a replacement, because changing both at once obscures which change altered the action. Record disagreements at the action level: a missing task, an incorrect recipient, an approval condition dropped from the evidence, or a contact permission inferred from a passing mention of a channel. If two candidates disagree, send the case to review rather than voting across transcripts; agreement between generated outputs is not independent proof of what the advertiser authorized. This adds migration work, but it provides a useful release artifact: a reviewable list of action differences instead of an unsupported claim that the providers are equivalent.

## 4. Put the write boundary in executable code

The following Python example checks a live model catalog, then demonstrates the local write boundary with fixtures. Set INFRAI_BASE_URL to the deployment's documented API base ending in /v1, INFRAI_API_KEY to its credential, and ASR_MODEL_ID to the exact target catalog ID. It uses only the standard library. The subsequent transcript values are illustrative adapter outputs, not responses from the catalog request; actual transcription and CRM delivery remain separate operations.

```python
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def target_ready():
    base = os.environ["INFRAI_BASE_URL"].rstrip("/")
    if not base.startswith("https://") or not base.endswith("/v1"):
        raise ValueError("Expected an HTTPS API base ending in /v1")
    for attempt in range(3):
        request = Request(
            base + "/ai/models",
            headers={"Authorization": "Bearer " + os.environ["INFRAI_API_KEY"]},
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                catalog = json.load(response)
            return any(
                model["id"] == os.environ["ASR_MODEL_ID"]
                and model.get("available") is True
                for model in catalog["data"]
            )
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code != 429 or attempt == 2:
                raise RuntimeError(f"Catalog status {error.code}: {detail}") from error
            delay = 2 ** attempt
            retry_after = error.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, int(retry_after))
                except ValueError:
                    deadline = parsedate_to_datetime(retry_after)
                    delay = max(delay, (deadline - datetime.now(timezone.utc)).total_seconds())
            time.sleep(delay)


print({"target_ready": target_ready()})


def select_result(candidates):
    for candidate in candidates:
        if candidate["approved"] and candidate["available"]:
            if not candidate["text"].strip():
                raise ValueError("Empty transcript requires review")
            return candidate
    raise RuntimeError("Hold recording: no approved, ready candidate")


def accept_intent(db, event_key, transcript, quote, action, reviewed):
    if not reviewed:
        raise ValueError("Human approval required")
    if not quote or quote not in transcript["text"]:
        raise ValueError("Action evidence is missing")
    with db:
        cursor = db.execute(
            "INSERT INTO intents(event_key, provider, evidence, action) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(event_key) DO NOTHING",
            (event_key, transcript["provider"], quote, action),
        )
    return cursor.rowcount == 1


with sqlite3.connect(":memory:") as db:
    db.execute(
        "CREATE TABLE intents (event_key TEXT PRIMARY KEY, "
        "provider TEXT NOT NULL, evidence TEXT NOT NULL, "
        "action TEXT NOT NULL)"
    )
    transcript = select_result([
        {"provider": "primary", "approved": True,
         "available": False, "text": ""},
        {"provider": "replacement", "approved": True,
         "available": True,
         "text": "Send the revised sponsorship proposal on Friday."},
    ])
    event_key = "media-call-42:recording-r1:proposal-followup"
    for attempt in range(2):
        created = accept_intent(
            db, event_key, transcript,
            "Send the revised sponsorship proposal on Friday.",
            "Review sponsorship proposal follow-up", reviewed=True,
        )
        print({"attempt": attempt + 1, "intent_created": created})
    count = db.execute("SELECT COUNT(*) FROM intents").fetchone()[0]
    assert count == 1
```

The first insertion succeeds; the second reports that it did not create an intent. The event key deliberately excludes the provider name and retry number. Including either would allow the same sales follow-up to acquire a new identity during fallback. In production, the business key must come from the call and action model, and the ledger must persist across process restarts.

A missing catalog entry means readiness has not been established, not that the model is permanently unsupported. The catalog result is printed separately so the fixture cannot be mistaken for a live transcription attempt.

Identity matters here.

This example records an intent locally. It does not prove exactly-once delivery to an external CRM. A production worker still needs a durable handoff and either destination idempotency or reconciliation after an uncertain write result. Otherwise, a process can lose the response after the CRM accepts a task and create another task on retry. RFC 9110's retry semantics are relevant here: sending the same request again does not by itself make a business operation idempotent.

The quote check is intentionally narrow, too. It verifies that the evidence exists in the transcript; it does not prove that the speaker consented or that the proposed action follows logically. That is why review remains explicit. Outbound email and SMS should have their own permission checks and deduplication boundaries, even if the CRM task was accepted.

## 5. Reject direct transcript-to-message automation for this rollout

Reject the shortcut that turns a successful replacement transcript directly into a CRM write and a customer message. It couples provider migration to customer contact, where a duplicated follow-up or a misread opt-out has consequences beyond an untidy task list. For a deliverability-sensitive sales workflow, preserving permission and preventing duplicate sends matter more than removing one internal review step.

The shortcut has a valid use case: an internal, read-only call digest with a visible transcript reference and no downstream action. There, accepting a candidate result for human reading can be reasonable after the provider and data handling have been approved.

For CRM actions, promote a replacement only after it passes the same semantic fixtures, preserves the action's business key, and meets the recording's processing constraints. Keep approval before customer contact. That gives a media team a practical portability decision: providers may change behind the transcript contract, while the meaning and identity of the sales follow-up remain controlled.

## References

- [HTTP semantics and retry considerations](https://www.rfc-editor.org/rfc/rfc9110)
- [OpenAI speech-to-text documentation](https://platform.openai.com/docs/guides/speech-to-text)
- [Deepgram documentation](https://developers.deepgram.com/docs)
- [AssemblyAI documentation](https://www.assemblyai.com/docs)
- [Gemini documentation](https://ai.google.dev/gemini-api/docs)
- [Claude documentation](https://docs.anthropic.com/en/docs/overview)
