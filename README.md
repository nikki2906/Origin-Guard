# Origin Guard

A backend API that classifies text-based content as human-written or AI-generated. Any creative sharing platform can plug into this system to protect attribution, build trust, and give audiences honest context about the content they read.

## Architecture Overview

A submission travels through the following path:

1. Creator sends text to `POST /submit`
2. Rate limiter checks if the creator has exceeded their request limit
3. Signal 1 (Groq LLM) analyzes the semantic patterns and writing style
4. Signal 2 (Stylometric Heuristics) measures statistical properties of the text
5. Both scores combine into a single weighted confidence score
6. Confidence score maps to a transparency label in plain English
7. Everything is written to the audit log
8. Response returns to the creator with attribution, confidence, and label

An appeal travels through this path:

1. Creator sends `POST /appeal` with their content ID and reasoning
2. Submission status updates from "classified" to "under_review"
3. Appeal is logged alongside the original classification decision
4. Creator receives confirmation that their appeal was received

## Detection Signals

### Signal 1 - LLM Classifier
- **What it measures:** Semantic patterns, writing style, and holistic feel of the text. The LLM has been trained on vast amounts of both human and AI-generated text, giving it an intuition for the patterns that distinguish them.
- **Why I chose it:** It captures meaning and context that pure math cannot. It reads the text the way a human reader would.
- **What it misses:** Can misclassify formal or precise human writers as AI, particularly non-native English speakers and academics whose clean structured writing statistically resembles AI output.
- **Output:** A score between 0 and 1 where 1 means very likely AI-generated and 0 means very likely human-written.

