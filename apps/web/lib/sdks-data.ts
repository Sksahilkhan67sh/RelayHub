export interface Sdk {
  name: string;
  install: string;
  lang: string;
  status: { tone: "green" | "amber"; label: string };
  clientCode: string;
  builderCode: string;
}

export const SDKS: Sdk[] = [
  {
    name: "Node.js / TypeScript",
    install: "npm install relayhub-sdk",
    lang: "TypeScript",
    status: { tone: "green", label: "Built, typechecked, 12/12 tests passing" },
    clientCode: `const client = new RelayHubClient({ apiKey });`,
    builderCode: `RelayHubClient.builder().apiKey(apiKey).timeout(10_000).build();`,
  },
  {
    name: "Python",
    install: "pip install relayhub",
    lang: "Python",
    status: { tone: "green", label: "ruff clean, mypy clean, 13/13 tests passing" },
    clientCode: `client = RelayHubClient(api_key=api_key)`,
    builderCode: `RelayHubClient.builder().api_key(api_key).timeout(10.0).build()`,
  },
  {
    name: "Go",
    install: "go get github.com/relayhub/relayhub-go",
    lang: "Go",
    status: { tone: "amber", label: "Written and reviewed, not compiled in this environment" },
    clientCode: `client := relayhub.New(apiKey)`,
    builderCode: `relayhub.NewBuilder().APIKey(apiKey).Timeout(10*time.Second).Build()`,
  },
  {
    name: "Java",
    install: "io.github.Sksahilkhan67sh:relayhub-sdk:1.0.0 (Maven)",
    lang: "Java",
    status: { tone: "amber", label: "Written and reviewed, not compiled in this environment" },
    clientCode: `RelayHubClient client = new RelayHubClient(apiKey);`,
    builderCode: `RelayHubClient.builder().apiKey(apiKey).timeout(Duration.ofSeconds(10)).build();`,
  },
];

export const RESOURCES = [
  "auth",
  "apiKeys / api_keys / APIKeys",
  "organizations (+ nested invitations)",
  "endpoints",
  "events",
  "deliveries",
  "dlq",
  "analytics",
  "billing",
  "notifications",
  "audit",
];
