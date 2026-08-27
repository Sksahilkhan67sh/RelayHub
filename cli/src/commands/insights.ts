import { ParsedArgs, flagString, flagNumber } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, color } from "../output.js";

// Wraps relayhub-sdk's client.insights (Phase 3 AI Intelligence layer, mounted
// at /v1/insights/intelligence/...). No new backend or SDK endpoints -- this
// is a CLI surface over what InsightsResource already exposes.
export async function insightsCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const view = args.positionals[0] ?? "health";

    switch (view) {
      case "health": {
        const endpointId = flagString(args.flags, "endpoint-id");
        const snapshots = await client.insights.health({ endpoint_id: endpointId });
        if (args.flags.json) return printJson(snapshots);
        printTable(
          ["ENDPOINT", "STATUS", "HEALTH SCORE", "CONFIDENCE", "SAMPLE SIZE"],
          snapshots.map((s) => [
            s.endpoint_id,
            s.status,
            s.health_score != null ? s.health_score.toFixed(2) : "-",
            `${(s.confidence * 100).toFixed(0)}%`,
            String(s.sample_size),
          ])
        );
        return;
      }
      case "health-history": {
        const endpointId = args.positionals[1];
        if (!endpointId) {
          console.log("Usage: relay insights health-history <endpointId> [--limit N] [--offset N]");
          process.exit(1);
        }
        const history = await client.insights.healthHistory(endpointId, {
          limit: flagNumber(args.flags, "limit"),
          offset: flagNumber(args.flags, "offset"),
        });
        if (args.flags.json) return printJson(history);
        printTable(
          ["WINDOW START", "STATUS", "HEALTH SCORE"],
          history.map((s) => [s.window_start, s.status, s.health_score != null ? s.health_score.toFixed(2) : "-"])
        );
        return;
      }
      case "anomalies": {
        const anomalies = await client.insights.anomalies({
          endpoint_id: flagString(args.flags, "endpoint-id"),
          metric: flagString(args.flags, "metric"),
          since: flagString(args.flags, "since"),
          limit: flagNumber(args.flags, "limit"),
        });
        if (args.flags.json) return printJson(anomalies);
        printTable(
          ["METRIC", "DIRECTION", "OBSERVED", "BASELINE", "CONFIDENCE", "INCIDENT"],
          anomalies.map((a) => [
            a.metric,
            a.direction,
            String(a.observed_value),
            String(a.baseline_value),
            `${(a.confidence * 100).toFixed(0)}%`,
            a.incident_id ?? "-",
          ])
        );
        return;
      }
      case "incidents": {
        const incidents = await client.insights.incidents({
          status: flagString(args.flags, "status"),
          endpoint_id: flagString(args.flags, "endpoint-id"),
          limit: flagNumber(args.flags, "limit"),
        });
        if (args.flags.json) return printJson(incidents);
        printTable(
          ["ID", "STATUS", "SEVERITY", "FAILURE CATEGORY", "TITLE", "OPENED"],
          incidents.map((i) => [i.id, i.status, i.severity, i.failure_category, i.title, i.opened_at])
        );
        return;
      }
      case "incident": {
        const incidentId = args.positionals[1];
        if (!incidentId) {
          console.log("Usage: relay insights incident <incidentId>");
          process.exit(1);
        }
        const incident = await client.insights.getIncident(incidentId);
        if (args.flags.json) return printJson(incident);
        console.log(`${color.bold("Incident:")}    ${incident.id}`);
        console.log(`${color.bold("Status:")}      ${incident.status}`);
        console.log(`${color.bold("Severity:")}    ${incident.severity}`);
        console.log(`${color.bold("Title:")}       ${incident.title}`);
        console.log(`${color.bold("Summary:")}     ${incident.summary}`);
        console.log();
        // FACT vs INFERENCE: anomalies are measured signals, RCA entries are
        // explanations (some deterministic/rule-based, some AI-generated) --
        // keep that distinction visible rather than flattening them together.
        console.log(color.bold(`Anomalies (measured) -- ${incident.anomalies.length}`));
        for (const a of incident.anomalies) {
          console.log(`  - ${a.metric} ${a.direction} (observed ${a.observed_value}, baseline ${a.baseline_value})`);
        }
        console.log();
        console.log(color.bold(`Root cause analysis -- ${incident.rca_entries.length}`));
        for (const rca of incident.rca_entries) {
          const sourceLabel = rca.source === "ai" ? color.magenta("[AI inference]") : color.cyan("[deterministic]");
          console.log(`  ${sourceLabel} ${rca.likely_cause} (confidence: ${rca.confidence_level})`);
        }
        return;
      }
      case "rca": {
        const incidentId = args.positionals[1];
        if (!incidentId) {
          console.log("Usage: relay insights rca <incidentId>");
          process.exit(1);
        }
        const entries = await client.insights.incidentRca(incidentId);
        if (args.flags.json) return printJson(entries);
        printTable(
          ["SOURCE", "LIKELY CAUSE", "CONFIDENCE", "AI MODEL"],
          entries.map((e) => [e.source, e.likely_cause, e.confidence_level, e.ai_model ?? "-"])
        );
        return;
      }
      case "recommendations": {
        const incidentId = args.positionals[1];
        if (!incidentId) {
          console.log("Usage: relay insights recommendations <incidentId>");
          process.exit(1);
        }
        const recs = await client.insights.incidentRecommendations(incidentId);
        if (args.flags.json) return printJson(recs);
        if (recs.recommendations.length === 0) {
          console.log(color.gray("(no recommendations)"));
          return;
        }
        recs.recommendations.forEach((r, i) => console.log(`  ${i + 1}. ${r}`));
        return;
      }
      case "timeline": {
        const incidentId = args.positionals[1];
        if (!incidentId) {
          console.log("Usage: relay insights timeline <incidentId>");
          process.exit(1);
        }
        const timeline = await client.insights.incidentTimeline(incidentId);
        if (args.flags.json) return printJson(timeline);
        printTable(
          ["AT", "TYPE", "DETAIL"],
          timeline.events.map((e) => [e.at, e.type, e.detail])
        );
        return;
      }
      default:
        console.log(
          "Usage: relay insights <health|health-history|anomalies|incidents|incident|rca|recommendations|timeline> [args] [flags]"
        );
    }
  });
}