### Signal 2 - Stylometric Heuristics
- **What it measures:** Statistical properties of the text including:
  - Sentence length variance (AI writing is more uniform)
  - Type-token ratio (vocabulary diversity — originally intended to catch AI's tendency toward repeated phrasing)
  - Informal punctuation density (humans use ! and ? more expressively)
  - Average sentence length (AI tends to write longer, more complete sentences)
- **Why I chose it:** It is completely independent from the LLM. It does not read meaning at all, it just measures structure. This means it catches patterns the LLM might miss and covers the LLM's blind spots.
- **What it misses:** Cannot read meaning, so heavily edited AI text with added irregularities may fool it into scoring as human. It also has a specific weakness in short passages — see Known Limitations below.
- **Output:** A score between 0 and 1 where 1 means very likely AI-generated and 0 means very likely human-written.

### Combining Signals
The final confidence score is a weighted average:

```
final_score = (llm_score x 0.55) + (stylo_score x 0.45)
```

The LLM still carries slightly more weight because it captures meaning and context, which is harder to fake than statistical structure alone. The weighting was originally 0.6/0.4 but was adjusted after testing revealed the stylometric signal's type-token ratio metric was unreliable on short passages (see Known Limitations) — increasing stylo's weight slightly, once combined with better test examples, produced more accurate results without over-trusting either signal.

## Confidence Scoring

| Score Range | Meaning |
|-------------|---------|
| Above 0.75 | High confidence AI |
| 0.45 - 0.75 | Uncertain |
| Below 0.45 | High confidence human |

A score of 0.51 and 0.95 produce meaningfully different labels. 0.51 falls in the uncertain range while 0.95 triggers the high confidence AI label.

### Example Submissions

**High confidence AI (confidence: 0.787)**
```
Text: "The rapid advancement of artificial intelligence technology has fundamentally
transformed the modern business landscape in numerous significant ways. The rapid
advancement of artificial intelligence technology has created substantial opportunities
for organizations across the global economy. The rapid advancement of artificial
intelligence technology has introduced considerable challenges related to ethics and
governance frameworks. The rapid advancement of artificial intelligence technology has
prompted stakeholders to reconsider traditional operational strategies entirely. The
rapid advancement of artificial intelligence technology continues to influence policy
decisions made by governments worldwide."

llm_score: 0.9
stylo_score: 0.648
confidence: 0.787
attribution: likely_ai
```

**Low confidence / likely human (confidence: 0.253)**
```
Text: "ok so i finally tried that new ramen place downtown and honestly? underwhelming.
the broth was fine but they put WAY too much sodium in it and i was thirsty for like
three hours after. my friend got the spicy version and said it was better. probably
wont go back unless someone drags me there"

llm_score: 0.2
stylo_score: 0.318
confidence: 0.253
attribution: likely_human
```

These two examples were run directly against the live API, not simulated, and show a clear ~0.53 spread in confidence between a clearly-AI and clearly-human sample — confirming the scoring produces meaningful separation rather than clustering around one value.

## Transparency Label

Three label variants based on confidence score:

### High Confidence AI (score > 0.75)
> "This content appears to be AI-generated. If you believe this is incorrect, you may submit an appeal."

### Uncertain (score between 0.45 and 0.75)
> "This content shows mixed signals. We were unable to determine with confidence whether it was written by a human or generated by AI. If you believe this is incorrect, you may submit an appeal."

### High Confidence Human (score < 0.45)
> "This content appears to be written by a human."

## Rate Limiting

Rate limits applied to `POST /submit`:
- **10 requests per minute**
- **100 requests per day**

**Reasoning:** A legitimate creator submitting their own work would rarely need to submit more than a few pieces per minute. 10 per minute is generous enough for normal usage while preventing automated scripts from flooding the system. 100 per day reflects realistic daily usage for an active creator on a writing platform.

Evidence of rate limiting working (status codes from 12 rapid requests, run immediately after a server restart so the rate-limit window was clean):
```
200 200 200 200 200 200 200 200 200 200 429 429
```

Note: the exact split between 200s and 429s depends on how many `/submit` requests already occurred within the current one-minute window, since the limiter tracks a rolling window across all submissions rather than resetting per test run. In one rehearsal where earlier submissions had already used part of the window, the result was `200 x7, 429 x5` instead — still correctly enforcing the 10/minute cap, just against a window that wasn't empty at the start of the loop.

## Known Limitations

### Limitation 1 - Formal Human Writers
A non-native English speaker or academic writer who writes very formally and precisely will likely be misclassified as AI. Their clean structured writing style statistically resembles AI output and both signals may wrongly flag them. This is the most critical false positive scenario and is why the appeals workflow exists.

### Limitation 2 - Heavily Edited AI Text
A user who takes AI-generated text and heavily edits it by adding irregular sentence lengths, varied vocabulary, and typos may fool both signals. The stylometric heuristics score it as human because the structure looks messy, while the LLM may also be fooled because the meaning has been altered enough to seem natural. The system would return an uncertain or incorrect human classification.

### Limitation 3 - Type-Token Ratio on Short Passages
During testing, a clearly AI-generated short paragraph (under 50 words) scored a stylometric confidence of only 0.439 instead of landing clearly in "AI" territory, even though its sentence structure and punctuation were textbook AI patterns. The cause was the type-token ratio (TTR) metric, which assumes low vocabulary diversity signals AI-written text. On short passages, however, a coherent paragraph of any origin — human or AI — will naturally have high vocabulary diversity simply because there isn't enough text for words to repeat. TTR is a much stronger signal at paragraph or page length, where AI's tendency toward repeated phrasing compounds across more sentences. On short text it is closer to noise, and weighting it at 30% within the stylometric signal was pulling otherwise-correct classifications toward "uncertain." This is a real blind spot in the current implementation: content submitted in short bursts (a tweet-length caption, a single paragraph excerpt) is more likely to receive a less confident stylometric score regardless of true origin. A production fix would either drop TTR's weight specifically for texts under some minimum word count, or exclude it from scoring entirely below that threshold.

## Spec Reflection

**One way the spec helped:** The requirement to write out all three transparency label variants in planning.md before building forced me to think about the user experience before the technical implementation. This made it much easier to implement the label generation function because the exact text was already decided.

**One way implementation diverged from the spec:** In planning.md I assumed the stylometric signal would differentiate clearly between AI and human text on its own. In practice the signal alone produced scores that were too close together, and testing later revealed the type-token ratio metric specifically was unreliable on short passages (see Known Limitations, Limitation 3). I had to add a fourth metric (average sentence length) and, after further testing with more realistic examples, rebalance the combination weights from 0.6/0.4 to 0.55/0.45 in favor of the stylometric signal. The combined system works well, but the stylometric signal alone — and specifically its TTR component — is weaker than anticipated on short inputs.

## AI Usage

### Instance 1
**What I directed the AI to do:** Generate the Flask app skeleton with the POST /submit route and the Signal 1 Groq classifier function.

**What I revised:** The initial Groq prompt did not specify a JSON response format, so the model was returning unstructured text that was difficult to parse. I revised the prompt to explicitly request a JSON object with a score field and added response_format json_object to the API call to enforce structured output.

### Instance 2
**What I directed the AI to do:** Generate the stylometric heuristics function combining sentence length variance, type-token ratio, and punctuation density into a single score.

**What I revised:** The initial normalization values produced scores that were too similar between AI and human text. I added a fourth metric (average sentence length) and adjusted the normalization thresholds and weights to produce better separation between clearly AI and clearly human text. Later testing (documented in Known Limitations) revealed the TTR component specifically was still underperforming on short passages, which I addressed by rebalancing the top-level signal combination weights rather than rewriting TTR itself, given time constraints.

## API Endpoints

### POST /submit
Accepts a piece of text for attribution analysis.

**Request:**
```json
{
  "text": "your text here",
  "creator_id": "user-123"
}
```

**Response:**
```json
{
  "content_id": "uuid",
  "attribution": "likely_ai | uncertain | likely_human",
  "confidence": 0.787,
  "llm_score": 0.9,
  "stylo_score": 0.648,
  "label": "transparency label text"
}
```

### POST /appeal
Contest a classification decision.

**Request:**
```json
{
  "content_id": "uuid",
  "creator_reasoning": "explanation"
}
```

**Response:**
```json
{
  "content_id": "uuid",
  "message": "Your appeal has been received and is under review.",
  "status": "under_review"
}
```

### GET /log
Returns all audit log entries.

**Response:**
```json
{
  "entries": [
    {
      "content_id": "uuid",
      "creator_id": "user-123",
      "timestamp": "2026-06-28T20:29:12.977155Z",
      "llm_score": 0.70,
      "stylo_score": 0.50,
      "confidence": 0.62,
      "attribution": "uncertain",
      "label": "transparency label text",
      "status": "under_review",
      "appeal": {
        "creator_reasoning": "explanation",
        "timestamp": "2026-06-28T20:33:16.158334Z"
      }
    }
  ]
}
```