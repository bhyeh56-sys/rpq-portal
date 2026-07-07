# RPQ MT5 Snapshot Sender

`RPQSnapshotSender.mq5` sends signed account snapshots from MT5 to:

```text
https://rpqtfund.com/fx/mt5/snapshot
```

## Install

1. Open MT5.
2. Go to `File` -> `Open Data Folder`.
3. Copy `RPQSnapshotSender.mq5` into `MQL5/Experts/`.
4. Open MetaEditor, compile `RPQSnapshotSender.mq5`.
5. Attach the EA to a chart.

## Inputs

- `WebhookUrl`: default `https://rpqtfund.com/fx/mt5/snapshot`
- `FxAccountId`: the server-side `fx_accounts.id`
- `FxSecret`: the server-side secret for that FX account
- `SendIntervalSeconds`: send interval in seconds, default `15`
- `DebugMode`: when `true`, prints signing diagnostics without printing the secret or body

Do not paste `FxSecret` into logs, screenshots, or shared config exports.

## WebRequest Allowlist

MT5 blocks WebRequest calls unless the target URL is allowed.

1. Go to `Tools` -> `Options` -> `Expert Advisors`.
2. Enable `Allow WebRequest for listed URL`.
3. Add:

```text
https://rpqtfund.com
```

4. Click `OK`, then reload or restart the EA.

## Payload And Signature

The EA sends compact JSON with string values:

```json
{"asof_at":"2026-06-05T12:00:00+00:00","balance":"10000.00","equity":"10050.00","free_margin":"10050.00","margin":"0.00"}
```

It signs the exact UTF-8 request body bytes with HMAC-SHA256 and sends:

- `X-FX-Account-Id`
- `X-Signature`
- `Content-Type: application/json`

When `DebugMode=true`, the Experts log prints only body length, body SHA256, signature length, and whether the signature is lowercase hex. It never prints `FxSecret` or the raw request body.
