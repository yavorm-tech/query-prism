# Incident Response Runbook — Halvard Cloud Platform

Maintained by the Site Reliability team. Last reviewed March 2026.

## Severity levels

| Severity | Definition | Example |
|---|---|---|
| SEV1 | Customer-facing outage or data loss affecting more than 10 % of customers | Sensor data ingestion stopped for all EU customers |
| SEV2 | Major degradation, or an outage for a single large customer | Dashboards loading in over 30 seconds |
| SEV3 | Minor issue with a workaround | One report export fails intermittently |

## Paging

Alerts page the on-call engineer through Beacon, our paging service. The on-call engineer must acknowledge a page within 10 minutes for SEV1 and within 30 minutes for SEV2. If a SEV1 page is not acknowledged in 10 minutes, Beacon escalates automatically to the secondary on-call, and after a further 10 minutes to the Head of SRE, currently Tomasz Erdély.

On-call rotations last one week and hand over on Mondays at 10:00 CET. On-call engineers receive a stipend of €300 per week on call.

## Roles during an incident

1. **Incident Commander (IC)** — owns the incident, coordinates, makes decisions. For SEV1 the IC is the first responder until they hand over explicitly.
2. **Communications lead** — updates the public status page and customer success.
3. **Scribe** — keeps the timeline in the incident channel.

Every incident gets its own Slack channel named `#inc-YYYYMMDD-short-name`.

## Communication

For SEV1, the status page at status.halvard.example must be updated within 15 minutes of declaring the incident, and then at least every 30 minutes until resolution. For SEV2, update every 60 minutes. Customer success is told about any SEV1 immediately so they can contact affected key accounts.

## Mitigation first

Restore service before finding the root cause. Preferred mitigations, in order: roll back the last deploy, fail over to the standby region (Frankfurt to Amsterdam), scale out, disable the offending feature flag.

## After the incident

- A blameless postmortem is required for every SEV1 and SEV2, published within 5 business days.
- Action items from postmortems are tracked in the RELIABILITY Jira project and must have an owner and a due date.
- Logs and metrics related to the incident are retained for 90 days; the incident timeline is kept permanently.

## Contacts

Head of SRE: Tomasz Erdély. Security incidents follow the separate security incident process and must also be reported to security@halvard.example within 1 hour.
