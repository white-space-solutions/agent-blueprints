# After you import the agent

The JSON carries the prompt, the skills, the schedules and the webhook
definitions. It does not carry any of the following, and the agent will run
badly or not at all until they are set.

1. **Credentials on each skill.** Every `skills/clients/*/credentials.md` lists what
   the skill's scripts read from the environment. Set them on the skill in
   the Hyperagent UI. Nothing in this repo contains a real key.
2. **Model.** The export pins `deepseek/deepseek-v4-pro`. Pick the model you
   want from the dropdown; the prompt does not depend on the model.
3. **Integrations.** `allowedIntegrations` names the connected apps the agent
   may use (Gmail, Slack, Close, Neon, and so on). Connect the ones you have
   and remove the rest.
4. **Webhook endpoints.** Creating each endpoint issues a fresh URL and
   secret. Services that cannot send a custom header (Close, Cal.com) need a
   small relay that verifies their signature and forwards with
   `X-Hyperagent-Webhook-Secret`. The `vapi-api` skill documents the shape.
5. **Context files.** Pin your own Game Plan (see `knowledge/`) as a context
   file. The prompt refers to it by name.
6. **Tables.** The lead activity ledger is a Hyperagent Table the agent
   maintains. Create it and put its id where the prompt says
   `<ledger-table-id>`.
7. **Placeholders.** Work through the table in the root README: `Alex`,
   `Ava`, `Brand A` / `Brand B` and their domains and product lines, the
   booking slugs, `<your-cal-handle>`, every `<...>` id, and the `+1555` SMS
   number.
8. **Read-only first.** Three of the four schedules write to the CRM and send
   messages. Run them in read-only mode for a week, read the threads, then
   turn writes on.
