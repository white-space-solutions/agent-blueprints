# The agent framework

One page, six words. Every agent in this repo is described this way, and the
job card asks the six questions that fill it in.

| | Question it answers | Where it lives in a Hyperagent export |
|---|---|---|
| **Role** | Who is this, in one sentence a new hire would understand? | The first paragraph of `systemPrompt`, and `description` |
| **Responsibilities** | What is it accountable for, and what number says it did the job? | The north-star line and the "your loop" section of the prompt |
| **Skills** | What does it know how to do, as written instructions it can follow? | `skills[]`: doctrine (no code) and clients (a script plus a credential) |
| **Tools** | What can it reach, and which of those can it write to? | `allowedIntegrations` and `toolSettings` |
| **Knowledge** | What documents does it work from, and who owns them? | Pinned context files and tables (not in the export; see `knowledge/` in each agent) |
| **Guardrails** | What must it never do, whatever the input says? | The safety-rules section of the prompt, lifted into `guardrails.md` |

Two habits that make the difference between an agent that runs and one that
runs well:

- **Doctrine goes in skills, not the prompt.** The prompt says what the job
  is. A skill says how to do one part of it, and it can be edited, reviewed
  and reused without touching the prompt. The lead agent's prompt is long
  because it grew before this rule existed; the four doctrine skills added
  later are the shape to copy.
- **Anything deterministic goes in a script.** Money, dates, thresholds,
  signatures. The model calls the script and reads the result. It never does
  the arithmetic, not even as a sanity check.
